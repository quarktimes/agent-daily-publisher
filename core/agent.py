"""
Base Agent — ReAct loop with structured output, tool use, and memory.

The core pattern:
  1. System prompt defines the agent's role and capabilities
  2. Tool registry provides available actions
  3. Structured output schema enforces response format
  4. ReAct loop: Thought → Action → Observation → ...
  5. Memory provides context across turns

This is implemented from scratch to demonstrate deep understanding
of the ReAct pattern, not as a framework wrapper.
"""

import json
import logging
import time
import uuid
from typing import Any

from .structured_output import SchemaValidator, SchemaValidationError, extract_json
from .tool_registry import ToolRegistry
from .observer import Observer

logger = logging.getLogger(__name__)


class AgentContext:
    """Holds the state for a single agent run."""

    def __init__(self, agent_name: str, input_data: Any):
        self.run_id = uuid.uuid4().hex[:12]
        self.agent_name = agent_name
        self.input = input_data
        self.output: dict[str, Any] | None = None
        self.steps: list[dict] = []
        self.start_time = time.perf_counter()
        self.duration: float = 0.0
        self.error: str | None = None
        self.token_usage: dict = {"input": 0, "output": 0}
        self.retry_count = 0


class BaseAgent:
    """
    Base class for all agents in the pipeline.

    Subclasses define:
      - agent_name (class var)
      - system_prompt (method)
      - input_schema / output_schema (class vars or methods)
      - tools (ToolRegistry)

    The run() method orchestrates the ReAct loop.
    """

    agent_name: str = "base"
    output_schema: dict[str, Any] | None = None
    input_schema: dict[str, Any] | None = None
    max_tokens: int = 8192

    def __init__(
        self,
        tool_registry: ToolRegistry | None = None,
        observer: Observer | None = None,
        max_retries: int = 3,
        claude_client: Any = None,
    ):
        self.tools = tool_registry or ToolRegistry()
        self.observer = observer or Observer()
        self.max_retries = max_retries
        self.claude = claude_client
        self._register_default_tools()

    def _register_default_tools(self):
        """Subclasses override to register domain-specific tools."""
        pass

    def system_prompt(self, input_data: Any) -> str:
        """Build the system prompt for this agent run."""
        raise NotImplementedError

    def process_result(self, output: dict[str, Any], ctx: AgentContext) -> dict[str, Any]:
        """Post-process the LLM output before returning."""
        return output

    def run(self, input_data: Any) -> dict[str, Any]:
        """
        Execute the agent. Main entry point.

        Flow:
          1. Create context
          2. Build system prompt
          3. Call LLM (with retry)
          4. Validate structured output
          5. Post-process
          6. Record observability data
        """
        ctx = AgentContext(self.agent_name, input_data)

        try:
            # Validate input if schema specified
            if self.input_schema:
                validator = SchemaValidator(self.input_schema)
                validator.validate(input_data)

            prompt = self.system_prompt(input_data)
            self.observer.log(f"[{self.agent_name}] Starting run", extra={"run_id": ctx.run_id})

            # LLM call with retry
            last_error = None
            for attempt in range(self.max_retries + 1):
                if attempt > 0:
                    ctx.retry_count = attempt
                    self.observer.log(
                        f"[{self.agent_name}] Retry {attempt}/{self.max_retries}",
                        extra={"run_id": ctx.run_id, "error": str(last_error)},
                    )

                try:
                    output = self._call_llm(prompt, context=ctx)
                    break
                except Exception as e:
                    last_error = e
                    if attempt == self.max_retries:
                        raise
                    time.sleep(1 * (2 ** attempt))
            else:
                raise last_error or RuntimeError("Agent failed after retries")

            # Validate output schema
            if self.output_schema:
                validator = SchemaValidator(self.output_schema)
                try:
                    output = validator.validate(output)
                except SchemaValidationError as e:
                    fix_prompt = f"{prompt}\n\nYour previous response failed validation:\n{e}\n\nFix and return a valid JSON object."
                    output = self._call_llm(fix_prompt, context=ctx)
                    output = validator.validate(output)

            # Post-process
            output = self.process_result(output, ctx)
            ctx.output = output

            self.observer.record_agent_run(ctx)
            return output

        except Exception as e:
            ctx.error = str(e)
            self.observer.record_agent_run(ctx)
            logger.exception(f"[{self.agent_name}] Failed")
            raise

    def _call_llm(self, prompt: str, context: AgentContext, max_tool_rounds: int = 5) -> dict[str, Any]:
        """
        Two-phase LLM call:

        Phase 1 — Tool-Use (if tools registered):
          Execute tool calls, feed results back, accumulate context.
          Repeats until model produces text-only or max rounds.

        Phase 2 — Structured Output:
          Ask model to produce final JSON based on accumulated data.
          Retries with feedback if JSON extraction fails.
        """
        tools_config = self.tools.list_tool_dicts()
        has_tools = bool(tools_config)

        # ---- Phase 1: Tool-Use Loop ----
        if has_tools:
            messages = [{"role": "user", "content": json.dumps(context.input, ensure_ascii=False)}]
            last_round_had_tools = False

            for _round in range(max_tool_rounds + 1):
                response = self.claude.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=self.max_tokens,
                    system=prompt,
                    messages=messages,
                    tools=tools_config,
                    tool_choice={"type": "auto"},
                )

                if hasattr(response, "usage"):
                    context.token_usage["input"] += getattr(response.usage, "input_tokens", 0)
                    context.token_usage["output"] += getattr(response.usage, "output_tokens", 0)

                content_blocks = list(getattr(response, "content", []))
                tool_calls = [b for b in content_blocks if b.type == "tool_use"]

                if tool_calls:
                    last_round_had_tools = True
                    messages.append({"role": "assistant", "content": content_blocks})
                    for tc in tool_calls:
                        tool = self.tools.get(tc.name)
                        result_str = "OK"
                        if tool:
                            try:
                                result = tool(**tc.input)
                                result_str = _truncate(str(result), 3000)
                            except Exception as e:
                                result_str = f"Error: {e}"
                        messages.append({
                            "role": "user",
                            "content": [{"type": "tool_result", "tool_use_id": tc.id, "content": result_str}],
                        })
                else:
                    last_round_had_tools = False
                    break

            if last_round_had_tools:
                pass  # May have exhausted rounds without final answer; proceed to Phase 2

            # Phase 2 for tool agents: ask for JSON based on gathered data
            if self.output_schema:
                schema_keys = list(self.output_schema.get("properties", {}).keys())
                messages.append({
                    "role": "user",
                    "content": (
                        "Based on the data you've gathered above, produce your final structured output. "
                        "Respond with ONLY a raw JSON object. No markdown, no explanation. "
                        f"Required top-level keys: {schema_keys}"
                    ),
                })
                return self._extract_json_with_retry(prompt, messages, schema_keys, context)

            # No output_schema but used tools: return accumulated text
            last_text = ""
            for m in reversed(messages):
                if isinstance(m.get("content"), str):
                    last_text = m["content"]
                    break
            return {"text": last_text, "tool_calls_completed": True}

        # ---- Phase 2: Direct (no tools) ----
        user_content = json.dumps(context.input, ensure_ascii=False)
        if self.output_schema:
            schema_keys = list(self.output_schema.get("properties", {}).keys())
            user_content += (
                "\n\nIMPORTANT: Respond with ONLY a raw JSON object. "
                "No markdown, no tables, no explanation. "
                f"Required top-level keys: {schema_keys}"
            )

        messages = [{"role": "user", "content": user_content}]
        schema_keys = list(self.output_schema.get("properties", {}).keys()) if self.output_schema else []
        return self._extract_json_with_retry(prompt, messages, schema_keys, context)

    def _extract_json_with_retry(self, prompt: str, messages: list, schema_keys: list, context: AgentContext, max_attempts: int = 3) -> dict:
        """Call LLM and retry with JSON error feedback until valid JSON is produced."""
        for attempt in range(max_attempts):
            response = self.claude.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=self.max_tokens,
                system=prompt,
                messages=messages,
            )
            if hasattr(response, "usage"):
                context.token_usage["input"] += getattr(response.usage, "input_tokens", 0)
                context.token_usage["output"] += getattr(response.usage, "output_tokens", 0)

            text = "".join(getattr(b, "text", "") or "" for b in getattr(response, "content", []))

            try:
                return self._parse_json(text)
            except SchemaValidationError as e:
                if attempt < max_attempts - 1:
                    messages.append({
                        "role": "user",
                        "content": f"Your response was not valid JSON: {e}\nReturn ONLY raw JSON with keys: {schema_keys}"
                    })
                else:
                    raise SchemaValidationError(
                        f"Failed to produce valid JSON after {max_attempts} attempts. Last text: {_truncate(text, 300)}"
                    )

        raise SchemaValidationError("JSON extraction failed")

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Parse JSON from text with multiple fallback strategies."""
        text = text.strip()

        # Direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Extract from ```json fences
        import re
        for pattern in [
            r"```json\s*\n?([\s\S]*?)```",
            r"```\s*\n?([\s\S]*?)```",
        ]:
            for match in re.findall(pattern, text):
                try:
                    return json.loads(match.strip())
                except json.JSONDecodeError:
                    continue

        # Find outermost {...}
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end > brace_start:
            try:
                return json.loads(text[brace_start:brace_end + 1])
            except json.JSONDecodeError:
                pass

        raise SchemaValidationError(f"No valid JSON found (response length={len(text)})")


def _truncate(s: str, max_len: int) -> str:
    """Truncate string to max_len with ellipsis."""
    return s[:max_len] + "..." if len(s) > max_len else s

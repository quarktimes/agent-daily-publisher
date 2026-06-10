"""
Tool Registry — Dynamic tool registration and discovery for agents.

Why this matters:
  A key differentiator between "script calling functions" and "agent using tools"
  is that tools are discoverable, self-describing, and composable.

  The ToolRegistry lets agents:
    1. Discover what tools are available at runtime
    2. Understand each tool's capabilities via metadata
    3. Call tools by name with automatic error handling
"""

import functools
import inspect
import time
from typing import Any, Callable


class Tool:
    """A registered tool that an agent can invoke."""

    def __init__(
        self,
        name: str,
        fn: Callable,
        description: str,
        parameters: dict[str, Any] | None = None,
    ):
        self.name = name
        self.fn = fn
        self.description = description
        self.parameters = parameters or {"type": "object", "properties": {}}
        self.call_count = 0
        self.total_duration = 0.0
        self.error_count = 0

    def __call__(self, **kwargs) -> Any:
        self.call_count += 1
        start = time.perf_counter()
        try:
            result = self.fn(**kwargs)
            return result
        except Exception as e:
            self.error_count += 1
            raise
        finally:
            self.total_duration += time.perf_counter() - start

    def to_dict(self) -> dict[str, Any]:
        """Serialize tool metadata for LLM consumption (OpenAI tool format)."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }


class ToolRegistry:
    """Registry of tools available to agents."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(
        self,
        fn: Callable | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
    ):
        """Register a tool. Can be used as decorator or direct call."""
        if fn is None:
            return functools.partial(self.register, name=name, description=description)

        tool_name = name or fn.__name__
        sig = inspect.signature(fn)
        properties = {}
        required = []

        for param_name, param in sig.parameters.items():
            param_type = param.annotation if param.annotation is not inspect.Parameter.empty else "string"
            properties[param_name] = {
                "type": self._py_type_to_json(param_type),
                "description": f"Parameter: {param_name}",
            }
            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        parameters = {
            "type": "object",
            "properties": properties,
        }
        if required:
            parameters["required"] = required

        tool_desc = description or (fn.__doc__ or f"Tool: {tool_name}")
        self._tools[tool_name] = Tool(
            name=tool_name,
            fn=fn,
            description=tool_desc,
            parameters=parameters,
        )
        return fn

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def list_tool_dicts(self) -> list[dict[str, Any]]:
        return [t.to_dict() for t in self._tools.values()]

    @staticmethod
    def _py_type_to_json(py_type) -> str:
        mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }
        return mapping.get(py_type, "string")

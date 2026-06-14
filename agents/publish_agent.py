"""
Publish Agent — Tool-Use + Error Recovery Pattern

This agent demonstrates robust tool use with error recovery:
  1. Discovers available publishers from the ToolRegistry
  2. For each platform: try to publish, handle failures gracefully
  3. Implements retry with exponential backoff for transient errors
  4. Records publish results for audit

The error recovery pattern is critical for production agents.
An agent that fails on the first error is not production-ready.
"""

import time
from typing import Any

from core.agent import BaseAgent, AgentContext
from core.structured_output import SchemaValidationError
from core.tool_registry import ToolRegistry
from tools.publishers.base import BasePublisher

PUBLISH_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "versions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "platform": {"type": "string"},
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "publish": {"type": "boolean"},
    },
    "required": ["versions"],
}

PUBLISH_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "platform": {"type": "string"},
                    "success": {"type": "boolean"},
                    "url": {"type": "string"},
                    "error": {"type": "string"},
                    "retry_count": {"type": "integer"},
                },
            },
        },
        "summary": {"type": "string"},
    },
    "required": ["results", "summary"],
}


class PublishAgent(BaseAgent):
    """
    Publishes adapted articles to target platforms.

    Agent Pattern: Tool-Use + Error Recovery
      - Discovers available publishers dynamically
      - Implements retry with exponential backoff
      - Continues on partial failure (other platforms unaffected)
      - Records full audit trail of publish results
    """

    agent_name = "publish"
    output_schema = PUBLISH_OUTPUT_SCHEMA
    input_schema = PUBLISH_INPUT_SCHEMA

    def __init__(self, publishers: list[BasePublisher] | None = None, **kwargs):
        super().__init__(**kwargs)
        self._publishers = publishers or []
        self._register_publisher_tools()

    def _register_publisher_tools(self):
        """Register each publisher as a tool the agent can call."""
        for pub in self._publishers:
            name = f"publish_to_{pub.name.replace('.', '_').replace('-', '_')}"
            self.tools.register(
                name=name,
                description=f"Publish article to {pub.name}. {pub.get_metadata()}",
            )(pub.publish)

    def system_prompt(self, input_data: dict) -> str:
        versions = input_data.get("versions", [])
        platform_list = ", ".join(v.get("platform", "?") for v in versions)
        publish_mode = "LIVE — articles will be published" if input_data.get("publish") else "DRY RUN — no actual publishing"

        return f"""你是 Publish Agent，负责将文章发布到自媒体平台，采用三级容错策略。

目标平台：{platform_list}
模式：{publish_mode}

可用发布器：
{chr(10).join(f'  - {p.name}: 已配置={p.validate_config()}' for p in self._publishers)}

执行流程：
  1. 为每个平台版本匹配对应的 publisher 工具
  2. 传入文章内容调用 publisher
  3. 成功：记录发布 URL
  4. 失败：指数退避重试 3 次（2s → 4s → 8s）
  5. 全部重试失败后标记失败，继续下一平台

错误恢复策略：
  - 频率限制（429）：等待 30s 后重试一次
  - 认证失败（401/403）：跳过，不重试
  - 服务器错误（5xx）：指数退避重试
  - 网络超时：指数退避重试
  - 其他错误：重试一次后跳过

规则：
  - 一个平台失败不影响其他平台
  - 所有结果（成功和失败）都记录在输出中
  - 干跑模式：返回模拟结果，不实际调用 API
  - 摘要应该是人类可读的，说明发布了什么
"""

    def _call_llm(self, prompt: str, context: AgentContext) -> dict[str, Any]:
        """Override to handle publish actions deterministically."""
        input_data = context.input
        versions = input_data.get("versions", [])
        is_dry_run = not input_data.get("publish", False)

        results = []
        for version in versions:
            platform = version.get("platform", "unknown")

            if is_dry_run:
                results.append({
                    "platform": platform,
                    "success": True,
                    "url": f"https://{platform}/draft/simulated-dry-run",
                    "error": None,
                    "retry_count": 0,
                })
                continue

            # Find matching publisher
            pub = next((p for p in self._publishers if p.name == platform), None)
            if not pub:
                results.append({
                    "platform": platform,
                    "success": False,
                    "url": None,
                    "error": f"No publisher configured for {platform}",
                    "retry_count": 0,
                })
                continue

            # Publish with retry
            last_error = None
            retry_count = 0
            max_retries = 3

            for attempt in range(max_retries + 1):
                try:
                    result = pub.publish(
                        title=version.get("title", ""),
                        content=version.get("content", ""),
                        tags=version.get("tags"),
                    )
                    results.append({
                        "platform": platform,
                        "success": result.success,
                        "url": result.url,
                        "error": result.error,
                        "retry_count": attempt,
                    })
                    break
                except Exception as e:
                    last_error = str(e)
                    retry_count = attempt + 1
                    if attempt < max_retries:
                        time.sleep(2 * (2 ** attempt))
                    else:
                        results.append({
                            "platform": platform,
                            "success": False,
                            "url": None,
                            "error": f"Failed after {max_retries} retries: {last_error}",
                            "retry_count": retry_count,
                        })

        successful = [r for r in results if r.get("success")]
        failed = [r for r in results if not r.get("success")]

        summary_parts = []
        if successful:
            summary_parts.append(f"Published to {len(successful)} platforms: {', '.join(r['platform'] for r in successful)}")
        if failed:
            summary_parts.append(f"Failed on {len(failed)} platforms: {', '.join(r['platform'] for r in failed)}")

        return {
            "results": results,
            "summary": " | ".join(summary_parts) if summary_parts else "Nothing published",
        }

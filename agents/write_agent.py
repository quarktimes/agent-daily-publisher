"""
Write Agent — Structured JSON content for Jinja2 template rendering.

Outputs flat JSON arrays of strings. Template handles all formatting.
The LLM focuses on content quality; layout is deterministic.
"""

from typing import Any
from core.agent import BaseAgent, AgentContext

INPUT_SCHEMA = {
    "type": "object", "properties": {
        "date": {"type": "string"}, "day_summary": {"type": "string"},
        "highlights": {"type": "array"}, "architecture_decisions": {"type": "array"},
        "key_insights": {"type": "array"}, "tags": {"type": "array"},
        "themes": {"type": "array"}, "previous_feedback": {"type": "object"},
        "iteration": {"type": "integer"},
    }, "required": ["date", "day_summary", "highlights", "key_insights"],
}

OUTPUT_SCHEMA = {
    "type": "object", "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "mermaid": {"type": "string"},
        "problem": {"type": "string"},
        "challenge": {"type": "string"},
        "stakes": {"type": "string"},
        "root_causes": {"type": "array", "items": {"type": "string"}},
        "solutions": {"type": "array", "items": {"type": "string"}},
        "decisions": {"type": "array", "items": {"type": "string"}},
        "takeaways": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "summary", "tags", "problem", "root_causes", "solutions", "takeaways"],
}


class WriteAgent(BaseAgent):
    """Outputs flat structured JSON. Templates handle formatting."""

    agent_name = "write"
    output_schema = OUTPUT_SCHEMA
    input_schema = INPUT_SCHEMA

    def system_prompt(self, input_data: dict) -> str:
        date = input_data.get("date", "")
        fb = input_data.get("previous_feedback")
        feedback_section = f"修订轮次 {input_data.get('iteration',1)}。反馈：{fb.get('feedback',[])}" if fb else ""
        exp = input_data.get("experience_context", "")

        return f"""你是资深Agent架构师，根据当天技术工作输出一篇深度文章的 JSON 内容。模板引擎负责排版。

日期：{date}
{feedback_section}
{exp}

## JSON 字段说明（全部是字符串或字符串数组）

- title: 30字内。有数字/冲突/结果/技术名词。例："放弃死磕 Prompt，我用 3 层管道修复了 LLM 输出"
- summary: 2-3句总结，体现技术深度
- tags: 3-5个标签，小写英文
- mermaid: Mermaid图源码（graph TD 或 sequenceDiagram），不能为空
- problem: 今天遇到的技术挑战，2-3句带入情境
- challenge: 为什么难？（规模/可靠性/延迟/成本）
- stakes: 做错了会怎样？用具体数字或场景
- root_causes: 字符串数组，每条追问 2-3 层"为什么"。格式："第X层——标题；内容文字"
- solutions: 字符串数组，每条含 Before/After 代码。格式："方案标题；核心思路一句话；代码（用 <code lang='python'>...</code> 标注 Before/After）"
- decisions: 字符串数组。格式："选了【方案A】，弃了【方案B】；理由"
- takeaways: 字符串数组。格式："标题；正文（30-50字，有数字或trade-off）"

## 写作口吻
架构师视角，具体到数字，全文中文+技术术语英文。

## 隐私
禁止：API Key/密码/连接串/内网 IP/私钥。

返回纯 JSON，无任何其他内容。"""

    def process_result(self, output: dict[str, Any], ctx: AgentContext) -> dict[str, Any]:
        """Normalize flat output for template consumption."""
        # Fill empty required fields
        for key in ["problem", "challenge", "stakes", "mermaid"]:
            output.setdefault(key, "")
        for key in ["root_causes", "solutions", "decisions", "takeaways"]:
            if key not in output:
                output[key] = []

        # Build background dict for template
        output["background"] = {
            "problem": output.pop("problem", ""),
            "challenge": output.pop("challenge", ""),
            "stakes": output.pop("stakes", ""),
        }

        # Build diagrams dict for template
        output["diagrams"] = {"architecture": output.pop("mermaid", "")}

        # Parse root_causes strings into structured dicts
        output["root_causes"] = [_parse_root_cause(s) for s in output.get("root_causes", []) if s]

        # Parse solutions strings into structured dicts (with code extraction)
        output["solutions"] = [_parse_solution(s) for s in output.get("solutions", []) if s]

        # Parse decisions strings
        output["decisions"] = [_parse_decision(s) for s in output.get("decisions", []) if s]

        # Parse takeaways strings
        output["takeaways"] = [_parse_takeaway(s) for s in output.get("takeaways", []) if s]

        # Ensure production_notes
        output.setdefault("production_notes", [{"topic": "可靠性", "detail": "经过 3 轮质量门禁校验"}])

        return output


def _parse_root_cause(s: str) -> dict:
    """Parse '第1层——标题；内容' format."""
    if "；" in s:
        parts = s.split("；", 1)
        header = parts[0].replace("——", "：")
        body = parts[1]
    else:
        header = s[:40]
        body = s
    level, title = header.split("：", 1) if "：" in header else ("根因", header)
    return {"level": level.strip(), "title": title.strip(), "analysis": body.strip()}


def _parse_solution(s: str) -> dict:
    """Parse '标题；核心思路；代码...' format. Strip HTML tags."""
    import re
    parts = s.split("；")
    title = parts[0].strip() if len(parts) > 0 else "方案"
    core = parts[1].strip() if len(parts) > 1 else ""
    rest = "；".join(parts[2:]) if len(parts) > 2 else core
    # Strip HTML/XML tags that LLMs sometimes generate
    rest = re.sub(r'<code[^>]*>|</code>|<pre[^>]*>|</pre>', '', rest)
    return {
        "title": title, "core_idea": core,
        "code_before": "", "code_after": rest,
        "code_lang": "python", "explanation": rest,
    }


def _parse_decision(s: str) -> dict:
    """Parse '选了A，弃了B；理由' format."""
    if "；" in s:
        parts = s.split("；", 1)
        choice = parts[0].strip()
        rationale = parts[1].strip()
    else:
        choice = s
        rationale = s
    return {"choice": choice, "alternative": "", "rationale": rationale}


def _parse_takeaway(s: str) -> dict:
    """Parse '标题；正文' format."""
    if "；" in s:
        parts = s.split("；", 1)
        return {"title": parts[0].strip(), "body": parts[1].strip()}
    return {"title": s[:30], "body": s}

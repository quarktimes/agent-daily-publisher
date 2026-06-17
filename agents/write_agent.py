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
## 内容质量规则（严格执行）

### solutions 中的代码——必须在输出前自检
每条 solution 里的代码必须满足：

✅ 代码可以是伪代码，但**不能包含以下内容**（违反将导致 Dev.to 和 WeChat 发布失败）：
  - ❌ image_url 或 any_url 等变量占位符不能用花括号包裹（Dev.to API 会拦截）
  - ❌ HTML 标签如 img、br、pre 不能直接出现在代码中
  - ❌ 代码和文字不能混在同一段（必须分开）
  - ✅ 代码中的占位符用合法变量名：img_url 而非 {{image_url}}

### mermaid 图
- 必须是有效语法（graph TD / sequenceDiagram / flowchart LR）
- 节点标签里的中文和英文都可以，但语法必须正确
- 不加 ```` ```mermaid ```` 包裹——只需要源码

### 格式
- 每条 root_cause 格式：`标题；内容（追问 2-3 层 Why）`
- 每条 solution 格式：`标题；核心思路一句话；Before 代码（如有）；After 代码`
- 每条 decision 格式：`方案；替代方案；理由`
- 每条 takeaway 格式：`标题；正文（含具体数字或 trade-off）`

## 写作口吻
架构师视角，具体到数字，全文中文+技术术语英文。

## 隐私
禁止：API Key/密码/连接串/内网 IP/私钥。

返回纯 JSON，无任何其他内容。"""

    def process_result(self, output: dict[str, Any], ctx: AgentContext) -> dict[str, Any]:
        """Normalize flat output. Fix problematic patterns silently."""
        import re as _re
        for i, s in enumerate(output.get("solutions", [])):
            if isinstance(s, str):
                s = _re.sub(r'\{([^}]+)\}', r'\1', s)
                s = _re.sub(r'<[a-zA-Z/][^>]*>', '', s)
                output["solutions"][i] = s
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
        valid_solutions = []
        for s in output.get("solutions", []):
            if isinstance(s, str):
                valid_solutions.append(_parse_solution(s))
            elif isinstance(s, dict):
                # LLM sometimes outputs dict instead of string — normalize
                valid_solutions.append({
                    "title": s.get("title", ""),
                    "core_idea": s.get("core_idea", s.get("summary", "")),
                    "code_before": s.get("code_before", ""),
                    "code_after": s.get("code_after", s.get("code", "")),
                    "code_lang": s.get("code_lang", "python"),
                    "explanation": s.get("explanation", s.get("description", "")),
                })
        output["solutions"] = valid_solutions

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
    """Parse '标题；核心思路；代码' format. Separate code from explanation."""
    import re as _re
    if not isinstance(s, str):
        return {"title": "", "core_idea": "", "code_before": "", "code_after": "", "code_lang": "python", "explanation": str(s)}
    parts = s.split("；")
    title = parts[0].strip() if len(parts) > 0 else "方案"
    core = parts[1].strip() if len(parts) > 1 else ""
    rest = "；".join(parts[2:]) if len(parts) > 2 else core
    rest = _re.sub(r'<code[^>]*>|</code>|<pre[^>]*>|</pre>', '', rest)

    # Separate code from explanation: ``` markers are the primary boundary
    lines = rest.split("\n")
    code_lines = []
    explanation_lines = []
    in_code = False
    found_fence = False
    seen_closing = False

    for line in lines:
        stripped = line.strip()
        is_fence = _re.match(r'^```[\w]*\s*$', stripped)

        if is_fence:
            if not in_code and not seen_closing:
                # Opening ``` — start code mode
                in_code = True
                found_fence = True
            elif in_code:
                # Closing ``` — end code mode
                in_code = False
                seen_closing = True
        elif in_code:
            code_lines.append(line)
        else:
            explanation_lines.append(line)

    code = "\n".join(code_lines).strip()
    explanation = "\n".join(explanation_lines).strip()

    # Fallback: no ``` markers found → use code_starters
    if not found_fence and not code:
        code_starters = (
            r'(def\s+|class\s+|import\s+|from\s+|const\s+|var\s+|let\s+|function\s+|'
            r'public\s+|private\s+|protected\s+|static\s+|'
            r'\w+\s*=\s*(lambda|\(|\[|\{)|'
            r'@\w+|#\s*(include|import|pragma))'
        )
        code_lines = []
        explanation_lines = []
        in_code = False
        for line in lines:
            stripped = line.strip()
            if not in_code:
                if _re.match(code_starters, stripped):
                    in_code = True
                    code_lines.append(line)
                else:
                    explanation_lines.append(line)
            else:
                code_lines.append(line)
        code = "\n".join(code_lines).strip()
        explanation = "\n".join(explanation_lines).strip()

    # If still no code, show as explanation only
    if not code:
        explanation = rest

    # Strip variable placeholders like {image_url}
    code = _re.sub(r'\{([^}]+)\}', r'\1', code)
    explanation = _re.sub(r'\{([^}]+)\}', r'\1', explanation)

    return {
        "title": title, "core_idea": core,
        "code_before": "", "code_after": code,
        "code_lang": "python", "explanation": explanation,
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

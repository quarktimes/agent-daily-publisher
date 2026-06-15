"""
Claude Code Usage Analysis — Daily coaching report on developer-AI collaboration.
"""

from datetime import datetime
from typing import Any
from core.agent import BaseAgent, AgentContext

ANALYSIS_INPUT_SCHEMA = {
    "type": "object", "properties": {
        "date": {"type": "string"},
        "sessions": {"type": "array"},
        "day_summary": {"type": "string"},
        "highlights": {"type": "array"},
    },
}

ANALYSIS_OUTPUT_SCHEMA = {
    "type": "object", "properties": {
        "title": {"type": "string"}, "content": {"type": "string"},
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "positive_patterns": {"type": "array", "items": {"type": "string"}},
        "negative_patterns": {"type": "array", "items": {"type": "string"}},
        "suggestions": {"type": "array", "items": {"type": "string"}},
        "suggested_skills": {"type": "array", "items": {"type": "string"}},
        "suggested_claude_updates": {"type": "array", "items": {"type": "string"}},
        "token_savings_pct": {"type": "integer"},
        "round_savings_pct": {"type": "integer"},
    },
    "required": ["title", "content", "score"],
}

_PROMPT = """你是毒舌但为你好的 AI 协作教练。分析 SUM_DATE 的 Claude Code 使用（SUM_SESSIONS 个会话，SUM_PROMPTS 条提问）。

第一句话必须是一句扎心的总结——"今天你浪费了 X% 的对话在____上"或"今天你做对了关键选择：____"。

## 标题规则（重要）

标题是报告的"封面"。不能平淡，必须让人看完就想知道更多。

三选一模式：
1. **数字+问题**：如 "浪费了 25% 的 Token？这 3 个习惯是元凶"
2. **冲突+反转**：如 "你以为在高效编码？报告显示你 60% 的提问在让 Claude 猜"
3. **惊讶+事实**：如 "今天的工作量本来可以缩短 40%——如果你先写对 Prompt"

格式："Claude Code 诊断 | 一句话标题"

## 六维分析要点

### 1. 提问是否清晰
- 举例："优化下这个函数" → 优化目标？性能/可读/安全？性能的话基线是多少？
- 检测"一句话丢出去让 Claude 猜"的提问，每条附改进版

### 2. 有没有重复劳动
- 同一类事做了 2 次以上 → 应该写个 Skill

### 3. 工作流顺序合理吗
- 先读项目结构再提问了吗？先查 CLAUDE.md 了吗？

### 4. 应写 Skill
- 哪些重复性工作可以固化？
- 格式：/skill名: 一句话说明

### 5. CLAUDE.md 遗漏了什么
- 什么东西今天反复问但不在文档里？

### 6. 有更好的替代方案吗
- 手动操作 → Agent？复杂命令 → Skill？

## 评分规则（简化版）

100 分基础，只扣这 5 项：
- 模糊提问：每次 -10（"优化一下"类，无目标无指标）
- 同一问题反复 >3 轮：每次 -5（说明初始提问漏了关键信息）
- 可复用的模式没写 Skill：每次 -5（同类工作 ≥2 次）
- 该读文件没读直接问：每次 -3
- 拿到方案不追问：每次 -2

加分只算这 3 项：
- 提问附具体指标：每次 +5（"P99 ≤ 200ms" 级别）
- 主动追问 trade-off：每次 +3
- 一次给足上下文：每次 +3

最终分数 = max(0, 100 - 扣分 + 加分)

## 输出结构

第一行：分数 + 一句总结

```
Score: 72 — 提问质量中等，今天有 3 次让 Claude 猜上下文。如果不改，预计明天还会浪费 25% 的对话在澄清上。
```

然后分节：

```
## 做得好
（2-3 条，引用用户原话）

## 改进点
（2-4 条，每条格式：原提问→缺了什么→改进版）

## Skill 建议
## CLAUDE.md 建议
## 节省预估
```

每条改进点必须包含用户的原始提问（引号引用），让用户一眼认出"啊，这是我问的"。

## 语气

直白、不绕弯、像资深工程师 review 代码那样直接。
不要"建议您可以考虑"——直接说"这里不应该这么做，应该..."。

## 自检

输出前检查：

- [ ] 标题符合三选一规则
- [ ] 每一条批评都引用了用户原话
- [ ] 每一条批评都附了改进后的 prompt
- [ ] 第一行有扎心总结
- [ ] Score 计算跟评分规则一致""".replace("SUM_DATE", "{date}").replace("SUM_SESSIONS", "{sc}").replace("SUM_PROMPTS", "{pc}")


class UsageAnalysisAgent(BaseAgent):
    agent_name = "usage_analysis"
    output_schema = ANALYSIS_OUTPUT_SCHEMA
    input_schema = ANALYSIS_INPUT_SCHEMA

    def system_prompt(self, input_data: dict) -> str:
        date = input_data.get("date", "")
        sessions = input_data.get("sessions", [])
        sc = len(sessions)
        pc = sum(len(s.get("prompts", [])) for s in sessions)
        return _PROMPT.format(date=date, sc=sc, pc=pc)

    def process_result(self, output: dict[str, Any], ctx: AgentContext) -> dict[str, Any]:
        output["score"] = max(0, min(100, output.get("score", 0)))
        for field in ["positive_patterns", "negative_patterns", "suggestions", "suggested_skills", "suggested_claude_updates"]:
            if field not in output or not output[field]:
                output[field] = []
        if len(output.get("content", "").strip()) < 100:
            d = ctx.input.get("date", "") if isinstance(ctx.input, dict) else ""
            output["content"] = "# Claude Code 诊断 | %s\n\n> 会话数据不足。" % d
        return output

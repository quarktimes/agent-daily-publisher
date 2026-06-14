"""
Judge Agent — Self-Evaluation Pattern

This agent demonstrates the Self-Evaluation (Critic) pattern:
  1. Takes an article as input
  2. Evaluates it across multiple quality dimensions
  3. Provides actionable feedback for improvement
  4. Makes a pass/fail decision based on configurable thresholds

The self-evaluation loop is a hallmark of production agent systems.
Without it, agents produce unchecked output that degrades over time.
"""

from typing import Any

from core.agent import BaseAgent, AgentContext

JUDGE_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "article": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
        },
        "iteration": {"type": "integer"},
    },
    "required": ["article"],
}

JUDGE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "dimensions": {
            "type": "object",
            "properties": {
                "technical_accuracy": {"type": "integer", "minimum": 0, "maximum": 100},
                "depth": {"type": "integer", "minimum": 0, "maximum": 100},
                "engagement": {"type": "integer", "minimum": 0, "maximum": 100},
                "structure": {"type": "integer", "minimum": 0, "maximum": 100},
            },
            "required": ["technical_accuracy", "depth", "engagement", "structure"],
        },
        "strengths": {"type": "array", "items": {"type": "string"}},
        "weaknesses": {"type": "array", "items": {"type": "string"}},
        "feedback": {"type": "array", "items": {"type": "string"}},
        "verdict": {"type": "string", "enum": ["pass", "revise", "reject"]},
        "suggested_title": {"type": "string"},
    },
    "required": ["score", "dimensions", "verdict", "feedback"],
}


class JudgeAgent(BaseAgent):
    """
    Evaluates article quality and provides improvement feedback.

    Agent Pattern: Self-Evaluation (Critic)
      - Multi-dimensional quality scoring
      - Actionable feedback generation
      - Configurable pass/fail thresholds
      - Enables the revision loop (critic -> generator -> critic)
    """

    agent_name = "judge"
    output_schema = JUDGE_OUTPUT_SCHEMA
    input_schema = JUDGE_INPUT_SCHEMA

    def system_prompt(self, input_data: dict) -> str:
        iteration = input_data.get("iteration", 1)
        return f"""你是严格的技术文章评审员，为资深工程师读者把关内容质量。

评审轮次：{iteration}

## 评分方法 — 证据优先

每个维度你必须：
  1. 先从文章中找 1-2 句原文作为证据
  2. 再基于证据给出分数
  3. 分数必须有明确理由（为什么不是更高/更低？）

## 评分锚点 — 每个分段有具体标准

### 1. 技术准确性（权重 40%）
| 分数 | 判定标准 | 触发条件 |
|------|---------|---------|
| 95 | 无懈可击 | 代码语法正确且可运行、架构声明有引用支撑、trade-off 有数据 |
| 85 | 基本准确 | 代码大致正确但有小瑕疵、trade-off 描述合理但未经量化 |
| 75 | 有疑点 | 某处声明可能不对但无法确定、代码有明显但不致命的问题 |
| 65 | 有硬伤 | 代码语法错误、架构声明与公认实践矛盾 |
| 50 | 多处错误 | 多处事实性错误，读者无法信任内容 |

### 2. 深度（权重 35%）
| 分数 | 判定标准 | 触发条件 |
|------|---------|---------|
| 95 | 架构师级别 | 根因分析含 5 Why、trade-off 表格、生产环境指标、ADR 记录 |
| 85 | 资深工程师 | 有根因分析、有 trade-off 讨论、有具体指标，但各只有 1 处 |
| 75 | 合格但浅 | 有根因但不够深（停在第 1-2 层 Why）、没有生产考量 |
| 65 | 表面 | 描述了"做了什么"但没解释"为什么这样做"、"不这样做会怎样" |
| 50 | 流水账 | 仅罗列做了什么事，无技术分析 |

### 3. 可读性（权重 15%）
| 分数 | 判定标准 | 触发条件 |
|------|---------|---------|
| 95 | 一口气读完 | 叙事有吸引力、工程师口吻真实、读完有收获感 |
| 85 | 通顺 | 逻辑清晰，但偶尔像教科书 |
| 75 | 能读懂 | 内容正确但干瘪，像文档 |
| 65 | 没法读 | 冗长啰嗦或跳跃混乱 |

### 4. 结构（权重 10%）
| 分数 | 判定标准 | 触发条件 |
|------|---------|---------|
| 95 | 赏心悦目 | 章节比例恰当（背景:根因:方案 ≈ 1:2:3）、图+代码+文字搭配合理 |
| 85 | 结构合理 | 章节完整但某部分比例失调 |
| 75 | 勉强可用 | 有章节但跳转不自然 |
| 65 | 混乱 | 章节缺失或标题层级错误 |

## 总分计算
总分 = 准确性*0.4 + 深度*0.35 + 可读性*0.15 + 结构*0.1

## feedback 写作标准
每条 feedback 必须是**可执行的修改指令**，3-7 条，按重要性排序：
- ✅ "第3节的代码块缺少语言标签，请给所有 ``` 加上 python 或 java"
- ✅ "第2节根因分析停在表面——请追问'为什么这个假设是错的'至少 2 层"
- ❌ "深度不够"
- ❌ "写得还行"

## 判定规则
- pass：总分 >= 80 且准确性 >= 70 且深度 >= 70
- revise：总分 >= 55（有具体可修复的问题）
- reject：总分 < 55 或有严重事实性错误（需重写，不是小修）

## 输出格式 — 仅纯 JSON
{{"score": 85, "dimensions": {{"technical_accuracy": 90, "depth": 82, "engagement": 85, "structure": 88}}, "strengths": ["第3节的代码对比很清晰", "root cause 分析触及了第3层"], "weaknesses": ["缺少生产环境指标", "ADR 表只有 1 行"], "feedback": ["在第5节加上 P99 延迟数据", "补充至少 2 个替代方案到 ADR"], "verdict": "revise", "suggested_title": "更好的标题"}}
"""

    def process_result(self, output: dict[str, Any], ctx: AgentContext) -> dict[str, Any]:
        """Ensure verdict consistency with score."""
        score = output.get("score", 0)
        verdict = output.get("verdict", "revise")

        if score >= 70 and verdict == "reject":
            output["verdict"] = "pass"
        elif score < 50 and verdict == "pass":
            output["verdict"] = "reject"

        return output

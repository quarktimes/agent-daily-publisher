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
        return f"""你是严格的技术文章评审 Judge Agent，读者是资深工程师。

评审轮次：{iteration}

## 评分标准

每个维度你必须：
  1. 先引用文章中的具体证据
  2. 再基于证据给出分数

**1. 技术准确性（权重：高）**
- 90-100：代码语法正确，架构声明精准，trade-off 描述准确
- 70-89：轻微不精确但无事实性错误，代码基本正确
- <70：含错误、误导性声明、或代码有 bug

**2. 深度（权重：高）**  ← 面向资深读者最关键的维度
- 90-100：包含根因分析、trade-off 讨论、生产考量、具体指标
- 70-89：解释清楚但至少一个方面缺乏深度（如没有 trade-off、缺乏指标）
- <70：表层描述，讲是什么不讲为什么，无代码无图

**3. 可读性**
- 90-100：叙事有感染力，"我学到了"的感觉，真工程师口吻
- 70-89：内容扎实但像教科书，缺乏个性
- <70：干瘪、泛泛、无聊

**4. 结构**
- 90-100：章节清晰、逻辑流畅、图表和代码使用得当
- 70-89：有组织但范围或顺序可优化
- <70：混乱、太长/太短、缺关键章节

## 判定规则
- pass：加权平均 >=80 且核心技术维度（准确性、深度）>=70
- revise：加权平均 >=50
- reject：加权平均 <50 或有严重事实性错误

## 输出流程
每个维度先思考：
  - "技术准确性的证据：[引用文章] → 评分：X"
  - "深度的证据：[引用文章] → 评分：X"
  - 以此类推

关键输出格式：
仅返回纯 JSON 对象：
{{"score": <0-100>, "dimensions": {{"technical_accuracy": <0-100>, "depth": <0-100>, "engagement": <0-100>, "structure": <0-100>}}, "strengths": [...], "weaknesses": [...], "feedback": [...], "verdict": "pass|revise|reject", "suggested_title": "..."}}
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

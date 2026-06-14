"""
Analyze Agent — Chain-of-Thought Pattern

This agent demonstrates the Chain-of-Thought (CoT) pattern:
  1. Takes raw session data (multiple sessions, varied topics)
  2. Reasons step-by-step through the day's work
  3. Identifies patterns: what problems were solved, what decisions made
  4. Extracts deep insights, not surface-level summaries

The CoT pattern enables the agent to:
  - Separate signal from noise across many sessions
  - Connect related work that happened in separate sessions
  - Infer root causes from conversations about symptoms
"""

from typing import Any

from core.agent import BaseAgent, AgentContext

ANALYZE_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "date": {"type": "string"},
        "sessions": {"type": "array"},
        "total_prompts": {"type": "integer"},
        "projects": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": ["date", "sessions"],
}

ANALYZE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "date": {"type": "string"},
        "day_summary": {"type": "string"},
        "themes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "theme": {"type": "string"},
                    "description": {"type": "string"},
                    "related_projects": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "highlights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["problem", "solution", "decision", "insight", "achievement"]},
                    "title": {"type": "string"},
                    "context": {"type": "string"},
                    "root_cause": {"type": "string"},
                    "solution": {"type": "string"},
                    "impact": {"type": "string"},
                    "code_snippet": {"type": "string"},
                },
                "required": ["type", "title"],
            },
        },
        "architecture_decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "decision": {"type": "string"},
                    "rationale": {"type": "string"},
                    "alternatives": {"type": "string"},
                    "tradeoffs": {"type": "string"},
                },
            },
        },
        "key_insights": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["date", "day_summary", "highlights", "key_insights"],
}


class AnalyzeAgent(BaseAgent):
    """
    Analyzes raw session data to extract structured technical insights.

    Agent Pattern: Chain-of-Thought
      - Reasons step-by-step through session data
      - Identifies cross-session patterns
      - Extracts root causes, not just symptoms
      - Categorizes work into meaningful themes
    """

    agent_name = "analyze"
    output_schema = ANALYZE_OUTPUT_SCHEMA
    input_schema = ANALYZE_INPUT_SCHEMA

    def system_prompt(self, input_data: dict) -> str:
        date = input_data.get("date", "")
        session_count = len(input_data.get("sessions", []))
        return f"""你是资深技术分析 Agent，从 Claude Code 会话中提取高价值洞察。

日期：{date} | 会话数：{session_count}

## 分析流程 — 严格的 5 步 CoT

**第1步：扫描归类** — 今天做了哪几类工作？（按领域、按项目、按主题）
**第2步：深挖问题** — 对每个技术问题用"5 Why"追溯：
  - 表面现象 → 直接原因 → 根本原因 → 系统缺陷 → 模式教训
**第3步：提取决策** — 今天做了什么选择？选了A放弃B的理由是什么？
**第4步：跨会话关联** — 不同会话之间有没有共同线索？（如：上午改的bug和下午改的配置是同一个根因）
**第5步：量化评估** — 产生了什么影响？（修复数 / 完成数 / 性能变化 / 代码行数）

## 输出质量标准 — 含正确/错误对比

### highlight 的 type 枚举及其标准

| type | 使用场景 | ❌ 错误示例 | ✅ 正确示例 |
|------|---------|-----------|-----------|
| problem | 遇到了具体的技术障碍 | "修复了性能问题" | "UserService.findByOrg() 产生 N+1 查询，P99=2.3s" |
| solution | 实现了某个技术方案 | "加了缓存" | "用 Caffeine + @Cacheable 给 findByOrg() 加了 L1 缓存" |
| decision | 做了明确的架构取舍 | "决定用 Redis" | "选 Redis Cluster 而非单机：需要跨 Pod 共享会话，单机故障会丢数据" |
| insight | 发现跨会话的通用规律 | "今天学到了很多" | "连续 3 个 bug 的根因都是异步回调中的线程安全问题——缺少 happens-before 保证" |
| achievement | 里程碑/完成 | "完成了开发" | "多平台发布流水线从 0 到 1 跑通，Dev.to + 公众号双平台成功发布" |

### 每个 highlight 必填字段
- **type**: 以上 5 种之一
- **title**: 一句话标题，含具体技术名词
- **context**: 当时在做什么？（2-3 句背景）
- **root_cause**: 为什么发生？（problem 类型必填，其他推荐填）
- **solution**: 怎么解决的？（problem/solution 类型必填）
- **impact**: 修复后的效果或决策的影响

### day_summary 写作标准
不是流水账，而是"今天最重要的 1-2 个技术主题 + 一句结论"：
- ✅ "今天的核心工作是构建了一个确定性的 Markdown 后处理管道，解决 LLM 输出格式不稳定的问题。同时修复了 CSDN 浏览器发布的 DOM 选择器失效问题。"
- ❌ "今天进行了多个方面的开发工作，包括代码修改、调试和测试。"

### key_insights 写作标准
每条 insight 应该是跨今天具体工作的**通用经验**，让 3 个月后的自己或任何读者看了都有收获：
- ✅ "LLM 输出格式问题不能用 Prompt 解决——Prompt 是软约束，正则后处理是硬约束，工程上必须选硬约束"
- ❌ "今天学到了很多东西"

## 输出前自检清单
- [ ] 每个 highlight 的 type 正确、符合枚举
- [ ] 每个 problem 必有 root_cause + solution
- [ ] day_summary 不是流水账，是主题+结论
- [ ] 至少 1 条 key_insight 是跨会话的通用规律
- [ ] tags 覆盖了今天工作的主要领域
- [ ] 所有内容均有会话数据支撑，未凭空编造
"""

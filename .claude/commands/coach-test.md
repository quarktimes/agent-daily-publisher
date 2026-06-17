---
name: coach-test
description: 快速测试教练报告输出（不经过主 pipeline）
---

运行 Usage Analysis Agent 单独测试教练报告输出。

流程：
1. 读取 `data/traces/2026-06-17_agent_runs.jsonl` 中的 usage_analysis 运行记录
2. 读取 `data/pipeline_state/2026-06-17.json` 中的 capture 数据（sessions）
3. 直接实例化 UsageAnalysisAgent，传入 session 数据
4. 输出结果到 `data/usage/`

命令：

```bash
cd /Users/dehualiu/ai-developer-knowledge-hub
python3 << 'PYEOF'
import json, os, sys
sys.path.insert(0, '.')
from agents.usage_analysis_agent import UsageAnalysisAgent

# 读取会话数据
with open('data/pipeline_state/2026-06-17.json') as f:
    state = json.load(f)
capture = state.get('outputs', {}).get('capture', {})

# 跑 coach
from core.agent import BaseAgent
from core.observer import Observer
from anthropic import Anthropic
claude = Anthropic()
ua = UsageAnalysisAgent(observer=Observer(), claude_client=claude)
result = ua.run({
    'date': '2026-06-17',
    'sessions': capture.get('sessions', []),
    'day_summary': capture.get('summary', ''),
    'highlights': [],
})
print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
PYEOF
```

注意：
- 如果 pipeline_state 不存在，先跑一次完整 pipeline 生成它
- 如果 usage_analysis 报错，看 data/usage/ 下的输出文件和 data/traces/ 下的错误记录
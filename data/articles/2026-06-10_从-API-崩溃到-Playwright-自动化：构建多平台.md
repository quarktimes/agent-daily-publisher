## 📌 今日概述
今天完成了 AI Developer Knowledge Hub 多平台发布管道的端到端测试与部署。我们不仅实现了基于 Dev.to API 的自动发布，还针对 CSDN 和微信公众号等缺乏 API 或 API 不可用的平台，使用 Playwright 构建了浏览器自动化方案。此外，修复了历史记录读取逻辑以适应 Claude Code 新的文件存储结构，并重新补齐了前两天的发布进度，同时强化了环境变量与敏感信息的安全管理。

## 🔧 问题和方案

### 1. CSDN API 不可用导致的发布阻断

**背景**
在构建多平台分发系统时，CSDN 是国内开发者社区的重要阵地。原计划调用 CSDN 开放平台的 API 进行文章自动发布，但在实际联调中发现请求持续失败，服务完全不可达。

**根因分析**
经过排查，确认并非网络或鉴权问题，而是 CSDN 开放平台本身的服务中断或接口已被废弃。这揭示了一个在第三方集成中经常被忽视的风险：对单一 API 的强依赖会导致整个业务流程在外部服务不可用时直接瘫痪。平台 API 的生命周期往往短于我们的业务预期，且通常缺乏事前通知。

**方案**
既然“后门”（API）走不通，我们决定走“正门”，使用 Playwright 模拟真实用户操作。我们实现了一个基于浏览器自动化的 Publisher 类，绕过 API 直接操作 DOM。

```typescript
// 使用 Playwright 模拟 CSDN 登录与发布
const browser = await playwright.chromium.launch({ headless: false });
const page = await browser.newPage();
await page.goto('https://mp.csdn.net/mp_blog/creation/editor');

// 填充表单
await page.fill('#title', articleTitle);
await page.fill('.cke_contents', articleContent);

// 点击发布按钮
await page.click('.btn-publish');
```

**效果**
成功绕过了 API 故障，恢复了 CSDN 的发布能力。虽然速度比原生 API 慢，且对 UI 变动较敏感，但保证了核心业务流程的连续性。

### 2. Claude Code 历史记录读取为空

**背景**
我们的工作流依赖于读取 Claude Code 的本地历史记录来自动生成日报和文章。但在最近几天，读取模块突然返回空结果，明明每天都有对话记录，却无法抓取到任何数据。

**根因分析**
经过对 `~/.claude/` 目录的深入检查，发现 Claude Code 更新了其数据存储策略。它不再将所有历史记录集中存储在单一的 `history.jsonl` 文件中，而是改为按项目分割，每个项目拥有独立的 `history.jsonl` 文件（路径格式为 `~/.claude/<project-id>/history.jsonl`）。原有的代码逻辑仅扫描单一文件，导致无法读取新格式下的数据。

**方案**
升级了 History Reader，增加了递归扫描和聚合逻辑：

```typescript
import fs from 'fs';
import path from 'path';

const claudeBaseDir = path.join(os.homedir(), '.claude');

function getAllHistoryFiles(): string[] {
  const projects = fs.readdirSync(claudeBaseDir);
  return projects
    .map(p => path.join(claudeBaseDir, p, 'history.jsonl'))
    .filter(p => fs.existsSync(p));
}

async function readAllHistory() {
  const files = getAllHistoryFiles();
  const allEntries = [];
  for (const file of files) {
    const content = await fs.readFile(file, 'utf-8');
    allEntries.push(...content.split('\n').filter(Boolean).map(JSON.parse));
  }
  return allEntries.sort((a, b) => b.createdAt - a.createdAt);
}
```

**效果**
恢复了历史记录读取能力，成功聚合了所有项目的对话数据，重新支撑起了内容自动生成的数据源。

### 3. 微信公众号无 API 的发布难题

**背景**
微信公众号是极其重要的分发渠道，但官方并未提供公开的文章发布 API，仅提供了“素材管理”等受限接口，无法满足自动排版并发布图文的需求。

**根因分析**
出于内容生态的封闭性管控，微信并未开放此类自动化接口。如果仅依赖官方能力，自动化发布将成为不可能完成的任务。

**方案**
复用了针对 CSDN 的 Playwright 方案。通过自动化脚本登录微信公众平台，定位到新建图文的编辑器 DOM，注入 Markdown 渲染后的 HTML，并触发发布流程。尽管这与 CSDN 的实现细节不同，但“浏览器自动化”这一架构模式完全复用。

**效果**
成功将微信公众号纳入统一发布管道，实现了真正的多平台覆盖。

### 4. Dev.to API 环境变量持久化

**背景**
在测试 Dev.to 发布时，每次重启终端后都需要重新 `export DEVTO_API_KEY`，非常繁琐且容易导致 CI/CD 流程失败。

**根因分析**
之前的配置仅作用于当前 Shell 会话，未写入 shell 配置文件，导致变量生命周期随会话结束而销毁。

**方案**
将 API Key 直接写入 `.zshrc`，确保永久生效：

```bash
echo 'export DEVTO_API_KEY="your_api_key_here"' >> ~/.zshrc
source ~/.zshrc
```

**效果**
实现了跨会话的认证持久化，为后续的自动化脚本和 CI 集成扫清了障碍。

## 🏗 架构决策

### 决策一：采用 Playwright 混合模式应对无 API 平台

**决策内容**
对于像 Dev.to 这样提供完善 API 的平台，直接调用 RESTful 接口；对于 CSDN、微信公众号等无 API 或 API 不可用的平台，统一采用 Playwright 浏览器自动化方案。

**被否决的替代方案**
1. **放弃无 API 平台**：虽然最省事，但会损失巨大的流量入口，特别是 CSDN 这种国内社区。
2. **开发官方 SDK**：对于没有官方 API 的平台，无法实现。
3. **使用第三方爬虫服务**：不可控且存在法律风险，不如本地 Playwright 灵活。

**胜出理由**
Playwright 提供了在 Node.js 环境中控制浏览器的标准化能力，虽然比 API 慢且维护成本较高（UI 改动会导致脚本失效），但它打破了平台封闭性的限制。在“不可用”和“难维护”之间，我们选择了后者，因为它不仅可行，而且能覆盖关键渠道。

### 决策二：发布管道支持 API 与 Browser 两种模式

**决策内容**
在设计 Publisher 接口时，不强制要求底层实现，抽象层支持 `execute(publisher: Publisher)`，具体实现可以是 `ApiPublisher` 也可以是 `BrowserPublisher`。

**被否决的替代方案**
针对不同平台写两套完全独立的脚本（如 `publish_to_devto.sh` 和 `publish_to_csdn.js`），互不干扰。

**胜出理由**
统一接口意味着我们可以使用统一的调度逻辑、统一的错误处理和统一的日志监控。即使底层技术栈不同，上层业务逻辑（如“获取文章 -> 渲染 -> 发布 -> 记录日志”）保持一致，极大降低了系统的认知负荷和维护成本。

### 决策三：使用 .gitignore 严格管控敏感信息

**决策内容**
在代码仓库中显式配置 `.gitignore`，排除 `*.key`、`.env` 以及任何包含 `appkey`、`secret` 字样的配置文件。

**被否决的替代方案**
依赖开发者手动检查提交内容，或者使用 pre-commit hook 进行拦截。

**胜出理由**
防御性编程的最佳实践。依赖人为记忆总会出错（谁都有手滑的时候），而 `.gitignore` 是版本控制层面的硬性阻断。考虑到我们项目涉及到多个平台的 API Key，一旦泄露后果严重，这种“零信任”的配置是必须的。

## 💡 关键收获

1.  **API 依赖是脆弱的**
    CSDN 的案例是一个警钟：所有外部 API 都可能变成“单点故障”。在设计系统时，必须考虑降级方案。如果业务至关重要，甚至是 B 计划（如浏览器自动化、逆向工程）也需要准备好。永远不要假设第三方服务永远在线且接口不变。

2.  **数据格式是流动的**
    工具（如 Claude Code）会更新，数据结构会变。在编写读取逻辑时，应尽量避免硬编码文件路径或结构。更好的做法是支持“模式匹配”或“多版本兼容”。例如，未来的 History Reader 也许可以自动识别是单文件模式还是多项目模式，而不需要人工介入修改代码。

3.  **混合架构是现实世界的最优解**
    在理论中，我们希望所有系统都通过干净的 REST API 通信。但在现实工程中，我们经常面临遗留系统、封闭平台或不稳定的服务。一个健壮的架构应该具备“异构包容性”：能用 API 就用 API，不能用就用 RPA（机器人流程自动化）。不要为了架构的纯粹性而牺牲业务的可行性。

4.  **环境管理的细节决定成败**
    很多时候自动化流程跑不通，不是代码逻辑错了，而是环境变量丢了、配置文件没挂载。将敏感信息通过 `.zshrc` 或 `.env` 进行持久化管理，并通过 `.gitignore` 进行保护，是 DevOps 环节中最基础但也最重要的一环。

今天的经历再次证明，构建自动化系统不仅是写代码，更是与外部环境（平台服务、文件系统、安全策略）不断博弈和适配的过程。
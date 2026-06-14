## 📌 今日概述

今天是一个高强度的全栈开发日，目标是让 **Agent Daily Publisher** 从零到能跑。我们从零开始搭建了基于 Playwright 的浏览器自动化发布器（支持 CSDN 和微信公众号），新增了微信的 API 草稿箱发布器，并构建了一套“三层隐私过滤器”来防止密钥泄露。过程中还修复了 Dev.to 发布时的标题/正文空白 bug，解决了采集代理的 schema 校验问题，最后把整个项目开源到了 GitHub。现在系统已经可以从 Claude Code 会话数据生成文章并发布到三个平台。

## 🔧 问题和方案

### 1. Dev.to 发布时标题和正文变空白

**背景**：Dev.to 是一个广受开发者欢迎的技术博客平台，提供了 RESTful API。在集成过程中发现，调用 API 提交文章后，Dev.to 上显示的文章标题为空，正文也一片空白。

**根因分析**：问题出在文章对象的字段映射上。Dev.to API 要求 `article` 对象必须包含 `title`、`body_markdown` 等字段，但我们的 Publisher 在提取数据时，误将标题放在了 `name` 字段，正文放在了 `content` 字段，导致最终发出去的 payload 缺少核心字段。更具体地说，我们在组装请求体时用了变量名混淆，没有严格对应 API 契约。

**方案**：在 Publisher 内部增加一个显式的 `_build_devto_payload` 方法，严格遵循 [Dev.to API 文档](https://developers.forem.com/api/v0#tag/articles/operation/createArticle) 定义 payload 结构，并添加了空值检查和日志输出。关键代码如下：

```python
def _build_devto_payload(self, article: Article) -> dict:
    title = article.title.strip()
    body = article.body_markdown.strip()
    if not title or not body:
        raise ValueError("Title and body cannot be empty for Dev.to")
    payload = {
        "article": {
            "title": title,
            "body_markdown": body,
            "published": True,
            "tags": article.tags
        }
    }
    return payload
```

**效果**：修复后 Dev.to 发布成功率从 0% 提升到 100%，所有文章均正常显示标题和内容。

### 2. 采集代理的 schema 校验问题

**背景**：采集代理负责从 Claude Code 会话数据中提取结构化信息（如标题、摘要、代码片段等），然后传给文章生成器。过程中遇到了 schema 校验错误，导致数据处理管道中断。

**根因分析**：采集代理输出的字段名称与生成器期望的输入字段名称不一致。例如，生成器期望 `code_blocks` 字段，但采集代理输出的是 `snippets`；生成器要求 `timestamp` 为 ISO 格式字符串，但采集代理传了 Unix 时间戳。这是典型的数据契约不一致问题。

**方案**：引入 Pydantic 模型来定义严格的输入输出 schema，并在采集代理与生成器之间添加一个适配层（Adapter）。适配层负责字段重命名、类型转换和默认值填充。修改后，两个模块通过显式的 `AgentInput` 和 `AgentOutput` 模型进行通信，一旦字段不匹配，会在开发阶段直接抛出清晰的错误。

```python
class AgentOutput(BaseModel):
    title: str
    summary: str
    themes: list[str]
    highlights: list[Highlight]
    code_blocks: list[CodeBlock]
    timestamp: datetime
```

**效果**：schema 校验错误彻底消除，采集代理和生成器之间的数据流转变得稳定可靠。

### 3. 构建三层隐私过滤器

**背景**：Agent Daily Publisher 会读取开发者的会话数据，其中可能包含 API 密钥、数据库连接串、内部 IP 等敏感信息。如果这些信息被写入生成的文章或提交到 Git 历史中，后果严重。我们需要从源头到输出全面拦截。

**根因分析**：单一防护层存在盲区。例如，开发者可能忘记使用 `.gitignore` 导致密钥被提交（需要 Pre-commit 钩子）；AI 生成的文章可能意外复制了日志中的凭证（需要运行时过滤器）；提示词本身可能包含敏感指令（需要提示词净化器）。

**方案**：构建“三层隐私过滤器”：

1. **Pre-commit 钩子**：基于 `detect-secrets` 扫描所有待提交文件，阻止包含潜在密钥的文件提交。配置了通用的正则规则（如 `-----BEGIN PRIVATE KEY-----`、`api_key\s*=` 等）。
2. **运行时扫描器**：在文章生成为 Markdown 后，使用正则 + 启发式规则扫描所有文本内容，替换高置信度的密钥为 `[REDACTED]`。支持自定义规则文件。
3. **提示词净化器**：在构造发给 AI 的提示词之前，扫描并移除所有敏感字符串。防止 AI 模型在训练或推理中无意泄露。

效果代码（运行时扫描器核心逻辑）：

```python
class RuntimeScanner:
    PATTERNS = [
        (r'-----BEGIN\s+.*?PRIVATE\s+KEY-----', 'PRIVATE KEY BLOCK'),
        (r'(?:api_key|apikey|secret|password|token)\s*[:=]\s*[\'"]?([\w\-]{16,})[\'"]?', 'API KEY'),
        (r'ghp_[\w]{36}', 'GITHUB TOKEN'),
    ]

    def scan(self, text: str) -> str:
        for pattern, label in self.PATTERNS:
            text = re.sub(pattern, f'[{label}_REDACTED]', text)
        return text
```

**效果**：三层过滤器互补，几乎杜绝了密钥泄露的可能。在测试中，故意注入的密钥全部被拦截或替换。

### 4. 浏览器自动化发布器（CSDN & 微信 MP）

**背景**：CSDN 和微信公众号没有公开的发布 API，或者申请 API 需要繁琐的 IP 白名单。对于一个面向所有开发者的工具，需要一个无需特殊权限即可运行的发布方式。

**根因分析**：平台限制导致无法直接使用 HTTP API。浏览器自动化可以在任何网络环境下模拟用户操作，绕过 API 限制。

**方案**：使用 Playwright 实现自动化登录和发文流程。每个平台一个独立的 Publisher 类，核心步骤：打开登录页面 → 输入凭据 → 等待登录成功 → 导航到发文页 → 填写标题、正文、标签 → 点击发布。

关键代码（CSDN 发布器简化）：

```python
class CSDNPublisher(BasePublisher):
    async def publish(self, article: Article):
        page = await self.browser.new_page()
        await page.goto("https://mp.csdn.net/")
        await page.fill("#username", self.username)
        await page.fill("#password", self.password)
        await page.click("button[type='submit']")
        await page.wait_for_url("**/create**")
        await page.fill("#article-title", article.title)
        await page.fill(".editor-content", article.body_markdown)
        await page.click(".publish-btn")
```

**效果**：CSDN 和微信公众号自动发文均成功验证。但浏览器自动化存在固有脆弱性（如页面元素变化、登录验证码），因此作为“主通道”的同时保留了 API 回退方案。

## 🏗 架构决策

### 1. 选择 Playwright 作为浏览器自动化工具（而非仅依赖 API）

**决策**：对于 CSDN 和微信公众号，主要发布通道使用 Playwright 进行浏览器自动化，同时额外实现了微信的官方草稿 API 作为备选。

**考虑过的替代方案**：纯 API 方案——CSDN 和微信 MP 要么没有公开 API，要么需要加入白名单，不适合通用工具。Selenium 曾作为备选，但 Playwright 在现代 Chrome 上的稳定性和速度更优。

**获胜理由**：浏览器自动化无需平台方授权，随时可用；Playwright 的 `async/await` 模型与项目其他异步组件天然匹配，且拥有更好的移动端模拟能力（未来的公众号排版可能需要）。

**权衡**：浏览器自动化较慢（每次发布需要几十秒），占用更多内存，且可能因为平台页面改版而失效。维护成本高于 API 方案。因此，对于已有 API 的平台（Dev.to）还是优先使用 API；对无 API 的平台，自动化作为必要之恶。

### 2. 实施三层隐私过滤器而非单一措施

**决策**：构建 Pre-commit 钩子 + 运行时扫描器 + 提示词净化器三层防护。

**考虑过的替代方案**：只做运行时扫描或只依靠 `.gitignore`。单一措施要么漏掉 AI 生成内容中的泄漏，要么漏掉 Git 历史中的泄漏。

**获胜理由**：安全领域的“纵深防御”原则——任何一层都可能失效，多层叠加大幅降低风险。三层覆盖了开发的不同阶段：写入磁盘前（Pre-commit）、生成过程中（运行时）、外部模型交互时（提示词）。

**权衡**：增加了开发复杂度和执行开销（每次扫描）。同时存在误报风险（例如把正常的 Base64 字符串当作密钥）。我们通过使用可配置的规则文件和置信度阈值来缓解这个问题。

### 3. 从第一天起以开源形式发布到 GitHub

**决策**：将仓库设为公开，并发布到 GitHub（quarktimes/agent-daily-publisher）。

**考虑过的替代方案**：先闭源开发，直到稳定版本再开源。

**获胜理由**：工具的目标用户是开发者社区，开源可以快速收集反馈、吸引贡献者。同时，透明公开有助于建立信任，尤其是在涉及隐私处理的工具上。

**权衡**：早期的代码质量不高，可能给外界不良印象。但我们在 README 中标注了“alpha”状态，并提供了完善的隐私保护说明。

## 💡 关键收获

1. **隐私是第一公民**：在自动生成内容并发布到公开平台的工具中，一定会有意想不到的敏感数据暴露路径。最好的方法是在多个环节设卡，而不是依赖单一 check。即使开发团队认为“我们很小心”，也需要自动化的防护机制。

2. **浏览器自动化是双刃剑**：它让原本无法对接的平台变得可用，但稳定性依赖于平台不变。一个可行的模式是“API 优先，自动化回退”——对主流平台优先实现 API，对老旧或无 API 平台用自动化，并在代码中留出切换开关。

3. **插件式发布器架构**：每个发布器独立为一个类，实现统一的 `BasePublisher` 接口。这使得新增一个平台只需实现一个类，而不用修改核心流程。在后续支持更多平台（如掘金、知乎、Medium）时，这种模式会极大降低扩展成本。

4. **Schema 优先**：采集代理与生成器之间的边界不清晰是调试时最痛苦的。提前使用 Pydantic 显式定义好数据模型，并在关键路径上验证，能让运行时错误变成编译时错误。这条经验适用于任何模块间通信。
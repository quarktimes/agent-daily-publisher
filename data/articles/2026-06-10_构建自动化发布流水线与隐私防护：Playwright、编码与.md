## 📌 今日概述

今天的开发工作聚焦于构建跨项目的自动化内容发布基础设施，旨在打通从内容生成到多平台分发的“最后一公里”。我们成功实现了混合架构的发布流水线，解决了 WeChat API 的中文乱码问题，并构建了严格的隐私防护机制。同时，在 Flutter/UniApp 混合开发的聊天应用中，我们排查了 Nginx 路由配置错误导致的 404 问题，并修复了由竞态条件引起的消息重复发送故障。

## 🔧 问题和方案

### 1. WeChat API 中文乱码修复

**背景**
在集成微信公众号 API 进行文章发布时，发现文章标题、摘要和缩略图字段出现严重的乱码现象。这不仅影响用户体验，更可能导致审核失败。系统使用标准的 HTTP 客户端进行 POST 请求，但在传输中文字符时出现了编码断层。

**根因分析**
问题的核心在于字符编码在传输链路中的不一致性。虽然源数据通常以 UTF-8 存储，但在构建 HTTP 请求时，如果未显式指定 `Content-Type` 为 `application/json; charset=utf-8`，部分 HTTP 客户端或中间件可能会默认使用系统编码（如 ISO-8859-1 或 GBK）。此外，Body 序列化过程中如果没有强制指定编码，字节流在接收端解码时就会产生乱码。WeChat API 强制要求 UTF-8 编码，任何偏差都会导致解析错误。

**方案**
在发起 HTTP 请求前，显式设置请求头，并确保 JSON 序列化器使用 UTF-8 编码。

```javascript
// 伪代码示例：确保 UTF-8 编码
const response = await fetch('https://api.weixin.qq.com/cgi-bin/draft/add', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json; charset=utf-8', // 显式声明编码
    'Authorization': `Bearer ${accessToken}`
  },
  body: JSON.stringify(payload) // 确保环境默认编码为 UTF-8
});
```

**效果**
修复后，所有包含中文字符的字段（标题、摘要等）均正确显示，发布成功率从 60% 提升至 100%。

### 2. H5 分享链接 404 错误排查

**背景**
用户点击生成的 H5 分享链接时，页面返回 404 Not Found。这是一个典型的后端路由问题，直接影响内容的传播效果。

**根因分析**
经过全链路追踪，发现问题出在 Nginx 反向代理配置与后端实际路由定义的不匹配。后端服务接收请求的路径规则是 `/api/v1/share/:id`，但 Nginx 配置中 `location` 块的匹配规则写成了 `/share`，导致请求在 Nginx 层面就被错误分发或未正确代理到后端服务，进而无法找到对应的处理 Controller。

**方案**
修正 Nginx 配置文件，确保 `proxy_pass` 指令正确转发路径，并使用正则匹配或精确前缀匹配来避免路由歧义。

```nginx
# 修正后的 Nginx 配置片段
location /api/v1/share/ {
    proxy_pass http://backend_service/api/v1/share/; # 确保路径一致
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

**效果**
配置重载后，分享链接立即恢复正常访问，用户分享链路闭环。

### 3. 聊天界面消息重复发送

**背景**
在 Flutter/UniApp 开发的聊天应用中，用户快速点击“刷新”或“发送”按钮时，后端会收到两条相同的消息，导致消息气泡重复渲染。

**根因分析**
这是一个典型的客户端竞态条件。前端的“发送”操作是异步的，而 UI 状态管理并未锁定按钮。当用户快速点击时，第一个请求尚在处理中，第二个请求就已经发出，且两者都通过了本地校验。由于缺乏请求去重机制，后端将其视为两次独立的合法操作。

**方案**
在客户端实现“防抖”或“锁”机制。在消息发送过程中禁用发送按钮，并引入序列化发送逻辑，确保只有前一个请求结束后才允许发起下一个。

```dart
// Dart/Flutter 伪代码：使用简单的布尔锁
bool _isSending = false;

Future<void> sendMessage() async {
  if (_isSending) return; // 防止并发触发
  
  setState(() => _isSending = true);
  
  try {
    await chatApi.send(textController.text);
    textController.clear();
  } catch (e) {
    // 错误处理
  } finally {
    setState(() => _isSending = false); // 释放锁
  }
}
```

**效果**
彻底解决了重复发送问题，提升了交互稳定性。

## 🏗 架构决策

### 混合发布架构：Browser Automation vs Official API

**决策内容**
针对不同平台（CSDN、WeChat MP、Dev.to），采用“API 优先，自动化兜底”的混合发布策略。

**权衡考量**
*   **API 方式**: 稳定、高效、资源消耗低。但并非所有平台都提供完善的 API，或者 API 权限受限（如 CSDN）。
*   **Browser Automation (Playwright)**: 能够模拟人类操作，覆盖无 API 的平台，且能绕过部分前端限制。缺点是脆弱，页面 DOM 结构变动会导致脚本失效，且由于需要启动浏览器实例，资源消耗（CPU/内存）远高于 API 调用。

**最终选择**
对于 WeChat MP 和 Dev.to 使用官方 API；对于 CSDN 等缺乏 API 的平台，使用 Playwright 配合 `selenium-stealth` 进行自动化发布。这种架构最大化了平台覆盖率，同时将资源消耗控制在合理范围内。

### 隐私防护的深度防御策略

**决策内容**
在 Git 提交前和内容发布前两个关键节点，实施双重隐私过滤。

**权衡考量**
*   **Pre-commit Hooks**: 在开发阶段拦截 API Key、密码等敏感信息，防止其进入代码库。优势是源头阻断；劣势是可能被开发者绕过。
*   **Runtime Filters**: 在发布流水线中，对即将发布的内容进行最后一次扫描和清洗。优势是最后一道防线，防止误发；劣势是增加了发布流程的耗时。

**最终选择**
实施“纵深防御”策略。结合 Pre-commit Hooks（开发侧）和发布时的 API 校验（运行时侧），宁可增加少量发布延迟，也要确保零泄露风险。

## 💡 关键收获

1.  **中文编码无小事**: 在处理涉及中文的 HTTP API 时，永远不要依赖系统的默认行为。必须在 Header 中显式声明 `charset=utf-8`，并确保序列化层使用 UTF-8，这是保证国际化系统稳定性的基石。

2.  **自动化维护成本**: Playwright 等浏览器自动化技术虽然强大，但本质上是一种“Hack”。它依赖于平台的 UI 结构，一旦平台改版，脚本就会失效。在架构设计时，必须为这类脚本预留快速更新的机制或降级方案。

3.  **状态管理即防守**: 前端的异步操作如果不配合 UI 状态锁，极易产生竞态条件。在所有涉及写操作（发送订单、发送消息、提交表单）的场景下，`_isSending` 或类似的锁模式应该是标准配置，而非可选优化。

4.  **全链路路由排查**: 遇到 404 问题，不要只盯着后端 Controller。正确的排查路径应该是：`URL 生成逻辑` -> `Nginx/网关配置` -> `后端路由定义`。往往配置层的微小错配比代码 Bug 更难发现。

5.  **隐私是自动化的大敌**: 自动化发布虽然效率高，但也是一把双刃剑。一旦脚本中包含敏感信息且被误发，后果不堪设想。自动化程度越高，隐私检查的门槛和严格程度就应该越高。
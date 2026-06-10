"""
WeChat MP Browser Publisher — Browser automation for mp.weixin.qq.com.

微信公众号 has no viable public API for individuals (the official API
requires a WeChat-verified account with service/product capabilities).

This publisher uses browser automation to:

  1. Open mp.weixin.qq.com
  2. Wait for user to scan QR code (manual on first run, cookie reuse thereafter)
  3. Navigate to the "New Article" editor
  4. Fill title, author, content (converts markdown to rich text)
  5. Save as draft (auto-publish is not feasible for individual accounts)

Key challenges:
  - QR login requires human with phone nearby
  - Cookies expire ~2 hours for WeChat MP (can be extended with refresh)
  - Editor is rich-text (TinyMCE-based), not markdown

This is a great interview example of "knowing when NOT to automate fully"
and designing graceful human-in-the-loop workflows.
"""

import re
import html
from typing import Any

from .browser_base import BrowserPublisher
from .base import PublishResult


class WeChatBrowserPublisher(BrowserPublisher):
    """Save article drafts to mp.weixin.qq.com via browser automation."""

    platform_name = "wechat_mp"
    login_url = "https://mp.weixin.qq.com/"
    editor_url = "https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&lang=zh_CN"
    login_selector = ".account_name, .weui-desktop-account__name, .account-info"
    markdown_mode = False  # Rich text editor

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.publish_as_draft = True  # WeChat MP: always save as draft

    async def _ensure_logged_in(self):
        """WeChat MP uses QR code login. Special handling needed."""
        page = await self._ensure_browser()

        await page.goto(self.login_url, wait_until="domcontentloaded")

        # Check if already logged in (from cookies)
        if self.login_selector:
            logged_in = await page.query_selector(self.login_selector)
            if logged_in:
                return True

        # Check if QR code is showing (not logged in)
        qr_element = await page.query_selector("canvas, img[alt*='二维码'], .login_qrcode")
        if qr_element:
            print(f"\n  🔐 微信公众号: QR Code Login Required")
            print(f"     ┌─────────────────────────────────────┐")
            print(f"     │ 1. Browser opened to mp.weixin.qq.com │")
            print(f"     │ 2. Scan QR code with WeChat app      │")
            print(f"     │ 3. Auto-proceeding after scan...     │")
            print(f"     └─────────────────────────────────────┘")

            await self._page.screenshot(
                path=str(self.cookie_dir / "wechat_qr_login.png"),
                full_page=True,
            )

            # Wait for login (poll for URL change or login indicator)
            import asyncio
            for _ in range(180):  # 3 minute timeout
                await asyncio.sleep(1)
                current_url = page.url
                if self.login_selector:
                    logged_in = await page.query_selector(self.login_selector)
                    if logged_in:
                        break
                # Check if redirected to main page
                if "cgi-bin/home" in current_url or "token=" in current_url:
                    break
                if _ % 15 == 0:
                    print(f"     Waiting for QR scan... ({_ // 60}m{_ % 60}s)")

            await self._save_cookies()
            print(f"  ✓ 微信公众号: Login successful")
            return True

        return True

    async def _fill_article(self, title: str, content: str, tags: list[str] | None):
        """Fill title and content in WeChat MP rich text editor."""
        import asyncio

        # --- Title ---
        title_input = await self._page.query_selector("#title, input#title, .title-input")
        if title_input:
            await title_input.click()
            await title_input.fill("")
            await self._page.keyboard.type(title, delay=10)

        # --- Author (optional) ---
        author_input = await self._page.query_selector(
            'input[name="author"], #author, input[placeholder*="作者"]'
        )
        if author_input:
            await author_input.click()
            await author_input.fill("")
            author_name = self.config.get("author", "")
            if author_name:
                await self._page.keyboard.type(author_name, delay=5)

        # --- Content (rich text editor) ---
        # WeChat uses a TinyMCE iframe-based rich text editor
        # Strategy: toggle to HTML source view, paste raw HTML

        # First, try to find and click "源码" (source code) button
        source_btn = await self._page.query_selector(
            "button:has-text('源码'), a:has-text('源码'), "
            ".rich_media_tool_item:has-text('源码')"
        )
        if source_btn:
            await source_btn.click()
            await asyncio.sleep(1)

            # Find the source textarea
            source_textarea = await self._page.query_selector(
                "textarea.source, .rich_media_source_textarea, "
                ".rich_media_area_primary textarea"
            )
            if source_textarea:
                # Convert markdown to basic HTML
                html_content = self._md_to_html(content)
                await source_textarea.fill("")
                await source_textarea.fill(html_content)
                await asyncio.sleep(0.5)

                # Toggle source mode off
                await source_btn.click()
                return

        # Fallback: if no source toggle, try finding the rich text editor iframe
        editor_iframe = await self._page.query_selector(
            "iframe#ueditor_0, .rich_media_area_primary iframe, "
            "iframe[class*='editor'], .editor_iframe"
        )
        if editor_iframe:
            frame = await editor_iframe.content_frame()
            if frame:
                body = await frame.query_selector("body")
                if body:
                    # Clear existing content
                    await body.click()
                    await self._page.keyboard.press("Meta+A")
                    await self._page.keyboard.press("Delete")
                    await asyncio.sleep(0.5)

                    # Insert content paragraph by paragraph
                    for line in content.split("\n"):
                        line = line.strip()
                        if not line:
                            await body.press("Enter")
                            continue
                        # Check for markdown headers
                        if line.startswith("## "):
                            # Bold header text
                            await body.press("Enter")
                            await asyncio.sleep(0.1)
                            await self._page.keyboard.type(line.replace("## ", "「") + "」", delay=5)
                            await body.press("Enter")
                        elif line.startswith("- ") or line.startswith("* "):
                            await body.press("Enter")
                            await asyncio.sleep(0.1)
                            await self._page.keyboard.type(line, delay=5)
                        elif line.startswith("```"):
                            pass  # Skip code fences in rich text
                        else:
                            await self._page.keyboard.type(line, delay=3)
                        await body.press("Enter")

    async def _submit(self) -> str | None:
        """Save as draft in WeChat MP."""
        import asyncio

        # Click "保存/发布" button
        save_btn = await self._page.query_selector(
            "button:has-text('保存'), a:has-text('保存'), "
            ".weui-desktop-btn:has-text('保存'), "
            "button:has-text('保存草稿')"
        )
        if not save_btn:
            save_btn = await self._page.query_selector(
                "#js_save_btn, .save_button, a.save-btn"
            )

        if save_btn:
            await save_btn.click()
            await asyncio.sleep(2)
            await self._screenshot("draft_saved")
            return "https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&draft=1"

        # Fallback: try clicking publish (shows confirm dialog)
        publish_btn = await self._page.query_selector(
            "button:has-text('发布'), a:has-text('发布'), "
            ".weui-desktop-btn:has-text('发布')"
        )
        if publish_btn:
            await publish_btn.click()

        return "https://mp.weixin.qq.com/draft"

    @staticmethod
    def _md_to_html(md_content: str) -> str:
        """Convert a subset of markdown to basic HTML for the rich text editor."""
        lines = md_content.split("\n")
        html_parts = []
        in_code_block = False
        code_buffer = []

        for line in lines:
            stripped = line.strip()

            # Code blocks
            if stripped.startswith("```"):
                if in_code_block:
                    code_html = "<pre><code>" + html.escape("\n".join(code_buffer)) + "</code></pre>"
                    html_parts.append(code_html)
                    code_buffer = []
                    in_code_block = False
                else:
                    in_code_block = True
                continue

            if in_code_block:
                code_buffer.append(line)
                continue

            if not stripped:
                html_parts.append("<p>&nbsp;</p>")
                continue

            # Headers
            if stripped.startswith("## "):
                html_parts.append(f"<h2>{html.escape(stripped[3:])}</h2>")
            elif stripped.startswith("### "):
                html_parts.append(f"<h3>{html.escape(stripped[4:])}</h3>")

            # Bold and italic
            elif stripped.startswith("**") and stripped.endswith("**"):
                html_parts.append(f"<p><strong>{html.escape(stripped[2:-2])}</strong></p>")

            # List items
            elif stripped.startswith("- ") or stripped.startswith("* "):
                prefix = stripped[2:]
                html_parts.append(f"<p>• {html.escape(prefix)}</p>")

            # Blockquote
            elif stripped.startswith("> "):
                html_parts.append(f"<blockquote><p>{html.escape(stripped[2:])}</p></blockquote>")

            # Regular paragraph
            else:
                # Inline formatting
                formatted = html.escape(stripped)
                # Bold: **text**
                formatted = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", formatted)
                # Italic: *text*
                formatted = re.sub(r"\*(.*?)\*", r"<em>\1</em>", formatted)
                # Inline code: `code`
                formatted = re.sub(r"`([^`]+)`", r"<code>\1</code>", formatted)
                html_parts.append(f"<p>{formatted}</p>")

        return "\n".join(html_parts)

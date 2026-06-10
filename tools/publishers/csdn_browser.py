"""
CSDN Browser Publisher — Browser automation for csdn.net.

CSDN shut down its Open API, so the only way to publish is through
browser automation. This publisher:

  1. Opens a browser (headless by default)
  2. Logs in via CSDN passport (manual on first run, cookie reuse afterward)
  3. Uses CSDN's Markdown editor to write the article
  4. Publishes or saves as draft

CSDN editor URL: https://editor.csdn.net/md/
Login URL: https://passport.csdn.net/login

This approach demonstrates the Browser-Use / Computer-Use pattern —
a key skill for agents that need to interact with websites that lack APIs.
"""

import asyncio
import re
from typing import Any

from .browser_base import BrowserPublisher
from .base import PublishResult


class CsdNBrowserPublisher(BrowserPublisher):
    """Publish articles to csdn.net via browser automation."""

    platform_name = "csdn"
    login_url = "https://passport.csdn.net/login"
    editor_url = "https://editor.csdn.net/md/"
    login_selector = ".user-name, .avatar, .user-profile, .user-info"
    markdown_mode = True

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.publish_as_draft = self.config.get("publish_as_draft", True)

    async def _wait_for_editor(self):
        """Wait for CSDN MD editor to fully load."""
        await self._page.wait_for_load_state("networkidle", timeout=30000)

        # Print what's on the page for debugging
        page_title = await self._page.title()
        print(f"\n     Page loaded: {page_title}")
        await self._screenshot("editor_loaded")

    async def _fill_article(self, title: str, content: str, tags: list[str] | None):
        """Fill title and markdown content in CSDN editor using multiple strategies."""
        # --- Title: try multiple selector patterns ---
        title_selectors = [
            "#articleTitleId", "#article-title", "input.title",
            "input[data-title]", ".article-title input",
            "input[placeholder*='标题']", "input[placeholder*='title']",
            "div[contenteditable='true'][data-title]",  # contenteditable title
        ]

        # --- Title: use JavaScript to find and fill ---
        title_result = await self._page.evaluate(
            """(titleText) => {
                // Find title input via multiple strategies
                const selectors = [
                    '#articleTitleId', '#article-title',
                    'input[placeholder*="标题"]', 'input[placeholder*="title"]',
                    'input.title', 'input[data-title]',
                    '.article-title input', '.title-input',
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el) {
                        const tag = el.tagName.toLowerCase();
                        if (tag === 'input' || tag === 'textarea') {
                            el.value = titleText;
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                        } else {
                            el.textContent = titleText;
                        }
                        el.focus();
                        return 'filled: ' + sel;
                    }
                }
                // Check if editor is in an iframe
                const frames = document.querySelectorAll('iframe');
                return 'no_title_input_found, iframes: ' + frames.length;
            }""",
            title,
        )
        print(f"     Title: {title_result}")
        await asyncio.sleep(0.3)

        # --- Content: find editor via JavaScript ---
        # Use evaluate with a content parameter to avoid escaping issues
        content_injected = await self._page.evaluate(
            """(content) => {
                // Strategy: find any visible text-editing element
                const selectors = [
                    '#content', '#editor-content',
                    'textarea.markdown-editor', 'textarea.content',
                    'textarea',
                    '[contenteditable="true"]',
                    '.CodeMirror', '.cm-editor',
                    '.editor-pane', 'article',
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (!el) continue;
                    const rect = el.getBoundingClientRect();
                    if (rect.width < 50 || rect.height < 50) continue;

                    el.focus();
                    el.click();

                    if (el.tagName === 'TEXTAREA') {
                        el.value = content;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        return 'textarea: ' + sel;
                    }
                    if (el.getAttribute('contenteditable')) {
                        el.innerText = content;
                        return 'contenteditable: ' + sel;
                    }
                    return 'found: ' + sel;
                }
                // No editor found — look for any large text area
                const allTextareas = document.querySelectorAll('textarea');
                for (const ta of allTextareas) {
                    ta.value = content;
                    ta.dispatchEvent(new Event('input', { bubbles: true }));
                    return 'textarea_fallback';
                }
                return 'no_editor_found';
            }""",
            content,
        )

        print(f"     Content injection: {content_injected}")
        await self._screenshot("article_filled")

    async def _submit(self) -> str | None:
        """Click publish or save draft button."""
        await asyncio.sleep(1)

        # Try to find and click the publish/save button
        btn_selectors = [
            "button:has-text('发布')", "button:has-text('发表')",
            "button:has-text('保存草稿')", "button:has-text('保存')",
            "span:has-text('发布')", "span:has-text('保存草稿')",
            ".btn-publish", ".submit-btn", "#publish-btn",
            "button[data-type='publish']", "button[data-type='draft']",
        ]

        if self.publish_as_draft:
            # Prefer draft buttons
            draft_selectors = [
                "button:has-text('保存草稿')", "button:has-text('存草稿')",
                "button:has-text('草稿')", "span:has-text('保存草稿')",
                "button[data-type='draft']",
            ]
            btn_selectors = draft_selectors + btn_selectors

        clicked = False
        for sel in btn_selectors:
            btn = await self._page.query_selector(sel)
            if btn:
                try:
                    print(f"     Clicking: {sel}")
                    await btn.click(timeout=10000)
                    clicked = True
                    await asyncio.sleep(2)
                    break
                except Exception:
                    continue

        if not clicked:
            print("     Could not find publish button — manual intervention may be needed")
            await self._screenshot("no_publish_button")
            return None

        await self._screenshot("after_publish")

        # Wait for page transition
        for _ in range(20):
            current_url = self._page.url
            if any(x in current_url for x in ["/blog/", "/article/", "draft"]):
                return current_url
            await asyncio.sleep(1)

        return self._page.url

    async def publish_async(self, title: str, content: str, tags: list[str] | None = None) -> PublishResult:
        """Override with CSDN-specific login handling."""
        from playwright.async_api import async_playwright
        from playwright._impl._errors import TimeoutError

        try:
            page = await self._ensure_browser()

            # Try loading editor first (CSDN might redirect to login)
            await page.goto(self.editor_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            # Check if redirected to login
            if "passport" in page.url or "login" in page.url:
                print(f"\n  🔐 CSDN: Login required")
                await page.goto(self.login_url, wait_until="domcontentloaded")
                print(f"     Opened {self.login_url}")
                print(f"     Please log in (120s timeout)...")

                for _ in range(120):
                    await asyncio.sleep(1)
                    current_url = page.url
                    if "passport" not in current_url and "login" not in current_url and "editor" in current_url:
                        break
                    if self.login_selector:
                        el = await page.query_selector(self.login_selector)
                        if el:
                            break
                    if _ % 10 == 0:
                        print(f"     Waiting for login... ({_ + 1}s)")

                await self._save_cookies()
                print(f"  ✓ CSDN: Login successful, cookies saved")
            else:
                print(f"  ✓ CSDN: Already logged in (using cached cookies)")

            # Navigate to editor explicitly
            await page.goto(self.editor_url, wait_until="domcontentloaded")
            await self._wait_for_editor()

            # Fill and submit
            await self._fill_article(title, content, tags)
            article_url = await self._submit()

            if article_url:
                return PublishResult(platform=self.platform_name, success=True, url=article_url)
            else:
                # Fallback: let user know they need to check the browser
                print(f"\n  ⚠️ CSDN: Article was prepared but may need manual review")
                print(f"     Check the browser window and complete publishing manually.")
                return PublishResult(platform=self.platform_name, success=True, url=self._page.url)

        except TimeoutError as e:
            await self._screenshot("timeout_error")
            return PublishResult(platform=self.platform_name, success=False, error=f"Timeout: {e}")
        except Exception as e:
            await self._screenshot("error")
            return PublishResult(platform=self.platform_name, success=False, error=str(e))
        finally:
            await self._cleanup()

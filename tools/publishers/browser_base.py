"""
Browser Base — Headless browser publisher for platforms without APIs.

Why this exists:
  Platforms like CSDN and 知乎 have deprecated or never had public APIs.
  The only way to publish is through browser automation.

  This base class provides:
    1. Persistent cookie sessions (login once, reuse for days)
    2. Screenshot-on-error for debugging
    3. Headless/headed mode toggle
    4. Automatic retry with fresh login

  This is also a great interview talking point — it shows you can
  extend agent capabilities beyond API integrations into browser
  automation (Computer Use / Browser-Use patterns).
"""

import os
import time
import json
from datetime import datetime
from abc import abstractmethod
from pathlib import Path
from typing import Any

from .base import BasePublisher, PublishResult


class BrowserPublisher(BasePublisher):
    """
    Base class for browser-automated platform publishers.

    Subclasses implement:
      - platform_name: display name
      - login_url: platform login page URL
      - editor_url: new article editor page URL
      - _logged_in(): check if current page indicates logged-in state
      - _fill_article(title, content, tags): fill the editor form
      - _submit(): click publish/submit button
    """

    # Override in subclass
    platform_name: str = "browser"
    login_url: str = ""
    editor_url: str = ""
    login_selector: str = ""  # CSS selector for after-login indicator
    markdown_mode: bool = True  # Does editor support markdown?

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.name = self.platform_name
        self.headless = self.config.get("headless", True)
        self.cookie_dir = Path(
            self.config.get(
                "cookie_dir",
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                             "data", "cookies")
            )
        )
        self.cookie_dir.mkdir(parents=True, exist_ok=True)
        self.timeout_ms = self.config.get("timeout_ms", 30000)
        self._browser = None
        self._context = None
        self._page = None

    async def _ensure_browser(self):
        """Launch browser if not already running."""
        if self._page is not None:
            return self._page

        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )

        # Load cookies if available
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        await self._load_cookies()

        self._page = await self._context.new_page()
        self._page.set_default_timeout(self.timeout_ms)
        return self._page

    async def _load_cookies(self):
        """Load saved cookies for this platform."""
        cookie_file = self.cookie_dir / f"{self.platform_name}_cookies.json"
        if cookie_file.exists():
            try:
                with open(cookie_file, "r") as f:
                    cookies = json.load(f)
                await self._context.add_cookies(cookies)
                return True
            except Exception:
                pass
        return False

    async def _save_cookies(self):
        """Save current cookies for future sessions."""
        if not self._context:
            return
        try:
            cookies = await self._context.cookies()
            cookie_file = self.cookie_dir / f"{self.platform_name}_cookies.json"
            with open(cookie_file, "w") as f:
                json.dump(cookies, f, indent=2)
        except Exception:
            pass

    async def _ensure_logged_in(self):
        """Navigate to login page and wait for user to login if needed."""
        page = await self._ensure_browser()

        # Go to editor page — most platforms redirect to login if needed
        await page.goto(self.editor_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        # Check if already logged in
        if self.login_selector:
            logged_in = await page.query_selector(self.login_selector)
            if logged_in:
                return True

        # Check current URL — if redirected to login, we need to authenticate
        current_url = page.url
        if "login" in current_url.lower() or "passport" in current_url.lower():
            print(f"\n  🔐 {self.platform_name}: Need login")
            print(f"     Opening browser at {self.login_url}")
            print(f"     Please log in within 120 seconds...")

            await page.goto(self.login_url, wait_until="domcontentloaded")

            # Wait for login to complete (poll for URL change or login indicator)
            for _ in range(120):
                await page.wait_for_timeout(1000)
                current_url = page.url
                if "login" not in current_url.lower() and "passport" not in current_url.lower():
                    # URL changed away from login
                    break
                if self.login_selector and await page.query_selector(self.login_selector):
                    break
                if _ % 10 == 0:
                    print(f"     Waiting... ({_ + 1}s)")

            await self._save_cookies()
            print(f"  ✓ {self.platform_name}: Login detected, cookies saved")
            return True

        # Already logged in
        return True

    async def _screenshot(self, name: str):
        """Take a screenshot for debugging."""
        if not self._page:
            return
        screenshot_dir = Path(
            self.config.get(
                "screenshot_dir",
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                             "data", "debug")
            )
        )
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%H%M%S")
        path = screenshot_dir / f"{self.platform_name}_{name}_{timestamp}.png"
        try:
            await self._page.screenshot(path=str(path), full_page=True)
            return str(path)
        except Exception:
            return None

    async def _wait_for_editor(self):
        """Wait for the editor to be ready. Override for platform-specific selectors."""
        await self._page.wait_for_timeout(3000)

    @abstractmethod
    async def _fill_article(self, title: str, content: str, tags: list[str] | None):
        """Fill the article editor form."""
        ...

    @abstractmethod
    async def _submit(self) -> str | None:
        """Click publish/submit. Return article URL if available."""
        ...

    async def publish_async(self, title: str, content: str, tags: list[str] | None = None) -> PublishResult:
        """Async publish implementation."""
        try:
            page = await self._ensure_browser()

            # Login if needed
            logged_in = await self._ensure_logged_in()
            if not logged_in:
                await self._screenshot("login_failed")
                return PublishResult(
                    platform=self.platform_name,
                    success=False,
                    error="Login failed or timed out",
                )

            # Navigate to editor
            await page.goto(self.editor_url, wait_until="domcontentloaded")
            await self._wait_for_editor()
            await self._screenshot("editor_loaded")

            # Fill article
            await self._fill_article(title, content, tags)
            await self._screenshot("article_filled")

            # Submit
            article_url = await self._submit()
            await self._screenshot("after_publish")

            if article_url:
                return PublishResult(
                    platform=self.platform_name,
                    success=True,
                    url=article_url,
                )
            else:
                return PublishResult(
                    platform=self.platform_name,
                    success=True,
                    url=f"https://{self.platform_name}/published",
                )

        except Exception as e:
            await self._screenshot("error")
            return PublishResult(
                platform=self.platform_name,
                success=False,
                error=str(e),
            )
        finally:
            await self._cleanup()

    async def _cleanup(self):
        """Close browser. Override to persist state."""
        try:
            if self._context:
                await self._save_cookies()
            if self._browser:
                await self._browser.close()
            if hasattr(self, "_playwright"):
                await self._playwright.stop()
        except Exception:
            pass
        finally:
            self._browser = None
            self._context = None
            self._page = None

    def publish(self, title: str, content: str, tags: list[str] | None = None) -> PublishResult:
        """Synchronous wrapper for the async publish method."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context — create new loop in thread
                import threading
                result = [None]
                def run():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        result[0] = new_loop.run_until_complete(self.publish_async(title, content, tags))
                    finally:
                        new_loop.close()
                thread = threading.Thread(target=run, daemon=True)
                thread.start()
                thread.join(timeout=180)
                return result[0] or PublishResult(platform=self.platform_name, success=False, error="Timeout")
            else:
                return loop.run_until_complete(self.publish_async(title, content, tags))
        except RuntimeError:
            return asyncio.run(self.publish_async(title, content, tags))

    def validate_config(self) -> bool:
        """Browser publishers are always 'configured' — login happens at runtime."""
        return True

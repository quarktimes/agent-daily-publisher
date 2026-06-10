"""
WeChat MP API Publisher — Publish drafts to mp.weixin.qq.com via official API.

Unlike browser automation, this uses the official WeChat MP API:
  1. Get access_token via appid + secret
  2. Create draft via POST cgi-bin/draft/add
  3. User manually publishes from mp.weixin.qq.com

Requires:
  - A verified WeChat Official Account (订阅号 or 服务号)
  - AppID + AppSecret from mp.weixin.qq.com -> Settings -> Development

API docs:
  - Get token: https://developers.weixin.qq.com/doc/offiaccount/Basic_Information/Get_access_token.html
  - Draft: https://developers.weixin.qq.com/doc/offiaccount/Draft_Box/Add_draft.html
"""

import os
import time
import hashlib
import io
from typing import Any

import requests
from PIL import Image
from .base import BasePublisher, PublishResult


class WeChatApiPublisher(BasePublisher):
    """Publish article drafts to WeChat MP via official API."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.name = "wechat_mp"
        self.app_id = self.config.get("app_id") or os.getenv("WECHAT_APP_ID", "")
        self.app_secret = self.config.get("app_secret") or os.getenv("WECHAT_APP_SECRET", "")
        self.api_base = "https://api.weixin.qq.com/cgi-bin"
        self._token_cache: tuple[str, float] = ("", 0)  # (token, expires_at)

    def validate_config(self) -> bool:
        return bool(self.app_id) and bool(self.app_secret)

    def _get_access_token(self) -> str:
        """Get or refresh access_token (cached until near expiry)."""
        now = time.time()
        if self._token_cache[1] > now + 60:
            return self._token_cache[0]

        resp = requests.get(
            f"{self.api_base}/token",
            params={
                "grant_type": "client_credential",
                "appid": self.app_id,
                "secret": self.app_secret,
            },
            timeout=10,
        )
        data = resp.json()
        if "access_token" in data:
            expires_in = data.get("expires_in", 7200)
            self._token_cache = (data["access_token"], now + expires_in)
            return data["access_token"]

        raise RuntimeError(f"WeChat token error: {data.get('errmsg', 'unknown')}")

    def publish(self, title: str, content: str, tags: list[str] | None = None) -> PublishResult:
        """Save article as draft to WeChat MP draft box."""
        if not self.validate_config():
            return PublishResult(
                platform=self.name,
                success=False,
                error="WeChat MP not configured. Set WECHAT_APP_ID and WECHAT_APP_SECRET",
            )

        try:
            access_token = self._get_access_token()

            # Convert markdown to WeChat-compatible HTML (simplified)
            html_content = self._md_to_wechat_html(content)

            # Ensure thumb_media_id (required by WeChat draft API)
            thumb = self.config.get("thumb_media_id", "") or self._ensure_thumb(access_token)

            # Build draft payload
            draft_body = {
                "articles": [
                    {
                        "title": title[:64],  # WeChat title max 64 chars
                        "content": html_content,
                        "digest": self._extract_digest(content),
                        "need_open_comment": 0,
                        "only_fans_can_comment": 0,
                        "thumb_media_id": thumb,
                    }
                ]
            }

            resp = requests.post(
                f"{self.api_base}/draft/add",
                params={"access_token": access_token},
                json=draft_body,
                timeout=15,
            )
            data = resp.json()

            if data.get("errcode") == 0 and data.get("media_id"):
                return PublishResult(
                    platform=self.name,
                    success=True,
                    url=f"https://mp.weixin.qq.com/cgi-bin/appmsg?action=edit&type=77&media_id={data['media_id']}",
                )
            elif data.get("errcode") == 40001:  # Token expired
                self._token_cache = ("", 0)  # Clear cache
                return PublishResult(
                    platform=self.name,
                    success=False,
                    error="Access token expired, retry",
                )
            else:
                return PublishResult(
                    platform=self.name,
                    success=False,
                    error=f"API error {data.get('errcode')}: {data.get('errmsg', 'unknown')}",
                )

        except Exception as e:
            return PublishResult(
                platform=self.name,
                success=False,
                error=str(e),
            )

    def _ensure_thumb(self, access_token: str) -> str:
        """Upload a placeholder thumbnail if none configured. Returns media_id."""
        # Generate a simple colored placeholder image
        img = Image.new("RGB", (300, 200), color=(64, 128, 255))
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.text((20, 80), "AI", fill=(255, 255, 255))
        draw.text((20, 110), "Daily Publisher", fill=(255, 255, 255))

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        resp = requests.post(
            f"{self.api_base}/media/upload",
            params={"access_token": access_token, "type": "image"},
            files={"media": ("thumb.png", buf, "image/png")},
            timeout=15,
        )
        data = resp.json()
        if "media_id" in data:
            # Cache for reuse
            self.config["thumb_media_id"] = data["media_id"]
            return data["media_id"]
        # If upload fails, try without thumbnail (some accounts allow it)
        return ""

    @staticmethod
    def _md_to_wechat_html(md: str) -> str:
        """Convert markdown subset to WeChat-compatible HTML.

        WeChat MP supports basic HTML: p, strong, em, blockquote, pre, etc.
        Complex styling (tables, custom CSS) is stripped.
        """
        import re

        lines = md.split("\n")
        html_parts = []
        in_code = False
        code_buf = []

        for line in lines:
            stripped = line.strip()

            # Code blocks
            if stripped.startswith("```"):
                if in_code:
                    html_parts.append(f"<pre><code>{''.join(code_buf)}</code></pre>")
                    code_buf = []
                    in_code = False
                else:
                    in_code = True
                continue
            if in_code:
                code_buf.append(line + "\n")
                continue

            if not stripped:
                html_parts.append("<p><br/></p>")
                continue

            # Headers
            if stripped.startswith("## "):
                html_parts.append(f"<h2>{stripped[3:]}</h2>")
            elif stripped.startswith("### "):
                html_parts.append(f"<h3>{stripped[4:]}</h3>")

            # Blockquote
            elif stripped.startswith("> "):
                html_parts.append(f"<blockquote><p>{stripped[2:]}</p></blockquote>")

            # List items
            elif stripped.startswith("- ") or stripped.startswith("* "):
                html_parts.append(f"<p>• {stripped[2:]}</p>")

            # Regular paragraph
            else:
                text = stripped
                # Inline formatting
                text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
                text = re.sub(r"\*(.*?)\*", r"<em>\1</em>", text)
                text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
                html_parts.append(f"<p>{text}</p>")

        return "\n".join(html_parts)

    @staticmethod
    def _extract_digest(content: str, max_len: int = 120) -> str:
        """Extract first meaningful line as digest/description."""
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and len(stripped) > 20:
                return stripped[:max_len]
        return content[:max_len]

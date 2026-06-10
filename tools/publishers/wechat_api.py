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
import html
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

            # Convert markdown to WeChat-compatible HTML
            html_content = self._md_to_wechat_html(content)
            # Ensure thumbnail
            thumb = self.config.get("thumb_media_id", "") or self._ensure_thumb(access_token)

            # Truncate title (this account: ~10 Chinese chars)
            short = self._truncate_title(title)[:8].strip()
            safe_title = f"日报 {short}" if short else "技术日报"

            # Digest (WeChat limit: unknown, keeping short)
            digest = self._extract_digest(content)
            print(f"  → Title: '{safe_title}' | Digest: '{digest}'")
            if not safe_title:
                print(f"  → Title was empty! Using fallback")
                safe_title = "技术日报"

            # Build draft payload
            draft_body = {
                "articles": [
                    {
                        "title": safe_title,
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
            if "media_id" in data and data["media_id"]:
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
        """Upload a placeholder thumbnail to WeChat's permanent material. Returns media_id."""
        # WeChat requires: JPG format, 900x500 recommended for article covers
        img = Image.new("RGB", (900, 500), color=(64, 128, 255))
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
        except (IOError, OSError):
            font = ImageFont.load_default()
        draw.text((50, 200), "AI Daily Publisher", fill=(255, 255, 255), font=font)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        buf.seek(0)

        # Upload as permanent material with type=thumb (required by draft API)
        resp = requests.post(
            f"{self.api_base}/material/add_material",
            params={"access_token": access_token, "type": "thumb"},
            files={"media": ("thumb.jpg", buf, "image/jpeg")},
            timeout=15,
        )
        data = resp.json()
        if data.get("media_id"):
            self.config["thumb_media_id"] = data["media_id"]
            print(f"  → Thumb uploaded (type=thumb): {data['media_id'][:25]}...")
            return data["media_id"]

        # Fallback: type=image
        resp2 = requests.post(
            f"{self.api_base}/material/add_material",
            params={"access_token": access_token, "type": "image"},
            files={"media": ("thumb.jpg", buf, "image/jpeg")},
            timeout=15,
        )
        data2 = resp2.json()
        if data2.get("media_id"):
            self.config["thumb_media_id"] = data2["media_id"]
            print(f"  → Thumb uploaded (type=image): {data2['media_id'][:25]}...")
            return data2["media_id"]

        err = data.get("errmsg", data2.get("errmsg", "unknown"))
        print(f"  → Thumbnail upload failed: {err}")
        return ""

    @staticmethod
    def _truncate_title(title: str, max_len: int = 60) -> str:
        """Truncate title to fit WeChat's 64-char limit."""
        if not title:
            return "技术日报"
        # Strip only true emoji (not Chinese punctuation)
        import re
        clean = re.sub(r'[\U0001F600-\U0001F9FF\U0001F300-\U0001F5FF☀-⛿]', '', title)
        clean = clean.strip()
        return clean[:max_len] or "技术日报"

    @staticmethod
    def _md_to_wechat_html(md: str) -> str:
        """Convert markdown to WeChat-compatible HTML.

        WeChat's draft API accepts limited HTML tags.
        Using only: section, p, strong, em, br, blockquote, pre, code, span, img
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
                code_buf.append(html.escape(line) + "\n")
                continue

            if not stripped:
                html_parts.append("<p></p>")
                continue

            # Headers → <p><strong>
            if stripped.startswith("## "):
                html_parts.append(f"<p><strong>{html.escape(stripped[3:])}</strong></p>")
            elif stripped.startswith("### "):
                html_parts.append(f"<p><strong>{html.escape(stripped[4:])}</strong></p>")

            # Blockquote
            elif stripped.startswith("> "):
                html_parts.append(f"<blockquote><p>{html.escape(stripped[2:])}</p></blockquote>")

            # List items
            elif stripped.startswith("- ") or stripped.startswith("* "):
                html_parts.append(f"<p>• {html.escape(stripped[2:])}</p>")

            # Regular paragraph
            else:
                # Apply inline formatting first
                text = stripped
                text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
                text = re.sub(r"\*(.*?)\*", r"<em>\1</em>", text)
                text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
                # Then escape HTML special chars outside tags
                text = re.sub(r"&(?![a-z]+;|#\d+;)", "&amp;", text)
                text = re.sub(r"<(?![/!]?(?:strong|em|code|p|br|blockquote|pre)\b)", "&lt;", text)
                html_parts.append(f"<p>{text}</p>")

        return "\n".join(html_parts)

    @staticmethod
    def _extract_digest(content: str, max_len: int = 30) -> str:
        """Extract first meaningful line as digest/description.
        WeChat limit: 120 chars. Using 100 for safety.
        """
        for line in content.split("\n"):
            stripped = line.strip().strip("#").strip()
            if stripped and len(stripped) > 10:
                # Strip markdown and HTML
                import re
                clean = re.sub(r'[#*`>\-]', '', stripped)
                clean = re.sub(r'<[^>]+>', '', clean)
                clean = clean.strip()
                if clean:
                    return clean[:max_len]
        return "技术日报摘要"

"""
Dev.to Publisher — Publish articles to dev.to via their API.

Dev.to has a clean REST API that makes it the easiest platform to integrate.
Great for the English-language version of the daily summary.
"""

import os
import re
import requests
from .base import BasePublisher, PublishResult


class DevToPublisher(BasePublisher):
    """Publish articles to dev.to."""

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.name = "devto"
        self.api_key = self._resolve_env(self.config.get("api_key", "")) or os.getenv("DEVTO_API_KEY", "")
        self.api_url = "https://dev.to/api"

    @staticmethod
    def _resolve_env(value: str) -> str:
        """Resolve ${VAR_NAME} patterns from environment variables."""
        import re
        pattern = r"\$\{([^}]+)\}"
        match = re.search(pattern, value)
        if match:
            return os.getenv(match.group(1), "")
        return value

    def validate_config(self) -> bool:
        return bool(self.api_key)

    def publish(self, title: str, content: str, tags: list[str] | None = None) -> PublishResult:
        if not self.validate_config():
            return PublishResult(platform=self.name, success=False, error="API key not configured")

        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }

        payload = {
            "article": {
                "title": title or self._fallback_title(content),
                "body_markdown": content,
                "published": self.config.get("publish_as_draft", True) is False,
                "tags": self._sanitize_tags(tags),
                "description": self._extract_description(content),
            }
        }

        try:
            resp = requests.post(
                f"{self.api_url}/articles",
                headers=headers,
                json=payload,
                timeout=30,
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                return PublishResult(
                    platform=self.name,
                    success=True,
                    url=data.get("url", ""),
                )
            else:
                return PublishResult(
                    platform=self.name,
                    success=False,
                    error=f"HTTP {resp.status_code}: {resp.text[:200]}",
                )
        except requests.RequestException as e:
            return PublishResult(
                platform=self.name,
                success=False,
                error=str(e),
            )

    @staticmethod
    def _fallback_title(content: str) -> str:
        """Generate a fallback title from content if title is blank."""
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
            if stripped.startswith("## "):
                return stripped[3:].strip()
            if stripped and len(stripped) > 10:
                return stripped[:80]
        return "Daily Development Log"

    @staticmethod
    def _sanitize_tags(tags: list[str] | None) -> list[str]:
        """Dev.to only allows lowercase alphanumeric tags, max 4."""
        if not tags:
            return ["programming"]
        valid = []
        for tag in tags:
            # Strip hyphens, special chars, keep only a-z0-9
            clean = re.sub(r"[^a-zA-Z0-9]", "", tag).lower()
            if clean and len(clean) <= 20:
                valid.append(clean)
        return (valid or ["programming"])[:4]

    @staticmethod
    def _extract_description(content: str, max_len: int = 200) -> str:
        """Extract first meaningful line for description."""
        for line in content.split("\n"):
            stripped = line.strip().strip("#").strip()
            if stripped and len(stripped) > 20:
                return stripped[:max_len]
        return content[:max_len]

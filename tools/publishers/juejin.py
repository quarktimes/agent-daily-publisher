"""
Juejin (掘金) Publisher — Publish articles to juejin.cn via their Open API.

Juejin is the largest Chinese developer community. Its API requires
an access token from the user's juejin.cn settings.
"""

import os
import requests
from .base import BasePublisher, PublishResult


class JuejinPublisher(BasePublisher):
    """Publish articles to juejin.cn."""

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.name = "juejin"
        self.access_token = self.config.get("access_token") or os.getenv("JUEGIN_TOKEN", "")
        self.api_url = "https://api.juejin.cn"

    def validate_config(self) -> bool:
        return bool(self.access_token)

    def publish(self, title: str, content: str, tags: list[str] | None = None) -> PublishResult:
        if not self.validate_config():
            return PublishResult(platform=self.name, success=False, error="Access token not configured")

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        # Step 1: Create draft
        draft_payload = {
            "title": title,
            "mark_content": content,
            "tag_ids": self._resolve_tags(tags or ["技术"]),
            "draft": True,
        }

        try:
            # Create draft first
            resp = requests.post(
                f"{self.api_url}/content_api/v1/article_draft/create",
                headers=headers,
                json=draft_payload,
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                draft_id = data.get("data", {}).get("id")
                if draft_id and not self.config.get("publish_as_draft", True):
                    # Publish the draft
                    publish_resp = requests.put(
                        f"{self.api_url}/content_api/v1/article/publish",
                        headers=headers,
                        json={"draft_id": draft_id},
                        timeout=30,
                    )
                    if publish_resp.status_code == 200:
                        pub_data = publish_resp.json()
                        article_url = f"https://juejin.cn/post/{pub_data.get('data', {}).get('article_id', draft_id)}"
                        return PublishResult(platform=self.name, success=True, url=article_url)

                return PublishResult(
                    platform=self.name,
                    success=True,
                    url=f"https://juejin.cn/draft/{draft_id}",
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

    def _resolve_tags(self, tags: list[str]) -> list[int]:
        """Map tag names to juejin tag IDs. This is a simplified mapping;
        in production you'd call the tag API to resolve dynamically."""
        tag_map = {
            "技术": 0, "前端": 1, "后端": 2, "AI": 3, "人工智能": 3,
            "Python": 4, "Java": 5, "Go": 6, "架构": 7, "性能优化": 8,
        }
        ids = []
        for t in tags[:5]:  # Max 5 tags
            tag_id = tag_map.get(t, 0)
            if tag_id:
                ids.append(tag_id)
        return ids or [0]

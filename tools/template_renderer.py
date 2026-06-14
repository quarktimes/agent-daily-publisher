"""
Template Renderer — Render structured JSON to perfectly-formatted articles.

Uses Jinja2 templates to produce:
  - Markdown (for Dev.to, 掘金, etc.)
  - MDNice-style HTML (for 微信公众号)

This replaces the LLM's free-form markdown generation. The LLM only
outputs structured content; the template handles 100% of the formatting.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, Template, TemplateNotFound

logger = logging.getLogger(__name__)

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")

TEMPLATE_MAP = {
    "devto": "article_markdown.j2",
    "juejin": "article_markdown.j2",
    "medium": "article_markdown.j2",
    "wechat_mp": "article_wechat.j2",
    "default": "article_markdown.j2",
}


class TemplateRenderer:
    """Render structured article data into formatted output."""

    def __init__(self, template_dir: str | None = None):
        self.template_dir = template_dir or TEMPLATE_DIR
        self.env = Environment(
            loader=FileSystemLoader(self.template_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._template_cache: dict[str, Template] = {}

    def render(self, article: dict[str, Any], platform: str = "default") -> str:
        """
        Render an article dict to formatted text for a given platform.

        Args:
            article: Structured article data (from Write Agent JSON output)
            platform: Target platform name (devto, wechat_mp, juejin, ...)

        Returns:
            Rendered markdown or HTML
        """
        template_name = TEMPLATE_MAP.get(platform, "article_markdown.j2")
        try:
            tmpl = self._get_template(template_name)
            return tmpl.render(**article)
        except Exception as e:
            logger.error(f"Template render failed for {platform}: {e}")
            raise

    def render_article_and_versions(self, article: dict[str, Any],
                                     platforms: list[str] | None = None) -> dict[str, Any]:
        """
        Render article for all target platforms.

        Returns the article dict enriched with rendered content for each platform.
        """
        if platforms is None:
            platforms = ["devto", "wechat_mp"]

        enriched = dict(article)
        enriched["versions"] = []

        for platform in platforms:
            try:
                rendered = self.render(article, platform)
                enriched["versions"].append({
                    "platform": platform,
                    "title": article.get("title", ""),
                    "content": rendered,
                    "tags": article.get("tags", []),
                    "language": "zh" if platform != "devto" else "en",
                })
                logger.info(f"  → Rendered for {platform}: {len(rendered)} chars")
            except Exception as e:
                logger.warning(f"  → Failed to render for {platform}: {e}")

        return enriched

    def _get_template(self, name: str) -> Template:
        """Get cached template."""
        if name not in self._template_cache:
            self._template_cache[name] = self.env.get_template(name)
        return self._template_cache[name]

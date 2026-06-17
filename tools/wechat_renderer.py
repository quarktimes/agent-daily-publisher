"""
WeChat Renderer — Convert Markdown to WeChat-compatible HTML via MD2WeChat.

Replaces the old _md_to_wechat_html() + MDNice template approach.
MD2WeChat handles: code blocks (Pygments), tables, blockquotes, lists.

Mermaid rendering is separate (mmdc → PNG → WeChat CDN).
"""

import os
import tempfile
import re
from pathlib import Path
from typing import Optional


class WeChatRenderer:
    """Render Markdown to WeChat-compatible HTML using MD2WeChat."""

    def __init__(self, style: str = "tech"):
        self.style = style
        self._converter = None

    def _get_converter(self):
        if self._converter is None:
            import sys
            sys.path.insert(0, str(Path(__file__).parent / "md2wechat"))
            from md2wechat import WeChatHTMLConverter
            self._converter = WeChatHTMLConverter(style=self.style)
        return self._converter

    def render(self, markdown_text: str, title: str = "", date: str = "") -> str:
        """
        Convert Markdown text to WeChat-compatible HTML.

        Args:
            markdown_text: Full article in Markdown
            title: Article title (for meta)
            date: Date string (for meta)

        Returns:
            WeChat-compatible HTML string
        """
        # Add YAML front matter that MD2WeChat expects
        if title:
            front_matter = f"---\ntitle: {title}\ndate: {date}\n---\n\n"
            full_md = front_matter + markdown_text
        else:
            full_md = markdown_text

        converter = self._get_converter()

        # MD2WeChat reads from file, write to temp
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(full_md)
            tmp_path = f.name

        try:
            html = converter.convert(tmp_path)
            return html
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def fix_mermaid_images(self, html: str, access_token: str) -> str:
        """
        Replace MD2WeChat-generated Mermaid base64 PNGs with WeChat CDN URLs.

        MD2WeChat renders Mermaid as base64-embedded PNGs. These are too large
        for WeChat. Instead, upload each PNG to WeChat's material API and
        replace with CDN URLs.
        """
        from tools.mermaid_renderer import mermaid_to_image, upload_to_wechat

        # Find base64 PNG images (MD2WeChat embeds them as <img src="data:image/png;base64,...">)
        pattern = re.compile(r'<img[^>]+src="data:image/png;base64,([^"]+)"[^>]*>')
        matches = pattern.findall(html)

        if not matches:
            return html

        print(f"  → Processing {len(matches)} Mermaid images...")
        result = html

        for i, b64_data in enumerate(matches):
            # Write base64 to temp PNG
            import base64
            png_data = base64.b64decode(b64_data)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(png_data)
                png_path = f.name

            try:
                media_id, img_url = upload_to_wechat(png_path, access_token)
                if media_id and img_url:
                    # Replace base64 img with CDN img
                    old_tag = f'<img src="data:image/png;base64,{b64_data}"'
                    new_tag = f'<img src="{img_url}" alt="Diagram {i+1}" style="width:100%;max-width:800px;border-radius:8px;"'
                    result = result.replace(old_tag, new_tag)
                    print(f"    Mermaid {i+1}: uploaded to WeChat CDN")
                else:
                    print(f"    Mermaid {i+1}: upload failed, keeping base64")
            finally:
                try:
                    os.unlink(png_path)
                except OSError:
                    pass

        return result

    def extract_digest(self, html: str, max_len: int = 100) -> str:
        """Extract plain text from HTML for digest."""
        plain = re.sub(r'<[^>]+>', '', html)
        plain = re.sub(r'\s+', ' ', plain).strip()
        return plain[:max_len]

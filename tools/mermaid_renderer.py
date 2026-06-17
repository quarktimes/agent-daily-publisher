"""
Mermaid Renderer — Convert Mermaid diagrams to PNG images for WeChat articles.

WeChat doesn't support Mermaid natively. This tool:
  1. Writes Mermaid source to a temp file
  2. Calls mermaid-cli (mmdc) to render PNG
  3. Uploads PNG to WeChat's permanent material
  4. Returns the media_id for embedding via <img>

Fallback: if mermaid-cli is not installed, returns None and caller
should display diagram source in <pre> block instead.
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def mermaid_to_image(mermaid_source: str, output_dir: str | None = None) -> str | None:
    """
    Convert Mermaid source to PNG image.

    Args:
        mermaid_source: The mermaid diagram source code
        output_dir: Where to save the PNG

    Returns:
        Path to generated PNG, or None if mermaid-cli unavailable
    """
    output_dir = output_dir or os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "covers"
    )
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Check if mmdc is available
    try:
        subprocess.run(["npx", "--yes", "@mermaid-js/mermaid-cli", "--version"],
                       capture_output=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None

    # Write mermaid source to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".mmd", delete=False) as f:
        f.write(mermaid_source)
        mmd_path = f.name

    # Output PNG
    import uuid
    png_filename = f"mermaid_{uuid.uuid4().hex[:8]}.png"
    png_path = os.path.join(output_dir, png_filename)

    try:
        result = subprocess.run(
            ["npx", "--yes", "@mermaid-js/mermaid-cli",
             "-i", mmd_path, "-o", png_path, "--outputFormat", "png",
             "-t", "neutral", "-w", "800", "-H", "500"],
            capture_output=True, timeout=30,
        )
        if result.returncode == 0 and os.path.exists(png_path):
            return png_path
        return None
    except Exception:
        return None
    finally:
        try:
            os.unlink(mmd_path)
        except OSError:
            pass


def upload_to_wechat(png_path: str, access_token: str) -> tuple[str | None, str | None]:
    """
    Upload a PNG image to WeChat permanent material.

    Returns:
        (media_id, image_url) - add_material returns both for images
    """
    import requests
    api_base = "https://api.weixin.qq.com/cgi-bin"

    with open(png_path, "rb") as f:
        resp = requests.post(
            f"{api_base}/material/add_material",
            params={"access_token": access_token, "type": "image"},
            files={"media": ("diagram.png", f, "image/png")},
            timeout=15,
        )
    data = resp.json()
    if data.get("media_id"):
        return data["media_id"], data.get("url")
    return None, None


def replace_mermaid_blocks_in_html(html_content: str, access_token: str) -> str:
    """
    Find all Mermaid diagrams in HTML, render each to image, upload to WeChat,
    and replace with <img> tags.

    Falls back to <pre> display if mmdc is unavailable.
    """
    pattern = re.compile(r'<pre[^>]*>\s*(graph\s+\w+|sequenceDiagram|stateDiagram|classDiagram|flowchart\s+\w+|gantt|pie|erDiagram)(.*?)</pre>',
                         re.DOTALL | re.IGNORECASE)

    def _replace(match):
        full_mermaid = match.group(1) + match.group(2)
        png_path = mermaid_to_image(full_mermaid)
        if png_path and access_token:
            media_id, img_url = upload_to_wechat(png_path, access_token)
            if media_id and img_url:
                return f'<img src="{img_url}" alt="Diagram" style="width:100%;max-width:800px;border-radius:8px;">'

        # Fallback: show as styled pre block
        return f'<pre style="background:#f8f9fa;padding:15px;border-radius:8px;font-size:12px;overflow-x:auto;">{full_mermaid}</pre>'

    return pattern.sub(_replace, html_content)

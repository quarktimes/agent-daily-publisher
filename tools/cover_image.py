"""
Cover Image Generator — Tech-blog-style OG/thumbnail images.

Generates 1200x630 PNG with:
  - Dynamic color palette based on article tags
  - Geometric decorative elements (bars, circles)
  - Large title with auto text wrapping
  - Tag badges and date footer
  - No external dependencies beyond PIL

Color themes per tag keyword:
  AI/Agent/LLM/MCP/RAG → Indigo (blue-purple)
  Backend/API/Database  → Teal (green-blue)
  Frontend/Flutter/CSS  → Orange
  Architecture/System   → Slate (cool gray)
  Default               → Dark slate
"""

import io
import os
import re
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

W, H = 1200, 630

# Color themes — each is (primary, primary_dark, accent, bg_start, bg_end, tag_bg, tag_text)
THEMES = {
    "indigo": {
        "primary": (79, 70, 229), "primary_dark": (49, 46, 129),
        "accent": (165, 180, 252), "accent2": (129, 140, 248),
        "bg_start": (15, 23, 42), "bg_end": (30, 41, 59),
        "tag_bg": (79, 70, 229), "tag_text": (199, 210, 254),
        "circle": (129, 140, 248),
    },
    "teal": {
        "primary": (5, 150, 105), "primary_dark": (6, 95, 70),
        "accent": (110, 231, 183), "accent2": (52, 211, 153),
        "bg_start": (2, 44, 34), "bg_end": (6, 78, 59),
        "tag_bg": (5, 150, 105), "tag_text": (167, 243, 208),
        "circle": (52, 211, 153),
    },
    "orange": {
        "primary": (234, 88, 12), "primary_dark": (154, 52, 18),
        "accent": (251, 191, 36), "accent2": (251, 146, 60),
        "bg_start": (39, 20, 10), "bg_end": (69, 39, 16),
        "tag_bg": (234, 88, 12), "tag_text": (254, 215, 170),
        "circle": (251, 146, 60),
    },
    "slate": {
        "primary": (71, 85, 105), "primary_dark": (30, 41, 59),
        "accent": (148, 163, 184), "accent2": (100, 116, 139),
        "bg_start": (15, 23, 42), "bg_end": (30, 41, 59),
        "tag_bg": (71, 85, 105), "tag_text": (203, 213, 225),
        "circle": (100, 116, 139),
    },
    "blue": {
        "primary": (37, 99, 235), "primary_dark": (30, 64, 175),
        "accent": (147, 197, 253), "accent2": (96, 165, 250),
        "bg_start": (12, 25, 60), "bg_end": (23, 37, 84),
        "tag_bg": (37, 99, 235), "tag_text": (191, 219, 254),
        "circle": (96, 165, 250),
    },
}


def _pick_theme(tags: list[str] | None) -> dict:
    """Pick color theme based on article tags."""
    text = " ".join(tags or []).lower()
    if any(w in text for w in ["ai", "agent", "llm", "mcp", "rag", "tool calling"]):
        return THEMES["indigo"]
    if any(w in text for w in ["backend", "api", "database", "sql", "server"]):
        return THEMES["teal"]
    if any(w in text for w in ["frontend", "flutter", "css", "react", "vue"]):
        return THEMES["orange"]
    if any(w in text for w in ["architecture", "system", "design", "pipeline"]):
        return THEMES["slate"]
    return THEMES["indigo"]


def _get_font(size: int, bold: bool = False):
    """Get font with fallback."""
    paths = [
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _draw_gradient(draw: ImageDraw, colors: tuple):
    """Vertical gradient fill."""
    for y in range(H):
        r = colors["bg_start"][0] + (colors["bg_end"][0] - colors["bg_start"][0]) * y // H
        g = colors["bg_start"][1] + (colors["bg_end"][1] - colors["bg_start"][1]) * y // H
        b = colors["bg_start"][2] + (colors["bg_end"][2] - colors["bg_start"][2]) * y // H
        draw.rectangle([(0, y), (W, y + 1)], fill=(r, g, b))


def _draw_decorations(img, draw, colors: dict):
    """Add geometric decorative elements."""
    # Left accent bars
    for i, c in enumerate([colors["primary"], colors["accent2"], colors["accent"]]):
        x = 36 + i * 6
        draw.rectangle([(x, 50), (x + 4, H - 50)], fill=c)

    # Semi-transparent circles on the right
    for cx, cy, r in [(980, 140, 180), (1080, 480, 130), (820, 350, 90)]:
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.ellipse([(cx - r, cy - r), (cx + r, cy + r)],
                    fill=colors["circle"] + (25,))
        img_d = img.convert("RGBA")
        img_d = Image.alpha_composite(img_d, overlay)
        # Copy back to original
        img.paste(img_d.convert("RGB"))
        draw = ImageDraw.Draw(img)

    return draw


def generate_cover(title: str, date_str: str | None = None,
                   tags: list[str] | None = None,
                   output_dir: str | None = None) -> str | None:
    """Generate a cover image. Returns path to PNG."""
    if not HAS_PIL:
        return None
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "covers")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    theme = _pick_theme(tags)
    img = Image.new("RGB", (W, H), theme["bg_start"])
    draw = ImageDraw.Draw(img)

    _draw_gradient(draw, theme)
    draw = _draw_decorations(img, draw, theme)

    # Tag badge
    tag_display = (tags or ["tech"])[0]
    if len(tag_display) > 18:
        tag_display = tag_display[:18]
    tag_font = _get_font(16)
    tw = len(tag_display) * 10 + 28
    tx, ty = 56, 70
    draw.rounded_rectangle([(tx, ty), (tx + tw, ty + 28)], radius=14, fill=theme["tag_bg"])
    draw.text((tx + 14, ty + 6), tag_display, fill=theme["tag_text"], font=tag_font)

    # Title
    safe_title = re.sub(r'[^\w\s一-鿿\-：，。！？、]', '', title)[:60]
    title_font = _get_font(46, bold=True)
    title_font_m = _get_font(36, bold=True)
    lines = textwrap.wrap(safe_title, width=16)
    if len(lines) > 3:
        lines = lines[:3]
    if len(lines) > 2:
        title_font = title_font_m
        lines = textwrap.wrap(safe_title, width=20)[:3]

    y = 140
    for line in lines:
        draw.text((56, y), line, fill=(255, 255, 255), font=title_font)
        y += 56 if title_font.size > 40 else 44

    # Subtitle = second tag (optional)
    if tags and len(tags) > 1:
        sub = tags[1]
        sub_font = _get_font(20)
        draw.text((56, y + 12), sub, fill=theme["accent"], font=sub_font)

    # Bottom bar
    bar_y = H - 50
    draw.rectangle([(0, bar_y), (W, bar_y + 4)], fill=theme["primary"])



    # Save
    safe_fn = re.sub(r'[^\w\-]', '_', safe_title[:30]).strip('_') or "cover"
    fp = os.path.join(output_dir, f"{date_str}_{safe_fn}.png")
    img.save(fp, "PNG")
    return fp

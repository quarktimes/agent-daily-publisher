"""
Cover Image Generator — Create OG/thumbnail images for articles.

Generates a tech-blog-style cover card with:
  - Dark gradient background (tech aesthetic)
  - Article title overlaid in white
  - Date and platform badges
  - Code-themed decorative elements

Used for: Dev.to social preview, WeChat MP thumbnails, article header images.
"""

import io
import os
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# Default colors — dark theme like Hashnode/Dev.to
COLORS = {
    "bg_start": (30, 30, 60),       # Dark navy
    "bg_end": (10, 10, 40),         # Almost black
    "text_primary": (255, 255, 255),
    "text_secondary": (180, 190, 210),
    "accent": (100, 180, 255),       # Blue accent
    "code_bg": (50, 50, 80),         # Slightly lighter dark
    "border": (60, 70, 100),
}

# Image dimensions (OG standard)
WIDTH = 1200
HEIGHT = 630


def generate_cover(title: str, date_str: str | None = None, tags: list[str] | None = None,
                   output_dir: str | None = None) -> str | None:
    """
    Generate a cover image for an article.

    Args:
        title: Article title
        date_str: Date string (YYYY-MM-DD)
        tags: List of tag strings
        output_dir: Directory to save the image (default: data/covers)

    Returns:
        Path to generated image, or None if PIL unavailable
    """
    if not HAS_PIL:
        return None

    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    if output_dir is None:
        output_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "covers"
        )
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Create gradient background
    img = Image.new("RGB", (WIDTH, HEIGHT), COLORS["bg_start"])
    draw = ImageDraw.Draw(img)

    # Gradient fill
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        r = int(COLORS["bg_start"][0] + (COLORS["bg_end"][0] - COLORS["bg_start"][0]) * ratio)
        g = int(COLORS["bg_start"][1] + (COLORS["bg_end"][1] - COLORS["bg_start"][1]) * ratio)
        b = int(COLORS["bg_start"][2] + (COLORS["bg_end"][2] - COLORS["bg_start"][2]) * ratio)
        draw.rectangle([(0, y), (WIDTH, y + 1)], fill=(r, g, b))

    # --- Decorative code-like pattern in background ---
    font_code = _get_font(14)
    code_lines = [
        "def build_agent():",
        "    pipeline = Pipeline()",
        "    pipeline.add(ReActLoop(max_retries=3))",
        "    pipeline.add(JudgeAgent(threshold=80))",
        "    return pipeline.deploy()",
        "",
        "# Agent Daily Publisher",
        f"# {date_str}",
    ]
    y_start = HEIGHT - 20 - len(code_lines) * 18
    for i, line in enumerate(code_lines):
        y = y_start + i * 18
        if y > 0:
            draw.text((30, y), line, fill=COLORS["code_bg"], font=font_code)

    # --- Accent line ---
    draw.rectangle([(50, 200), (200, 204)], fill=COLORS["accent"])

    # --- Tag badges ---
    if tags:
        font_tag = _get_font(16)
        x = 50
        for tag in tags[:4]:
            tag_text = f"#{tag}"
            bbox = draw.textbbox((0, 0), tag_text, font=font_tag)
            tw = bbox[2] - bbox[0] + 20
            th = bbox[3] - bbox[1] + 10
            draw.rounded_rectangle([(x, 70), (x + tw, 70 + th)], radius=6,
                                   fill=COLORS["code_bg"], outline=COLORS["border"], width=1)
            draw.text((x + 10, 75), tag_text, fill=COLORS["accent"], font=font_tag)
            x += tw + 10

    # --- Date ---
    font_date = _get_font(18)
    draw.text((50, 115), date_str, fill=COLORS["text_secondary"], font=font_date)

    # --- Title ---
    font_title = _get_font(40, bold=True)
    font_title_small = _get_font(32, bold=True)

    # Wrap title to fit
    title_lines = _wrap_title(title, font_title if len(title) <= 30 else font_title_small, max_width=WIDTH - 100)
    y_title = 170
    for line in title_lines:
        draw.text((50, y_title), line, fill=COLORS["text_primary"],
                  font=font_title if len(line) <= 25 else font_title_small)
        y_title += 55 if font_title else 45

    # --- Bottom bar ---
    draw.rectangle([(0, HEIGHT - 4), (WIDTH, HEIGHT)], fill=COLORS["accent"])

    # --- Source watermark ---
    font_wm = _get_font(14)
    draw.text((50, HEIGHT - 30), "Agent Daily Publisher", fill=COLORS["text_secondary"], font=font_wm)

    # Save
    safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title[:30])
    filename = f"{date_str}_{safe_title}.png"
    filepath = os.path.join(output_dir, filename)
    img.save(filepath, "PNG")
    return filepath


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Get a font, falling back to default if system font unavailable."""
    font_paths = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/SFNSText.ttf",
    ]
    if bold:
        font_paths = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/SFNSText.ttf",
        ]

    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap_title(title: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Smart wrap title to fit image width, preserving Chinese character boundaries."""
    # For CJK text, each char is roughly the same width
    # For mixed CJK + ASCII, estimate widths
    lines = []
    current = ""
    for char in title:
        test = current + char
        # Rough width estimate: CJK ~ font.size, ASCII ~ font.size * 0.6
        width = sum(font.size if ord(c) > 127 else font.size * 0.6 for c in test)
        if width > max_width and current:
            lines.append(current)
            current = char
        else:
            current = test
    if current:
        lines.append(current)
    return lines[:4]  # Max 4 lines


def generate_and_return_bytes(title: str, date_str: str | None = None,
                               tags: list[str] | None = None) -> io.BytesIO | None:
    """Generate cover and return as in-memory bytes (for API uploads)."""
    path = generate_cover(title, date_str, tags)
    if not path:
        return None
    buf = io.BytesIO()
    with open(path, "rb") as f:
        buf.write(f.read())
    buf.seek(0)
    return buf

"""Generate Git Manager application icon.

Creates a tech-style icon with gradient background and "GM" text.
Exports as multi-size .ico and .png files.

File Name: generate_icon.py
Author: hang.shi
Time: 2026-05-04
Version: 1
Description: Generate Git Manager app icon with tech-style design
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def create_icon(size: int) -> Image.Image:
    """Create a single icon image at the given size."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # --- Gradient background (deep navy → electric cyan) ---
    for y in range(size):
        ratio = y / max(size - 1, 1)
        r = int(10 + ratio * 0)
        g = int(25 + ratio * 180)
        b = int(60 + ratio * 200)
        draw.line([(0, y), (size - 1, y)], fill=(r, g, b, 255))

    # --- Rounded rectangle mask ---
    radius = max(size // 8, 2)
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle(
        [(0, 0), (size - 1, size - 1)],
        radius=radius,
        fill=255,
    )
    img.putalpha(mask)

    # --- Geometric tech pattern (subtle circuit lines) ---
    line_color = (0, 220, 255, 40)
    grid_step = max(size // 8, 4)
    for i in range(0, size, grid_step):
        draw.line([(i, 0), (i, size)], fill=line_color, width=1)
        draw.line([(0, i), (size, i)], fill=line_color, width=1)

    # Accent lines
    accent = (0, 220, 255, 80)
    cx, cy = size // 2, size // 2
    r_line = int(size * 0.38)
    draw.arc(
        [cx - r_line, cy - r_line, cx + r_line, cy + r_line],
        start=200, end=340, fill=accent, width=max(size // 32, 1),
    )
    draw.arc(
        [cx - r_line, cy - r_line, cx + r_line, cy + r_line],
        start=20, end=160, fill=accent, width=max(size // 32, 1),
    )

    # Small dots at corners
    dot_r = max(size // 40, 1)
    for dx, dy in [(0.2, 0.2), (0.8, 0.2), (0.2, 0.8), (0.8, 0.8)]:
        px, py = int(size * dx), int(size * dy)
        draw.ellipse(
            [px - dot_r, py - dot_r, px + dot_r, py + dot_r],
            fill=(0, 220, 255, 120),
        )

    # --- "GM" text ---
    font_size = int(size * 0.42)
    try:
        font = ImageFont.truetype("consola.ttf", font_size)
    except OSError:
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()

    text = "GM"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (size - tw) // 2
    ty = (size - th) // 2 - bbox[1]

    # Shadow
    draw.text((tx + 1, ty + 1), text, fill=(0, 0, 0, 100), font=font)
    # Main text
    draw.text((tx, ty), text, fill=(255, 255, 255, 240), font=font)

    return img


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    out_dir = project_root / "git_manager"
    out_dir.mkdir(exist_ok=True)

    sizes = [16, 32, 48, 64, 128, 256]
    images = [create_icon(s) for s in sizes]

    # Save .ico (multi-size)
    ico_path = out_dir / "git_manager.ico"
    images[0].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )
    print(f"Created: {ico_path}")

    # Save .png (256px for tkinter)
    png_path = out_dir / "git_manager.png"
    images[-1].save(png_path, format="PNG")
    print(f"Created: {png_path}")


if __name__ == "__main__":
    main()

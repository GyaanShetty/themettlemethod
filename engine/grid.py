"""Grid puzzle: one 3240x4320 master cut into nine 1080x1440 covers that rebuild it on the profile grid.

Instagram puts the newest post top-left and fills each row left to right. So the first post made
ends up bottom-right, and the ninth ends up top-left.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps

from . import brand

W, H, COLS, ROWS = 1080, 1440, 3, 3


def master(out: Path) -> Path:
    """The seal on ink, whole and uncropped, with nothing over it."""
    canvas = Image.new("RGB", (W * COLS, H * ROWS), brand.color("paper", "ink"))
    seal = Image.open(brand.ROOT / "web" / "assets" / "seal.png").convert("RGBA")
    size = int(W * COLS * 0.82)
    seal = seal.resize((size, size), Image.LANCZOS)
    white = Image.new("RGBA", seal.size, brand.color("ink", "ink"))
    ink_parts = ImageOps.invert(seal.convert("RGB")).convert("L")          # black line art becomes the light part
    white.putalpha(Image.composite(ink_parts, Image.new("L", seal.size, 0), seal.getchannel("A")))
    canvas.paste(white, ((W * COLS - size) // 2, (H * ROWS - size) // 2), white)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return out


def split(master_png: Path, out: Path) -> list[Path]:
    """Cut the master and name the tiles in posting order: post-01 is posted first."""
    im = Image.open(master_png)
    if im.size != (W * COLS, H * ROWS):
        raise ValueError(f"master is {im.size}, expected {(W * COLS, H * ROWS)}")
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for post in range(1, COLS * ROWS + 1):
        row, col = divmod(COLS * ROWS - post, COLS)      # where this post will sit once all nine are up
        f = out / f"post-{post:02d}.png"
        im.crop((col * W, row * H, (col + 1) * W, (row + 1) * H)).save(f)
        files.append(f)
    return files


def as_profile_shows(files: list[Path]) -> Image.Image:
    """Rebuild the grid the way the profile shows it, newest first. Used to check the split."""
    grid = Image.new("RGB", (W * COLS, H * ROWS))
    for i, f in enumerate(reversed(files)):
        row, col = divmod(i, COLS)
        grid.paste(Image.open(f), (col * W, row * H))
    return grid

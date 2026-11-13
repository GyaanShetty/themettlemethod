"""Still renderers: plate, story, carousel and product covers. Each is a pure function from an
atom to PNG files, drawn by the shared brand template and checked for overflow before it is saved."""
from __future__ import annotations

import hashlib
import json
import re
from contextlib import contextmanager
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup, escape

from . import brand
from .atoms import Atom, image_path

TPL_DIR = Path(__file__).parent / "templates" / "brand"
TPL = Environment(loader=FileSystemLoader(TPL_DIR), autoescape=True)
OUT = brand.ROOT / "build" / "social"
SEAL = brand.ROOT / "web" / "assets" / "seal.png"
HEADLINE = brand.tokens()["plate"]["headline"]


class RenderError(RuntimeError):
    pass


@contextmanager
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        try:
            yield b
        finally:
            b.close()


def _label(a: Atom) -> str:
    return f"PILLAR {brand.PILLARS[a.pillar]} · {a.pillar.upper()}"


def _shot(b, out: Path, name: str, w: int, h: int, sizes, **ctx) -> Path:
    html = TPL.get_template("social.html").render(
        brand_css=brand.css(ctx.get("theme", "ink")), css=(TPL_DIR / "social.css").read_text(),
        w=w, h=h, seal=SEAL.as_uri(), theme=ctx.pop("theme", "ink"), **ctx)
    out.mkdir(parents=True, exist_ok=True)
    src = out / f"{name}.html"
    src.write_text(html, encoding="utf-8")
    page = b.new_page(viewport={"width": w, "height": h})
    try:
        page.goto(src.as_uri())
        res = page.evaluate("s => window.check(s)", sizes)
        if res["errs"]:
            raise RenderError(f"{name}: " + "; ".join(res["errs"]))
        png = out / f"{name}.png"
        page.screenshot(path=str(png), clip={"x": 0, "y": 0, "width": w, "height": h})
    finally:
        page.close()
    src.unlink()
    return png


def _ctx(a: Atom) -> dict:
    return {"a": a, "label": _label(a), "numeral": brand.roman(a.number) if a.number else "",
            "image": image_path(a.image).as_uri(),
            "headline_html": Markup("<br>").join(escape(line) for line in a.headline.split("\n"))}


def _lead(a: Atom, limit: int = 260) -> str:
    """First paragraph of the body, cut at a sentence end."""
    para = next((p for p in a.body.split("\n\n") if p.strip() and not p.lstrip().startswith(("#", "-", "*"))), a.sub)
    para = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", " ".join(para.split()))  # links to their text
    para = re.sub(r"[*_`]", "", para)
    if len(para) <= limit:
        return para
    cut = para[:limit].rsplit(". ", 1)[0]
    return cut + "."


def plate(b, a: Atom, theme: str = "ink") -> list[Path]:
    return [_shot(b, OUT / a.id, "plate", 1080, 1350, HEADLINE, kind="plate", win=540, theme=theme, **_ctx(a))]


def story(b, a: Atom) -> list[Path]:
    return [_shot(b, OUT / a.id, "story", 1080, 1920, HEADLINE, kind="story", win=760, pad_y=250, **_ctx(a))]


def carousel(b, a: Atom) -> list[Path]:
    c, d = _ctx(a), OUT / a.id
    return [
        _shot(b, d, "carousel-1", 1080, 1440, HEADLINE, kind="cover", win=630, **c),
        _shot(b, d, "carousel-2", 1080, 1440, None, kind="slide-image", **c),
        _shot(b, d, "carousel-3", 1080, 1440, None, kind="slide-text", theme="paper", lead=_lead(a), **c),
        _shot(b, d, "carousel-4", 1080, 1440, None, kind="slide-end", **c),
    ]


def product_cover(b, slug: str, name: str, kicker: str, sub: str) -> list[Path]:
    p, d = {"name": name, "kicker": kicker, "sub": sub}, OUT / "products" / slug
    return [_shot(b, d, "cover-1280x720", 1280, 720, None, kind="product", theme="paper", p=p),
            _shot(b, d, "thumb-600x600", 600, 600, None, kind="product", theme="paper", p=p)]


RENDERERS = {"instagram_plate": plate, "instagram_story": story, "instagram_carousel": carousel}


def render_atom(a: Atom, b=None) -> dict:
    """Render every still the atom's channels ask for and write a manifest of file hashes."""
    def run(br):
        files = [f for ch, fn in RENDERERS.items() if ch in a.channels for f in fn(br, a)]
        manifest = {"atom": a.id, "files": {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
        (OUT / a.id / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        return manifest
    if b is not None:
        return run(b)
    with browser() as br:
        return run(br)

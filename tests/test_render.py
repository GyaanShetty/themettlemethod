"""Every still is rendered, measured in the browser for overflow and overlap, and compared with a golden image."""
import os
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageStat

from engine import atoms, brand, social

GOLDEN = Path(__file__).parent / "golden"
SIZES = {"plate": (1080, 1350), "story": (1080, 1920), "carousel-1": (1080, 1440), "carousel-2": (1080, 1440),
         "carousel-3": (1080, 1440), "carousel-4": (1080, 1440)}


def _small(path):
    im = Image.open(path).convert("RGB")
    return im.resize((270, round(im.height * 270 / im.width)), Image.LANCZOS)


def _matches_golden(path, name):
    got, ref = _small(path), GOLDEN / f"{name}.png"
    if os.environ.get("UPDATE_GOLDEN") or not ref.exists():
        got.save(ref)
        return
    diff = ImageStat.Stat(ImageChops.difference(got, Image.open(ref).convert("RGB"))).mean
    assert max(diff) < 4.0, f"{name} drifted from its golden image (mean difference {max(diff):.1f})"


@pytest.mark.parametrize("atom", atoms.all_atoms(), ids=lambda a: a.id)
def test_every_atom_renders_without_overflow(browser, atom):
    manifest = social.render_atom(atom, browser)
    for name in manifest["files"]:
        w, h = SIZES[name.removesuffix(".png")]
        assert Image.open(social.OUT / atom.id / name).size == (w, h)


def test_golden_images(browser):
    a = atoms.get("second-order-thinking")
    social.render_atom(a, browser)
    for name in SIZES:
        _matches_golden(social.OUT / a.id / f"{name}.png", name)
    paper = social.plate(browser, a.model_copy(update={"id": "golden-paper"}), theme="paper")[0]
    _matches_golden(paper, "plate-paper")
    for f in social.product_cover(browser, "golden", "Decision Journal", "Notion template", "Write the decision down first."):
        _matches_golden(f, f.stem)


def test_headline_that_cannot_fit_fails_the_build(browser):
    a = atoms.get("inversion").model_construct(**{**atoms.get("inversion").model_dump(),
                                                 "id": "too-long", "headline": "A headline that keeps going well past the three lines a plate allows, clause after clause, without ever reaching its full stop in time."})
    with pytest.raises(social.RenderError, match="headline|overflow"):
        social.plate(browser, a)


def test_sub_that_overflows_fails_the_build(browser):
    a = atoms.get("inversion").model_construct(**{**atoms.get("inversion").model_dump(), "id": "too-tall", "sub": "word " * 220})
    with pytest.raises(social.RenderError, match="overflow"):
        social.plate(browser, a)


def _lum(hex_):
    c = [int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


@pytest.mark.parametrize("theme", ["ink", "paper"])
@pytest.mark.parametrize("fg,bg", [("ink", "paper"), ("ink-muted", "paper"), ("oxblood", "paper"), ("brass", "paper"),
                                   ("ink", "paper-raised"), ("ink-muted", "paper-raised"), ("on-oxblood", "oxblood")])
def test_text_contrast_is_at_least_4_5(theme, fg, bg):
    a, b = sorted((_lum(brand.color(fg, theme)), _lum(brand.color(bg, theme))), reverse=True)
    assert (a + 0.05) / (b + 0.05) >= 4.5

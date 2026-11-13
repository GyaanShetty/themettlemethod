import os
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from engine import atoms, grid, text


@pytest.mark.parametrize("atom", atoms.all_atoms(), ids=lambda a: a.id)
def test_thread_is_three_to_five_lines(atom):
    t = text.thread(atom)
    assert 3 <= len(t.split("\n\n")) <= 5 and len(t) <= 500 and "!" not in t and "*" not in t


@pytest.mark.parametrize("atom", atoms.all_atoms(), ids=lambda a: a.id)
def test_email_has_html_text_and_one_click_stop(atom):
    e = text.email(atom, "https://example.org")
    assert "{{unsubscribe_url}}" in e["html"] and "{{unsubscribe_url}}" in e["text"]
    assert atom.headline.split("\n")[0] in e["html"] and "free" in e["text"]
    assert "gradient" not in e["html"] and "monospace" not in e["html"]


def test_grid_puzzle_rebuilds_the_master(tmp_path):
    m = grid.master(tmp_path / "master.png")
    files = grid.split(m, tmp_path / "tiles")
    assert [f.name for f in files] == [f"post-{i:02d}.png" for i in range(1, 10)]
    assert not ImageChops.difference(grid.as_profile_shows(files), Image.open(m)).getbbox()
    # the first post is the bottom-right tile
    assert not ImageChops.difference(Image.open(files[0]), Image.open(m).crop((2160, 2880, 3240, 4320))).getbbox()


def test_reel_stills_render_in_the_brand(monkeypatch):
    monkeypatch.setenv("TTS_ENGINE", "silent")
    from engine import reel
    sheet = reel.render("inversion", preview=True)
    assert Path(sheet).exists()
    html = (Path(sheet).parent / "s00.html").read_text()
    assert "Marcellus" in html and "Fraunces" not in html and "gradient" not in html

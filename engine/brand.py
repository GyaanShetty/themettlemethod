"""The brand in one place. Every renderer gets its colours and fonts from brand/tokens.json."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "brand"
PILLARS = {"mind": "I", "body": "II", "faith": "III", "relationships": "IV"}


@lru_cache
def tokens() -> dict:
    return json.loads((BRAND / "tokens.json").read_text(encoding="utf-8"))


def color(name: str, theme: str = "ink") -> str:
    return tokens()["color"][name][theme]


def roman(n: int) -> str:
    out = ""
    for v, s in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
                 (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= v:
            out, n = out + s, n - v
    return out


def css(theme: str = "ink") -> str:
    """Font faces and custom properties for one theme. Fonts are local files, so renders never depend on the network."""
    t = tokens()
    faces = []
    for role, f in t["font"].items():
        for weight, file in f["files"].items():
            faces.append(f"@font-face{{font-family:'{f['family']}';font-weight:{weight};font-style:normal;"
                         f"src:url('{(BRAND / 'fonts' / file).as_uri()}') format('woff2')}}")
    props = [f"--{k}:{v[theme]}" for k, v in t["color"].items()]
    props += [f"--font-{role}:'{f['family']}'" for role, f in t["font"].items()]
    return "\n".join(faces) + "\n:root{" + ";".join(props) + "}"

"""Config and content atoms.

A content atom (content/models/<slug>.yaml) is one mental model. The engine turns each atom
into a reel (Instagram + YouTube Shorts), a page on the website, and a card in the derived products.
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "content" / "models"
LAYOUTS = {"hook", "title", "statement", "list", "versus", "quote", "cta"}
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class ContentError(ValueError):
    pass


def config() -> dict:
    cfg = yaml.safe_load((ROOT / "engine.yaml").read_text(encoding="utf-8"))
    from . import brand  # colours come from the brand tokens, never from this file
    cfg["brand"]["colors"] = {"bg": brand.color("paper"), "surface": brand.color("paper-raised"), "ink": brand.color("ink"),
                              "muted": brand.color("ink-muted"), "accent": brand.color("oxblood")}
    return cfg


def load_model(slug_or_path: str | Path) -> dict:
    p = Path(slug_or_path)
    if not p.suffix:
        p = MODELS / f"{slug_or_path}.yaml"
    m = yaml.safe_load(p.read_text(encoding="utf-8"))
    validate_model(m, p.stem)
    return m


TRACK_KEYS = {"concepts": [], "skills": ["level", "time_to_learn", "steps"]}


def tracks() -> dict:
    return config().get("tracks", {"models": {"label": "Mental models", "blurb": ""}})


def load_item(track: str, path: Path) -> dict:
    if track == "models":
        return load_model(path)
    it = yaml.safe_load(path.read_text(encoding="utf-8"))
    errs = [f"missing {k}" for k in ("slug", "title", "category", "publish_on", "summary", "article") + tuple(TRACK_KEYS.get(track, [])) if k not in it]
    if not errs and (it["slug"] != path.stem or not SLUG_RE.match(it["slug"])):
        errs.append("slug must be kebab-case and match the filename")
    if not errs and not isinstance(it["publish_on"], dt.date):
        errs.append("publish_on must be a date")
    if not errs and len(it["article"].split()) < 150:
        errs.append("article under 150 words")
    if errs:
        raise ContentError("; ".join(errs))
    return it


def all_items(track: str) -> list[dict]:
    d = ROOT / "content" / track
    return sorted((load_item(track, p) for p in d.glob("*.yaml")), key=lambda i: (i["publish_on"], i["slug"]))


def all_models() -> list[dict]:
    return sorted((load_model(p) for p in MODELS.glob("*.yaml")), key=lambda m: m["number"])


def segments(scene: dict) -> list[str]:
    """The spoken lines of a scene, in order. A list scene speaks its intro then each item;
    a versus scene speaks left then right when both are given."""
    segs = []
    if scene.get("say"):
        segs.append(scene["say"])
    if scene["layout"] == "list":
        segs += [i["say"] for i in scene["items"] if i.get("say")]
    if scene["layout"] == "versus":
        segs += [s["say"] for s in (scene["left"], scene["right"]) if s.get("say")]
    return segs


def word_count(m: dict) -> int:
    return sum(len(s.split()) for sc in m["scenes"] for s in segments(sc))


def validate_model(m: dict, stem: str) -> None:
    errs = []
    for k in ("slug", "number", "title", "category", "publish_on", "summary", "scenes", "caption", "tags", "article"):
        if k not in m:
            errs.append(f"missing {k}")
    if errs:
        raise ContentError("; ".join(errs))
    if m["slug"] != stem or not SLUG_RE.match(m["slug"]):
        errs.append(f"slug '{m['slug']}' must be kebab-case and match the filename '{stem}'")
    if not isinstance(m["publish_on"], dt.date):
        errs.append("publish_on must be a date like 2026-11-03")
    sc = m["scenes"]
    if not sc or sc[0]["layout"] != "hook":
        errs.append("first scene must be a hook")
    if sc and sc[-1]["layout"] != "cta":
        errs.append("last scene must be a cta")
    for i, s in enumerate(sc):
        lay = s.get("layout")
        if lay not in LAYOUTS:
            errs.append(f"scene {i}: unknown layout {lay}")
            continue
        if not segments(s):
            errs.append(f"scene {i}: nothing to say")
        if lay in ("hook", "statement", "quote") and not s.get("text"):
            errs.append(f"scene {i}: {lay} needs text")
        if lay == "list" and not (2 <= len(s.get("items", [])) <= 5):
            errs.append(f"scene {i}: list needs 2-5 items")
        if lay == "versus" and not (s.get("left") and s.get("right")):
            errs.append(f"scene {i}: versus needs left and right")
        for key in ("text", "title"):
            if s.get(key) and len(s[key]) > 90:
                errs.append(f"scene {i}: {key} too long for the screen ({len(s[key])} > 90 chars)")
    words = word_count(m) if not errs else 0
    if words and not 60 <= words <= 170:
        errs.append(f"script is {words} words; aim for 70-150 (about 30-60 seconds)")
    if len(m["caption"]) > 2000:
        errs.append("caption over 2000 chars")
    if errs:
        raise ContentError("\n".join(errs))

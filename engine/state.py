"""state.json: what has been posted, built and shipped. Committed back to the repo by CI."""
from __future__ import annotations

import datetime as dt
import json

from .content import ROOT, all_models

PATH = ROOT / "state.json"


def load() -> dict:
    s = json.loads(PATH.read_text()) if PATH.exists() else {}
    s.setdefault("posts", {})
    s.setdefault("products", {})
    return s


def save(s: dict) -> None:
    PATH.write_text(json.dumps(s, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def platforms(cfg: dict) -> list[str]:
    return [p for p in ("youtube", "instagram") if cfg["publish"].get(p)]


def due(day: dt.date) -> list[str]:
    from .content import config
    s, want = load(), platforms(config())
    out = []
    for m in all_models():
        if m["publish_on"] > day:
            continue
        done = s["posts"].get(m["slug"], {})
        if any(p not in done for p in want):
            out.append(m["slug"])
    return out


def report() -> None:
    s = load()
    print("REELS")
    for m in all_models():
        p = s["posts"].get(m["slug"], {})
        marks = " ".join(f"{k}:{'✓' if k in p else '·'}" for k in ("youtube", "instagram"))
        print(f"  {m['number']:>3}  {m['publish_on']}  {m['slug']:<28} {marks}")
    print("PRODUCTS")
    for slug, e in sorted(s["products"].items()):
        print(f"  {slug:<32} {e.get('status')}")

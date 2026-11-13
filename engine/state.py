"""state.json: what has been posted, built and shipped. Committed back to the repo by CI."""
from __future__ import annotations

import datetime as dt
import json

from .content import ROOT

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


def report() -> None:
    s = load()
    print("ATOMS")
    for slug, chans in sorted(s["posts"].items()):
        print(f"  {slug:<28} " + " ".join(f"{c}:{v.get('status')}" for c, v in sorted(chans.items())))
    print("PRODUCTS")
    for slug, e in sorted(s["products"].items()):
        print(f"  {slug:<32} {e.get('status')}")

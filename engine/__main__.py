"""engine CLI

  python -m engine validate                 check every content atom and product spec
  python -m engine preview <slug>           stills of each scene (fast look before a full render)
  python -m engine reel <slug>              render build/reels/<slug>.mp4
  python -m engine due [--date YYYY-MM-DD]  slugs due to post that haven't been posted
  python -m engine post <slug> [--dry-run]  render if needed, upload to YouTube + Instagram
  python -m engine site                     build the website into build/site
  python -m engine product <cmd> ...        products: validate | build | ship | reject  (see products.py)
  python -m engine status                   what's queued, posted, built and shipped
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys

from . import content


def cmd_validate(a) -> int:
    bad = 0
    for p in sorted(content.MODELS.glob("*.yaml")):
        try:
            m = content.load_model(p)
            print(f"ok   model {p.stem}: {len(m['scenes'])} scenes, {content.word_count(m)} words, posts {m['publish_on']}")
        except Exception as e:  # noqa: BLE001
            bad += 1
            print(f"FAIL model {p.stem}\n  " + str(e).replace("\n", "\n  "))
    for tr in content.tracks():
        if tr == "models":
            continue
        for p in sorted((content.ROOT / "content" / tr).glob("*.yaml")):
            try:
                it = content.load_item(tr, p)
                print(f"ok   {tr[:-1]} {p.stem}: live {it['publish_on']}")
            except Exception as e:  # noqa: BLE001
                bad += 1
                print(f"FAIL {tr[:-1]} {p.stem}: {e}")
    nums = [content.load_model(p)["number"] for p in content.MODELS.glob("*.yaml")] if not bad else []
    if len(nums) != len(set(nums)):
        bad += 1
        print("FAIL duplicate model numbers")
    try:
        from . import products
        bad += products.validate_all()
    except ImportError:
        pass
    return 1 if bad else 0


def cmd_preview(a) -> int:
    from . import reel
    print(reel.render(a.slug, preview=True))
    return 0


def cmd_reel(a) -> int:
    from . import reel
    print(reel.render(a.slug))
    return 0


def cmd_due(a) -> int:
    from . import state
    day = dt.date.fromisoformat(a.date) if a.date else dt.date.today()
    for s in state.due(day):
        print(s)
    return 0


def cmd_post(a) -> int:
    from . import publish
    return publish.post(a.slug, dry_run=a.dry_run, only=a.only)


def cmd_site(a) -> int:
    from . import site
    print(site.build())
    return 0


def cmd_status(a) -> int:
    from . import state
    state.report()
    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "product":
        from . import products
        return products.cli(sys.argv[2:])
    ap = argparse.ArgumentParser(prog="engine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    for name in ("preview", "reel"):
        sub.add_parser(name).add_argument("slug")
    d = sub.add_parser("due"); d.add_argument("--date")
    p = sub.add_parser("post"); p.add_argument("slug"); p.add_argument("--dry-run", action="store_true")
    p.add_argument("--only", choices=["youtube", "instagram"])
    sub.add_parser("site")
    sub.add_parser("status")
    a = ap.parse_args()
    return {"validate": cmd_validate, "preview": cmd_preview, "reel": cmd_reel, "due": cmd_due,
            "post": cmd_post, "site": cmd_site, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())

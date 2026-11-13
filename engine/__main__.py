"""engine CLI

  python -m engine validate                 check every content atom and product spec
  python -m engine preview <slug>           stills of each scene (fast look before a full render)
  python -m engine reel <slug>              render build/reels/<slug>.mp4
  python -m engine render <id>              plate, story and carousel PNGs for one atom
  python -m engine daily [--date D] [--atom ID] [--no-reel]
                                            render and publish whatever is due; a dry run unless the owner's switch is on
  python -m engine connections              which channels have their secrets
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


def cmd_render(a) -> int:
    from . import atoms, social
    print(social.render_atom(atoms.get(a.id)))
    return 0


def cmd_daily(a) -> int:
    import subprocess
    from . import atoms, ledger, publish, reel, social
    day = dt.date.fromisoformat(a.date) if a.date else dt.date.today()
    every = atoms.all_atoms()
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or None
        ledger.mirror_content(every, sha)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::content not mirrored to Supabase: {e}")
    todo = [atoms.get(a.atom)] if a.atom else publish.due(day, every)
    if not todo:
        print("nothing due")
        return 0
    live = ledger.publish_live()
    print(f"{'LIVE' if live else 'DRY RUN'}: {len(todo)} atom(s) for {day}")
    failed = 0
    with social.browser() as b:
        for atom in todo:
            social.render_atom(atom, b)
    for atom in todo:
        video = {"instagram_reel", "youtube_short"}
        if not a.no_reel and video & set(atom.channels):
            reel.render(atom.id)
        failed += sum(v == "failed" for v in publish.run(atom, live=live, skip=video if a.no_reel else set()).values())
    return 1 if failed else 0


def cmd_connections(a) -> int:
    from . import ledger, publish
    for ch, missing in publish.connections().items():
        print(f"{ch:<19} " + ("connected" if not missing else "not connected: " + ", ".join(missing)))
    print(f"{'supabase':<19} " + ("connected" if ledger.connected() else "not connected: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY"))
    print(f"{'publish_live':<19} {ledger.publish_live()}")
    return 0


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
    sub.add_parser("render").add_argument("id")
    d = sub.add_parser("daily"); d.add_argument("--date"); d.add_argument("--atom"); d.add_argument("--no-reel", action="store_true")
    sub.add_parser("connections")
    sub.add_parser("site")
    sub.add_parser("status")
    a = ap.parse_args()
    return {"validate": cmd_validate, "preview": cmd_preview, "reel": cmd_reel, "render": cmd_render,
            "daily": cmd_daily, "connections": cmd_connections, "site": cmd_site, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())

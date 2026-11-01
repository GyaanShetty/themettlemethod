"""Product lines.

products/<slug>.yaml with `type`:
  notion  a self-help Notion template, built through the Notion API (see notion.py)
  deck    a printable card deck generated from every published mental model

Flow: build -> review issue (you check it) -> `/ship` comment -> Gumroad listing -> site lists it.

  python -m engine product validate
  python -m engine product pending                       specs not built yet
  python -m engine product build <slug> [--dry-run] [--force]
  python -m engine product issue-body <slug> <owner/repo>
  python -m engine product ship <slug> [--link URL] [--draft] [--dry-run]
  python -m engine product reject <slug> [reason]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import notion, state
from .content import ROOT, SLUG_RE, all_models, config

DIR = ROOT / "products"
OUT = ROOT / "build" / "products"          # PDFs (not committed)
ART = DIR / "assets"                        # covers, committed so review issues can show them
TPL = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates" / "product"),
                  autoescape=select_autoescape(["html"]))
NOTION_LINK = re.compile(r"^https://([a-z0-9-]+\.notion\.site|(www\.)?notion\.so|(www\.)?notion\.com)/\S+$")


def load(slug: str) -> dict:
    p = DIR / f"{slug}.yaml"
    if not p.exists():
        raise SystemExit(f"no product spec at {p}")
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def validate(spec: dict, stem: str) -> list[str]:
    errs = []
    for k in ("slug", "type", "title", "icon", "tagline", "listing"):
        if k not in spec:
            errs.append(f"missing {k}")
    if errs:
        return errs
    if spec["slug"] != stem or not SLUG_RE.match(spec["slug"]):
        errs.append("slug must be kebab-case and match the filename")
    lst = spec["listing"]
    for k in ("name", "price", "summary", "description", "tags"):
        if k not in lst:
            errs.append(f"listing.{k} missing")
    if not isinstance(lst.get("price"), (int, float)) or not 1 <= lst["price"] <= 500:
        errs.append("listing.price: USD between 1 and 500")
    if len(lst.get("tags", [])) > 15:
        errs.append("listing.tags: 15 max")
    if spec["type"] == "notion":
        if "home" not in spec:
            errs.append("notion products need a home section")
        errs += notion.validate(spec)
    elif spec["type"] == "deck":
        if not isinstance(spec.get("min_models"), int):
            errs.append("deck needs min_models (how many published models before it can ship)")
    else:
        errs.append(f"unknown type {spec['type']}")
    return errs


def validate_all() -> int:
    bad = 0
    for p in sorted(DIR.glob("*.yaml")):
        errs = validate(yaml.safe_load(p.read_text(encoding="utf-8")), p.stem)
        if errs:
            bad += 1
            print(f"FAIL product {p.stem}\n  " + "\n  ".join(errs))
        else:
            print(f"ok   product {p.stem}")
    return bad


# ---- rendering -------------------------------------------------------------------------------

def _ctx(spec: dict, **extra) -> dict:
    b = config()["brand"]
    head = re.split(r"\s[—–|:]\s", spec["title"], maxsplit=1)[0]
    return {"spec": spec, "b": b, "c": b["colors"], "headline": head,
            "fonts": (ROOT / "assets" / "fonts").as_uri(),
            "size": 78 if len(head) <= 16 else 62 if len(head) <= 26 else 50, **extra}


def _shoot(jobs: list[tuple[str, dict, Path, dict]]) -> None:
    """jobs: (template, context, output path, {"w","h"} for png | {"pdf": True})"""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = p.chromium.launch()
        for tpl, ctx, out, opt in jobs:
            out.parent.mkdir(parents=True, exist_ok=True)
            html = out.with_suffix(".html")
            html.write_text(TPL.get_template(tpl).render(**ctx), encoding="utf-8")
            page = br.new_page(viewport={"width": opt.get("w", 1280), "height": opt.get("h", 720)})
            page.goto(html.as_uri())
            page.evaluate("document.fonts.ready")
            if opt.get("pdf"):
                page.pdf(path=str(out), print_background=True, prefer_css_page_size=True)
            else:
                page.screenshot(path=str(out))
            page.close()
            html.unlink()
        br.close()


def _deck_cards(spec: dict, force: bool) -> list[dict]:
    import datetime as dt
    models = [m for m in all_models() if force or m["publish_on"] <= dt.date.today()]
    if len(models) < spec["min_models"] and not force:
        raise SystemExit(f"{len(models)} published models; deck ships at {spec['min_models']}")
    cards = []
    for m in models:
        how = re.search(r"## How to use it\s*\n(.*?)(\n## |\Z)", m["article"], re.S)
        steps = re.findall(r"^\s*\d+\.\s+(.+)$", how.group(1), re.M) if how else []
        cards.append({"number": m["number"], "title": m["title"], "category": m["category"],
                      "summary": m["summary"], "steps": steps[:4]})
    return cards


def build(slug: str, dry: bool = False, force: bool = False) -> dict:
    spec = load(slug)
    errs = validate(spec, slug)
    if errs:
        raise SystemExit("\n".join(errs))
    s = state.load()
    if slug in s["products"] and not force and not dry:
        print(f"{slug} already built ({s['products'][slug]['status']}); --force to rebuild")
        return s["products"][slug]

    out = OUT / slug
    entry = {"type": spec["type"], "name": spec["listing"]["name"], "summary": spec["listing"]["summary"],
             "price": spec["listing"]["price"], "price_label": f"${spec['listing']['price']:g}"}
    jobs = []
    if spec["type"] == "notion":
        res = notion.build(spec, dry=dry)
        entry.update(notion_url=res["url"], notion_page_id=res["page_id"])
        print(f"notion: {res['calls']} API calls, {res['url']}")
        items = [(d.get("icon", "▦"), d["title"], f"{len(d.get('rows', []))} items" if d.get("rows") else "")
                 for d in spec["databases"][:7]]
    else:
        cards = _deck_cards(spec, force or dry)
        jobs.append(("deck.html", _ctx(spec, cards=cards), out / f"{slug}.pdf", {"pdf": True}))
        entry.update(cards=len(cards))
        items = [("◆", f"Nº {c['number']:02d} · {c['title']}", c["category"]) for c in cards[:7]]
    ctx = _ctx(spec, items=items)
    jobs += [("cover.html", ctx, ART / slug / "cover.png", {"w": 1280, "h": 720}),
             ("thumb.html", ctx, ART / slug / "thumbnail.png", {"w": 600, "h": 600})]
    _shoot(jobs)
    print("assets: " + ", ".join(str(p.relative_to(ROOT)) for _, _, p, _ in jobs))
    if dry:
        return entry
    entry.update(status="built", built_at=state.now())
    s["products"][slug] = entry
    state.save(s)
    return entry


def issue_body(slug: str, repo: str) -> str:
    spec, e = load(slug), state.load()["products"].get(slug, {})
    lst = spec["listing"]
    raw = f"https://github.com/{repo}/blob/main/products/assets/{slug}"
    if spec["type"] == "notion":
        views = "\n".join(f"   - [ ] **{v['database']}**: {v['type']} view, {v.get('note', '')}" for v in spec.get("views", []))
        steps = f"""1. Open the Notion page: {e.get('notion_url')}
2. Optional, since the API can't make views:
{views or '   - (none)'}
3. **Share → Publish → turn on "Allow duplicate as template"**, copy the public link.
4. Comment `/ship <public link>` to go live, `/ship-draft <public link>` for a Gumroad draft, or `/reject <reason>`."""
    else:
        steps = f"""1. Check the deck PDF attached to this run's artifacts ({e.get('cards')} cards).
2. Comment `/ship` to go live, `/ship-draft` for a Gumroad draft, or `/reject <reason>`."""
    return f"""<!-- product: {slug} -->
## {spec['icon']} {lst['name']}

**Price:** ${lst['price']:g} · **Type:** {spec['type']} · **Tags:** {', '.join(lst['tags'])}

![cover]({raw}/cover.png?raw=true)

### Your part
{steps}

<details><summary>Listing copy</summary>

**Summary:** {lst['summary']}

{lst['description']}
</details>
"""


def _gumroad(spec: dict, files: list[Path], cover: Path, thumb: Path, draft: bool, dry: bool) -> dict:
    lst = spec["listing"]
    cmd = ["gumroad", "products", "create", "--name", lst["name"], "--price", f"{lst['price']:.2f}", "--currency", "usd",
           "--description", markdown.markdown(lst["description"]), "--custom-summary", lst["summary"],
           "--custom-permalink", spec["slug"], "--cover-image", str(cover), "--thumbnail", str(thumb),
           "--json", "--non-interactive", "--no-input"]
    for f in files:
        cmd += ["--file", str(f), "--file-name", f.name]
    if lst.get("category"):
        cmd += ["--category", lst["category"]]
    for t in lst["tags"]:
        cmd += ["--tag", t]
    if draft:
        cmd.append("--draft")
    if dry:
        cmd.append("--dry-run")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"gumroad: {r.stderr.strip() or r.stdout.strip()}")
    if dry:
        return {"dry_run": r.stdout}
    data = json.loads(r.stdout)
    prod = data.get("product", {})
    return {"id": prod.get("id"), "published": prod.get("published"), "warning": data.get("warning") or ""}


def ship(slug: str, link: str | None, draft: bool, dry: bool) -> dict:
    spec, s = load(slug), state.load()
    e = s["products"].get(slug)
    if not e and not dry:
        raise SystemExit(f"{slug} isn't built yet")
    e = e or {}
    if e.get("status") == "shipped" and not dry:
        raise SystemExit(f"{slug} is already live")
    if e.get("status") == "gumroad-draft" and not draft and not dry:
        r = subprocess.run(["gumroad", "products", "publish", e["gumroad_id"], "--non-interactive", "--no-input"],
                           capture_output=True, text=True)
        if r.returncode:
            raise SystemExit(f"gumroad publish: {r.stderr.strip()}")
        e.update(status="shipped", shipped_at=state.now())
        state.save(s)
        return {"id": e["gumroad_id"], "published": True, "warning": ""}

    out = OUT / slug
    if spec["type"] == "notion":
        if not link or not NOTION_LINK.match(link):
            raise SystemExit("notion products need the public Notion link: /ship https://you.notion.site/...")
        pdf = out / f"{slug}-access.pdf"
        _shoot([("delivery.html", _ctx(spec, link=link), pdf, {"pdf": True})])
        files = [pdf]
        e["public_link"] = link
    else:
        pdf = out / f"{slug}.pdf"
        if not pdf.exists():
            _shoot([("deck.html", _ctx(spec, cards=_deck_cards(spec, False)), pdf, {"pdf": True})])
        files = [pdf]
    res = _gumroad(spec, files, ART / slug / "cover.png", ART / slug / "thumbnail.png", draft, dry)
    if dry:
        print(res["dry_run"])
        return res
    gr = config()["brand"].get("gumroad", "").rstrip("/")
    e.update(status="shipped" if res["published"] else "gumroad-draft", gumroad_id=res["id"],
             gumroad_url=f"{gr}/l/{slug}", shipped_at=state.now())
    if res["warning"]:
        e["gumroad_warning"] = res["warning"]
    s["products"][slug] = e
    state.save(s)
    return res


def _out(**kv) -> None:
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            for k, v in kv.items():
                f.write(f"{k}={str(v).replace(chr(10), ' ')}\n")


def cli(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="engine product")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    sub.add_parser("pending")
    b = sub.add_parser("build"); b.add_argument("slug"); b.add_argument("--dry-run", action="store_true")
    b.add_argument("--force", action="store_true")
    i = sub.add_parser("issue-body"); i.add_argument("slug"); i.add_argument("repo")
    sh = sub.add_parser("ship"); sh.add_argument("slug"); sh.add_argument("--link")
    sh.add_argument("--draft", action="store_true"); sh.add_argument("--dry-run", action="store_true")
    r = sub.add_parser("reject"); r.add_argument("slug"); r.add_argument("reason", nargs="?", default="")
    a = ap.parse_args(argv)
    if a.cmd == "validate":
        return 1 if validate_all() else 0
    if a.cmd == "pending":
        built = state.load()["products"]
        for p in sorted(DIR.glob("*.yaml")):
            spec = yaml.safe_load(p.read_text(encoding="utf-8"))
            if p.stem in built:
                continue
            if spec.get("type") == "deck":
                import datetime as dt
                if sum(m["publish_on"] <= dt.date.today() for m in all_models()) < spec.get("min_models", 0):
                    continue
            print(p.stem)
        return 0
    if a.cmd == "build":
        build(a.slug, a.dry_run, a.force)
        return 0
    if a.cmd == "issue-body":
        print(issue_body(a.slug, a.repo))
        return 0
    if a.cmd == "ship":
        res = ship(a.slug, a.link, a.draft, a.dry_run)
        _out(published=str(bool(res.get("published"))).lower(), warning=res.get("warning", ""), gumroad_id=res.get("id", ""))
        return 0
    if a.cmd == "reject":
        s = state.load()
        s["products"].setdefault(a.slug, {}).update(status="rejected", reason=a.reason, rejected_at=state.now())
        state.save(s)
        return 0
    return 1

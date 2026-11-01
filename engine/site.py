"""Static website, generated from the same atoms and product state.

build/site/
  index.html                 latest models + products
  models/<slug>/index.html   the reel (YouTube embed once posted) + written breakdown + sources
  models/index.html          library of every published model
  products/index.html        everything live on Gumroad
  feed.xml, sitemap.xml, robots.txt, 404.html
Only models whose publish_on date has passed are included.
"""
from __future__ import annotations

import datetime as dt
import shutil
from email.utils import format_datetime
from pathlib import Path

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import state
from .content import ROOT, all_models, config

TPL = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates" / "site"),
                  autoescape=select_autoescape(["html", "xml"]))
OUT = ROOT / "build" / "site"


def _md(text: str) -> str:
    return markdown.markdown(text, extensions=["extra", "sane_lists"])


def build(today: dt.date | None = None) -> Path:
    today = today or dt.date.today()
    cfg, st = config(), state.load()
    b = cfg["brand"]
    base = b["site_url"].rstrip("/")
    root = "/" + base.split("://", 1)[-1].split("/", 1)[1] if base.count("/") > 2 else ""  # GitHub Pages project path

    from .content import all_items, tracks
    trs = tracks()
    by_track: dict[str, list[dict]] = {}
    for tr, meta in trs.items():
        items = [i for i in all_items(tr) if i["publish_on"] <= today]
        for i in items:
            i["track"], i["track_label"] = tr, meta["label"]
            i["html"] = _md(i["article"])
            i["url"] = f"{root}/{tr}/{i['slug']}/"
            if tr == "models":
                post = st["posts"].get(i["slug"], {})
                i["youtube_id"] = post.get("youtube", {}).get("id")
        items.sort(key=lambda i: (i["publish_on"], i.get("number", 0)), reverse=True)
        by_track[tr] = items
    models = by_track.get("models", [])
    latest = sorted((i for v in by_track.values() for i in v), key=lambda i: (i["publish_on"], i["slug"]), reverse=True)

    products = [dict(slug=s, **e) for s, e in st["products"].items() if e.get("status") == "shipped"]
    products.sort(key=lambda p: p.get("shipped_at", ""), reverse=True)

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "fonts").mkdir(parents=True)
    for f in (ROOT / "assets" / "fonts").glob("*.ttf"):
        shutil.copy(f, OUT / "fonts" / f.name)

    nav = [(m["label"], f"{root}/{t}/") for t, m in trs.items()] + [("Products", f"{root}/products/")]
    ctx = dict(b=b, root=root, base=base, year=today.year, models=models, products=products,
               tracks=trs, by_track=by_track, latest=latest, nav=nav)

    def page(rel: str, tpl: str, **kw):
        p = OUT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(TPL.get_template(tpl).render(**ctx, **kw), encoding="utf-8")

    page("index.html", "index.html", title=b["name"], description=b["tagline"])
    for tr, meta in trs.items():
        items = by_track[tr]
        page(f"{tr}/index.html", "collection.html", tr=tr, meta=meta, items=items,
             title=f"{meta['label']} · {b['name']}", description=meta["blurb"])
        for k, it in enumerate(items):
            page(f"{tr}/{it['slug']}/index.html", "item.html", m=it, meta=meta,
                 older=items[k + 1] if k + 1 < len(items) else None, newer=items[k - 1] if k else None,
                 title=f"{it['title']} · {b['name']}", description=it["summary"])
    page("products/index.html", "products.html", title=f"Products · {b['name']}",
         description="Templates and tools for clearer thinking.")
    page("404.html", "404.html", title="Not found", description=b["tagline"])

    def rfc822(d):
        return format_datetime(dt.datetime.combine(d, dt.time(13, 30), tzinfo=dt.timezone.utc))
    (OUT / "feed.xml").write_text(TPL.get_template("feed.xml").render(**ctx, rfc822=rfc822), encoding="utf-8")
    urls = [f"{base}/", f"{base}/products/"] + [f"{base}/{t}/" for t in trs] + [base + i["url"][len(root):] for i in latest]
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n")
    (OUT / ".nojekyll").write_text("")
    return OUT

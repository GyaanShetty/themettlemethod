"""Build a Notion template from a product spec with the public REST API (version 2022-06-28).

Order: home page -> databases (simple columns) -> dual relations (+ rename the synced column)
-> rollups -> formulas -> rows -> relations between rows.
The API can't create views or publish to the web; those stay manual (the review issue lists them).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import time

import requests

API = "https://api.notion.com/v1"
SIMPLE = {"rich_text", "number", "select", "multi_select", "date", "checkbox", "url", "email", "phone_number", "files"}
COLORS = ["blue", "green", "orange", "pink", "purple", "yellow", "red", "brown", "gray", "default"]
ROLLUP_FUNCS = {"sum", "average", "count", "count_values", "min", "max", "percent_checked", "percent_not_checked",
                "checked", "unchecked", "show_original", "earliest_date", "latest_date", "empty", "not_empty", "median"}
REL_DATE = re.compile(r"^([+-]\d+)d(?:T(\d{2}:\d{2}))?$")


def options(opts: list) -> list[dict]:
    out = []
    for i, o in enumerate(opts):
        name, color = str(o), COLORS[i % (len(COLORS) - 1)]
        head, sep, tail = name.rpartition(":")
        if sep and tail in COLORS:
            name, color = head, tail
        out.append({"name": name, "color": color})
    return out


def rel_date(v, today=None):
    m = REL_DATE.match(v) if isinstance(v, str) else None
    if not m:
        return v
    d = (today or dt.date.today()) + dt.timedelta(days=int(m.group(1)))
    return f"{d.isoformat()}T{m.group(2)}:00" if m.group(2) else d.isoformat()


def validate(spec: dict) -> list[str]:
    errs, names = [], {}
    dbs = spec.get("databases", [])
    if not 2 <= len(dbs) <= 8:
        errs.append("notion products need 2-8 databases")
    for db in dbs:
        for f in ("key", "title", "title_property", "properties"):
            if f not in db:
                errs.append(f"database {db.get('key')}: missing {f}")
        names[db.get("key")] = {db.get("title_property")} | set(db.get("properties", {}))
    for db in dbs:
        for pn, p in db.get("properties", {}).items():
            if p.get("type") == "relation":
                if p.get("target") not in names:
                    errs.append(f"{db['key']}.{pn}: unknown relation target {p.get('target')}")
                elif p.get("synced_name"):
                    names[p["target"]].add(p["synced_name"])
    rels = 0
    for db in dbs:
        for pn, p in db.get("properties", {}).items():
            t, where = p.get("type"), f"{db['key']}.{pn}"
            if t == "status":
                errs.append(f"{where}: the API can't create status columns; use select")
            elif t not in SIMPLE | {"relation", "rollup", "formula"}:
                errs.append(f"{where}: unknown type {t}")
            if t in ("select", "multi_select") and not p.get("options"):
                errs.append(f"{where}: needs options")
            if t == "relation":
                rels += 1
            if t == "rollup":
                if p.get("relation") not in names[db["key"]]:
                    errs.append(f"{where}: rollup relation '{p.get('relation')}' isn't a column here")
                if p.get("function") not in ROLLUP_FUNCS:
                    errs.append(f"{where}: bad rollup function {p.get('function')}")
            if t == "formula" and not p.get("expression"):
                errs.append(f"{where}: formula needs expression")
        for i, row in enumerate(db.get("rows", [])):
            for col, v in row.get("values", {}).items():
                if col not in names[db["key"]]:
                    errs.append(f"{db['key']}.rows[{i}]: unknown column '{col}'")
                if v is None:
                    errs.append(f"{db['key']}.rows[{i}].{col}: empty (quote strings containing commas)")
    if rels < 1:
        errs.append("needs at least one relation; linked data is what people pay for")
    return errs


class Client:
    def __init__(self, token: str, dry: bool = False):
        self.dry, self.n, self.calls = dry, 0, 0
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28",
                               "Content-Type": "application/json"})

    def __call__(self, method: str, path: str, body: dict | None = None) -> dict:
        self.calls += 1
        if self.dry:
            self.n += 1
            if method == "PATCH" and path.startswith("/databases/"):
                return {"properties": {k: {"relation": {"dual_property": {"synced_property_id": f"syn{self.n}"}}}
                                       for k, v in (body or {}).get("properties", {}).items() if "relation" in v}}
            return {"id": f"dry-{self.n}", "url": f"https://www.notion.so/dry-{self.n}"}
        for attempt in range(6):
            r = self.s.request(method, API + path, data=json.dumps(body) if body else None, timeout=60)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(float(r.headers.get("Retry-After", 2 ** attempt)))
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"Notion {method} {path}: {r.status_code} {r.text[:500]}")
            time.sleep(0.34)
            return r.json()
        raise RuntimeError(f"Notion {method} {path}: gave up")


def _rt(text: str) -> list[dict]:
    return [{"type": "text", "text": {"content": text[i:i + 2000]}} for i in range(0, len(text), 2000)]


def _value(t: str, v):
    if t == "title":
        return {"title": _rt(str(v))}
    if t == "rich_text":
        return {"rich_text": _rt(str(v))}
    if t == "number":
        return {"number": v}
    if t == "select":
        return {"select": {"name": str(v)}}
    if t == "multi_select":
        return {"multi_select": [{"name": str(x)} for x in (v if isinstance(v, list) else [v])]}
    if t == "checkbox":
        return {"checkbox": bool(v)}
    if t in ("url", "email", "phone_number"):
        return {t: str(v)}
    if t == "date":
        return {"date": {"start": rel_date(str(v))}}
    raise ValueError(f"can't set a value on a {t} column")


def _home(spec: dict) -> list[dict]:
    h = spec["home"]
    blocks = [{"type": "callout", "callout": {"rich_text": _rt(h["intro"]), "color": "orange_background",
                                              "icon": {"type": "emoji", "emoji": h.get("intro_icon", "✨")}}},
              {"type": "heading_2", "heading_2": {"rich_text": _rt("Start here")}}]
    blocks += [{"type": "numbered_list_item", "numbered_list_item": {"rich_text": _rt(s)}} for s in h.get("steps", [])]
    blocks += [{"type": "callout", "callout": {"rich_text": _rt(c["text"]), "color": c.get("color", "gray_background"),
                                               "icon": {"type": "emoji", "emoji": c.get("icon", "💡")}}}
               for c in h.get("callouts", [])]
    blocks += [{"type": "divider", "divider": {}}, {"type": "heading_2", "heading_2": {"rich_text": _rt("Your workspace")}}]
    return blocks


def build(spec: dict, dry: bool = False) -> dict:
    token = os.environ.get("NOTION_TOKEN", "dry")
    parent = os.environ.get("NOTION_PARENT_PAGE_ID", "dry")
    if not dry and "dry" in (token, parent):
        raise RuntimeError("set NOTION_TOKEN and NOTION_PARENT_PAGE_ID")
    n = Client(token, dry)
    home = n("POST", "/pages", {"parent": {"page_id": parent}, "icon": {"type": "emoji", "emoji": spec["icon"]},
                                "properties": {"title": {"title": _rt(spec["title"])}}, "children": _home(spec)})
    ids, types = {}, {}
    for db in spec["databases"]:
        props = {db["title_property"]: {"title": {}}}
        types[db["key"]] = {db["title_property"]: "title"}
        for name, p in db["properties"].items():
            types[db["key"]][name] = p["type"]
            if p["type"] in ("select", "multi_select"):
                props[name] = {p["type"]: {"options": options(p["options"])}}
            elif p["type"] == "number":
                props[name] = {"number": {"format": p.get("format", "number")}}
            elif p["type"] in SIMPLE:
                props[name] = {p["type"]: {}}
        body = {"parent": {"type": "page_id", "page_id": home["id"]}, "title": _rt(db["title"]), "properties": props}
        if db.get("icon"):
            body["icon"] = {"type": "emoji", "emoji": db["icon"]}
        if db.get("description"):
            body["description"] = _rt(db["description"])
        ids[db["key"]] = n("POST", "/databases", body)["id"]

    for db in spec["databases"]:
        for name, p in db["properties"].items():
            if p["type"] != "relation":
                continue
            res = n("PATCH", f"/databases/{ids[db['key']]}", {"properties": {name: {"relation": {
                "database_id": ids[p["target"]], "type": "dual_property", "dual_property": {}}}}})
            synced = res["properties"][name]["relation"].get("dual_property", {})
            if p.get("synced_name"):
                if synced.get("synced_property_id"):
                    n("PATCH", f"/databases/{ids[p['target']]}",
                      {"properties": {synced["synced_property_id"]: {"name": p["synced_name"]}}})
                types[p["target"]][p["synced_name"]] = "relation"

    for kind in ("rollup", "formula"):
        for db in spec["databases"]:
            batch = {}
            for name, p in db["properties"].items():
                if p["type"] == kind == "rollup":
                    batch[name] = {"rollup": {"relation_property_name": p["relation"],
                                              "rollup_property_name": p["property"], "function": p["function"]}}
                elif p["type"] == kind == "formula":
                    batch[name] = {"formula": {"expression": p["expression"]}}
            if batch:
                n("PATCH", f"/databases/{ids[db['key']]}", {"properties": batch})

    rows, pending = {}, []
    for db in spec["databases"]:
        t = types[db["key"]]
        for row in db.get("rows", []):
            props, rels = {}, {}
            for col, v in row["values"].items():
                if t[col] == "relation":
                    rels[col] = v if isinstance(v, list) else [v]
                elif t[col] not in ("rollup", "formula"):
                    props[col] = _value(t[col], v)
            body = {"parent": {"database_id": ids[db["key"]]}, "properties": props}
            if row.get("icon"):
                body["icon"] = {"type": "emoji", "emoji": row["icon"]}
            pid = n("POST", "/pages", body)["id"]
            if row.get("key"):
                rows[f"{db['key']}.{row['key']}"] = pid
            if rels:
                pending.append((pid, rels))
    for pid, rels in pending:
        props = {}
        for col, refs in rels.items():
            missing = [r for r in refs if r not in rows]
            if missing:
                raise RuntimeError(f"unknown row reference(s) {missing}; use <db_key>.<row_key>")
            props[col] = {"relation": [{"id": rows[r]} for r in refs]}
        n("PATCH", f"/pages/{pid}", {"properties": props})

    return {"page_id": home["id"], "url": home.get("url"), "database_ids": ids, "calls": n.calls}

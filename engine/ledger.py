"""The record of what has gone out. Supabase is the system of record; state.json in the repo is the
fallback, so a run with no database still cannot post anything twice."""
from __future__ import annotations

import os

from . import net, state


def _sb() -> tuple[str, str] | None:
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    return (url.rstrip("/"), key) if url and key else None


def _headers(key: str, extra: dict | None = None) -> dict:
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", **(extra or {})}


def connected() -> bool:
    return _sb() is not None


def publish_live() -> bool:
    """Live posting needs the owner's switch in the config table. Anything else is a dry run."""
    if os.environ.get("PUBLISH_LIVE", "").lower() == "false" or not _sb():
        return False
    url, key = _sb()
    try:
        rows = net.call("GET", f"{url}/rest/v1/config?key=eq.publish_live&select=value", headers=_headers(key), log=False).json()
        return bool(rows) and rows[0]["value"] is True
    except Exception:  # noqa: BLE001  if the switch cannot be read, stay silent
        return False


def upsert(table: str, rows: list[dict], on_conflict: str) -> None:
    if not _sb() or not rows:
        return
    url, key = _sb()
    net.call("POST", f"{url}/rest/v1/{table}?on_conflict={on_conflict}", json=rows, log=False,
             headers=_headers(key, {"Prefer": "resolution=merge-duplicates,return=minimal"}))


def event(name: str, props: dict) -> None:
    if not _sb():
        return
    url, key = _sb()
    try:
        net.call("POST", f"{url}/rest/v1/events", json=[{"name": name, "props": props}], log=False, tries=1,
                 headers=_headers(key, {"Prefer": "return=minimal"}))
    except Exception:  # noqa: BLE001  logging never breaks a run
        pass


def already_posted(atom_id: str, channel: str) -> bool:
    if state.load()["posts"].get(atom_id, {}).get(channel, {}).get("status") == "posted":
        return True
    if _sb():
        url, key = _sb()
        rows = net.call("GET", f"{url}/rest/v1/publications?content_id=eq.{atom_id}&channel=eq.{channel}&select=status",
                        headers=_headers(key), log=False).json()
        return bool(rows) and rows[0]["status"] == "posted"
    return False


def record(atom_id: str, channel: str, status: str, **fields) -> None:
    """Write the outcome to state.json first, then mirror it to Supabase."""
    s = state.load()
    if s["posts"].get(atom_id, {}).get(channel, {}).get("status") == "posted" and status != "posted":
        return                                   # never downgrade a real post
    if status != "dry_run":                      # dry runs go to the database only, so the repo stays quiet
        s["posts"].setdefault(atom_id, {}).setdefault(channel, {}).update({"status": status, **fields, "at": state.now()})
        state.save(s)
    row = {"content_id": atom_id, "channel": channel, "status": status, "updated_at": state.now(),
           "external_id": fields.get("external_id"), "url": fields.get("url"), "error": fields.get("error"),
           "posted_at": state.now() if status == "posted" else None}
    try:
        upsert("publications", [row], "content_id,channel")
    except Exception as e:  # noqa: BLE001
        print(f"::warning::could not mirror {atom_id}/{channel} to Supabase: {e}")


def mirror_content(atoms: list, sha: str | None = None) -> None:
    rows = [{"id": a.id, "type": a.type, "pillar": a.pillar, "number": a.number, "title": a.title, "kicker": a.kicker,
             "headline": a.headline, "sub": a.sub, "body": a.body, "source": a.source, "image": a.image,
             "publish_on": a.publish_on.isoformat(), "status": a.status, "channels": list(a.channels),
             "git_sha": sha, "updated_at": state.now()} for a in atoms]
    upsert("content", rows, "id")


def upload(path, name: str, content_type: str) -> str:
    """Put a file in the public media bucket and return the URL the platforms fetch it from."""
    url, key = _sb()
    with open(path, "rb") as f:
        net.call("POST", f"{url}/storage/v1/object/media/{name}", data=f.read(), timeout=300,
                 headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": content_type, "x-upsert": "true"})
    return f"{url}/storage/v1/object/public/media/{name}"

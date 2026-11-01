"""Post a rendered reel to YouTube Shorts and Instagram Reels.

Secrets (environment):
  YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN
  IG_ACCESS_TOKEN                      long-lived Instagram User token (Instagram Login)
  SUPABASE_URL, SUPABASE_SERVICE_KEY   public bucket "reels" used as the video_url Instagram fetches
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

from . import state
from .content import ROOT, config, load_model

IG = "https://graph.instagram.com/" + os.environ.get("IG_API_VERSION", "v26.0")
BUCKET = "reels"


def _env(*names: str) -> list[str]:
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise RuntimeError("missing secrets: " + ", ".join(missing))
    return [os.environ[n] for n in names]


def _hashtags(m: dict) -> str:
    return " ".join("#" + t.lstrip("#") for t in m["tags"])


def youtube_meta(m: dict, cfg: dict) -> dict:
    title = f"{m['title']}: {m['summary']}"
    if len(title) > 90:
        title = f"{m['title']} | Mental model #{m['number']}"
    site = cfg["brand"].get("site_url", "")
    link = f"\n\nFull breakdown: {site}/models/{m['slug']}/" if "YOUR-" not in site else ""
    return {
        "snippet": {
            "title": (title + " #Shorts")[:100],
            "description": f"{m['caption'].strip()}{link}\n\n{_hashtags(m)} #Shorts",
            "tags": m["tags"][:15],
            "categoryId": cfg["publish"].get("youtube_category", "27"),
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {"privacyStatus": cfg["publish"].get("youtube_privacy", "public"),
                   "selfDeclaredMadeForKids": False},
    }


def instagram_caption(m: dict) -> str:
    return f"{m['caption'].strip()}\n\nFull breakdown: link in bio.\n\n{_hashtags(m)}"[:2200]


# ---- YouTube --------------------------------------------------------------------------------

def _yt_token() -> str:
    cid, secret, refresh = _env("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": cid, "client_secret": secret, "refresh_token": refresh, "grant_type": "refresh_token"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def post_youtube(video: Path, meta: dict) -> dict:
    tok = _yt_token()
    size = video.stat().st_size
    r = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
        data=json.dumps(meta), timeout=60)
    r.raise_for_status()
    loc = r.headers["Location"]
    with open(video, "rb") as f:
        up = requests.put(loc, headers={"Authorization": f"Bearer {tok}", "Content-Type": "video/mp4"},
                          data=f, timeout=600)
    up.raise_for_status()
    vid = up.json()["id"]
    privacy = up.json().get("status", {}).get("privacyStatus")
    return {"id": vid, "url": f"https://youtube.com/shorts/{vid}", "privacy": privacy}


# ---- Instagram ------------------------------------------------------------------------------

def _host(video: Path, name: str) -> str:
    url, key = _env("SUPABASE_URL", "SUPABASE_SERVICE_KEY")
    url = url.rstrip("/")
    with open(video, "rb") as f:
        r = requests.post(f"{url}/storage/v1/object/{BUCKET}/{name}", data=f, timeout=300,
                          headers={"Authorization": f"Bearer {key}", "apikey": key,
                                   "Content-Type": "video/mp4", "x-upsert": "true"})
    r.raise_for_status()
    return f"{url}/storage/v1/object/public/{BUCKET}/{name}"


def _unhost(name: str) -> None:
    url, key = _env("SUPABASE_URL", "SUPABASE_SERVICE_KEY")
    requests.delete(f"{url.rstrip('/')}/storage/v1/object/{BUCKET}", timeout=60,
                    headers={"Authorization": f"Bearer {key}", "apikey": key},
                    json={"prefixes": [name]})


def _ig(method: str, path: str, **params) -> dict:
    (tok,) = _env("IG_ACCESS_TOKEN")
    r = requests.request(method, f"{IG}/{path}", params={**params, "access_token": tok}, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"Instagram {path}: {r.status_code} {r.text[:400]}")
    return r.json()


def post_instagram(video: Path, caption: str, slug: str) -> dict:
    me = _ig("GET", "me", fields="user_id,username")
    uid = me.get("user_id") or me["id"]
    name = f"{slug}-{int(time.time())}.mp4"
    video_url = _host(video, name)
    try:
        c = _ig("POST", f"{uid}/media", media_type="REELS", video_url=video_url, caption=caption, share_to_feed="true")
        cid = c["id"]
        for _ in range(40):  # up to ~10 minutes of processing
            st = _ig("GET", cid, fields="status_code,status").get("status_code")
            if st == "FINISHED":
                break
            if st in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Instagram rejected the video: {st}")
            time.sleep(15)
        else:
            raise RuntimeError("Instagram processing timed out")
        mid = _ig("POST", f"{uid}/media_publish", creation_id=cid)["id"]
        link = _ig("GET", mid, fields="permalink").get("permalink")
        return {"id": mid, "url": link, "account": me.get("username")}
    finally:
        _unhost(name)


def refresh_instagram_token() -> str:
    """Long-lived tokens last 60 days; refreshing gives a fresh 60 days. Run monthly."""
    (tok,) = _env("IG_ACCESS_TOKEN")
    r = requests.get("https://graph.instagram.com/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": tok}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


# ---- orchestration --------------------------------------------------------------------------

def post(slug: str, dry_run: bool = False, only: str | None = None) -> int:
    m, cfg = load_model(slug), config()
    video = ROOT / "build" / "reels" / f"{slug}.mp4"
    want = [p for p in state.platforms(cfg) if not only or p == only]

    if dry_run:
        print(json.dumps({"video": str(video), "exists": video.exists(), "platforms": want,
                          "youtube": youtube_meta(m, cfg), "instagram_caption": instagram_caption(m)},
                         indent=2, ensure_ascii=False))
        return 0

    if not video.exists():
        from . import reel
        reel.render(slug)

    s = state.load()
    done = s["posts"].setdefault(slug, {})
    failed = 0
    for p in want:
        if p in done:
            print(f"{p}: already posted ({done[p].get('url')})")
            continue
        try:
            res = post_youtube(video, youtube_meta(m, cfg)) if p == "youtube" else \
                post_instagram(video, instagram_caption(m), slug)
            res["posted_at"] = state.now()
            done[p] = res
            state.save(s)  # save after each platform so a later failure doesn't cause a double post
            print(f"{p}: {res.get('url')}" + (f" (privacy: {res['privacy']})" if res.get("privacy") else ""))
            if p == "youtube" and res.get("privacy") == "private" and cfg["publish"].get("youtube_privacy") == "public":
                print("::warning::YouTube locked this upload to private: your API project hasn't passed YouTube's "
                      "audit yet. Flip it public in YouTube Studio and submit the audit form (see README).")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"{p}: FAILED {e}")
    return 1 if failed else 0

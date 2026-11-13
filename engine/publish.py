"""Publishers. One per channel, all behind the same interface, all safe to run twice.

A publisher never decides whether to go live. `run()` does: it posts only when the atom is approved,
the owner's switch is on, the channel's secrets exist and the ledger shows nothing posted yet.
Otherwise it renders, logs what it would have sent and records a dry run.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import ledger, net, text
from .atoms import Atom
from .content import ROOT, config

IG = "https://graph.instagram.com/" + os.environ.get("IG_API_VERSION", "v26.0")
THREADS = "https://graph.threads.net/v1.0"
BUILD = ROOT / "build"


@dataclass
class Result:
    external_id: str
    url: str | None = None
    note: str | None = None


@dataclass
class Publisher:
    channel: str
    secrets: tuple[str, ...]
    files: tuple[str, ...] = ()
    needs_media_host: bool = False
    _missing: list[str] = field(default_factory=list)

    def missing(self) -> list[str]:
        need = self.secrets + (("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY") if self.needs_media_host else ())
        return [s for s in need if not os.environ.get(s)]

    def paths(self, a: Atom) -> list[Path]:
        return [BUILD / f.format(id=a.id) for f in self.files]

    def payload(self, a: Atom) -> dict:
        return {"caption": caption(a)}

    def send(self, a: Atom) -> Result:  # pragma: no cover - overridden
        raise NotImplementedError


def caption(a: Atom) -> str:
    """Five hashtags, Instagram's cap: three fixed, two for the pillar."""
    tags = ["stoicism", "discipline", "mettlemethod", a.pillar, {"model": "mentalmodels", "concept": "ideas", "skill": "skills",
                                                                 "quote": "stoicquotes", "law": "principles"}[a.type]]
    lines = [a.headline.replace("\n", " "), a.sub] + ([a.source] if a.source else [])
    return "\n\n".join(lines + ["One lesson a day. Link in bio.", " ".join("#" + t for t in tags)])[:2200]


# ---- Instagram ------------------------------------------------------------------------------

def _ig(method: str, path: str, **params) -> dict:
    return net.call(method, f"{IG}/{path}", params={**params, "access_token": os.environ["IG_ACCESS_TOKEN"]}).json()


def _ig_wait(cid: str) -> None:
    for _ in range(40):
        st = _ig("GET", cid, fields="status_code").get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram rejected the media: {st}")
        time.sleep(15)
    raise RuntimeError("Instagram processing timed out")


def _ig_publish(uid: str, cid: str) -> Result:
    _ig_wait(cid)
    mid = _ig("POST", f"{uid}/media_publish", creation_id=cid)["id"]
    return Result(mid, _ig("GET", mid, fields="permalink").get("permalink"))


def _ig_uid() -> str:
    me = _ig("GET", "me", fields="user_id")
    return me.get("user_id") or me["id"]


class InstagramPlate(Publisher):
    def send(self, a):
        uid, url = _ig_uid(), ledger.upload(self.paths(a)[0], f"{a.id}/plate.png", "image/png")
        return _ig_publish(uid, _ig("POST", f"{uid}/media", image_url=url, caption=caption(a))["id"])


class InstagramStory(Publisher):
    def payload(self, a):
        return {}

    def send(self, a):
        uid, url = _ig_uid(), ledger.upload(self.paths(a)[0], f"{a.id}/story.png", "image/png")
        return _ig_publish(uid, _ig("POST", f"{uid}/media", media_type="STORIES", image_url=url)["id"])


class InstagramCarousel(Publisher):
    def send(self, a):
        uid = _ig_uid()
        kids = [_ig("POST", f"{uid}/media", image_url=ledger.upload(p, f"{a.id}/{p.name}", "image/png"), is_carousel_item="true")["id"]
                for p in self.paths(a)]
        cid = _ig("POST", f"{uid}/media", media_type="CAROUSEL", children=",".join(kids), caption=caption(a))["id"]
        return _ig_publish(uid, cid)


class InstagramReel(Publisher):
    def send(self, a):
        uid, url = _ig_uid(), ledger.upload(self.paths(a)[0], f"{a.id}/reel.mp4", "video/mp4")
        cid = _ig("POST", f"{uid}/media", media_type="REELS", video_url=url, caption=caption(a), share_to_feed="true")["id"]
        return _ig_publish(uid, cid)


def refresh_instagram_token() -> str:
    """Long-lived tokens last 60 days; refreshing gives a fresh 60. Run monthly by tokens.yml."""
    return net.call("GET", "https://graph.instagram.com/refresh_access_token", log=False,
                    params={"grant_type": "ig_refresh_token", "access_token": os.environ["IG_ACCESS_TOKEN"]}).json()["access_token"]


# ---- YouTube --------------------------------------------------------------------------------

class YouTubeShort(Publisher):
    def payload(self, a):
        cfg = config()
        site = cfg["brand"].get("site_url", "")
        return {"snippet": {"title": f"{a.title}. {a.headline.replace(chr(10), ' ')} #Shorts"[:100],
                            "description": f"{a.sub}\n\nThe full lesson: {site}/library/{a.type}s/{a.id}/\n\n#Shorts",
                            "categoryId": cfg["publish"].get("youtube_category", "27"), "defaultLanguage": "en"},
                "status": {"privacyStatus": cfg["publish"].get("youtube_privacy", "public"), "selfDeclaredMadeForKids": False}}

    def send(self, a):
        tok = net.call("POST", "https://oauth2.googleapis.com/token", log=False, data={
            "client_id": os.environ["YOUTUBE_CLIENT_ID"], "client_secret": os.environ["YOUTUBE_CLIENT_SECRET"],
            "refresh_token": os.environ["YOUTUBE_REFRESH_TOKEN"], "grant_type": "refresh_token"}).json()["access_token"]
        video = self.paths(a)[0]
        start = net.call("POST", "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                         headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8",
                                  "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(video.stat().st_size)},
                         data=json.dumps(self.payload(a)))
        up = net.call("PUT", start.headers["Location"], data=video.read_bytes(), timeout=600, tries=2,
                      headers={"Authorization": f"Bearer {tok}", "Content-Type": "video/mp4"}).json()
        privacy = up.get("status", {}).get("privacyStatus")
        note = "YouTube held this upload as private; the API project has not passed its audit." if privacy == "private" else None
        return Result(up["id"], f"https://youtube.com/shorts/{up['id']}", note)


# ---- Threads --------------------------------------------------------------------------------

class Threads(Publisher):
    def payload(self, a):
        return {"text": text.thread(a)}

    def send(self, a):
        tok = os.environ["THREADS_ACCESS_TOKEN"]
        uid = net.call("GET", f"{THREADS}/me", params={"fields": "id", "access_token": tok}).json()["id"]
        cid = net.call("POST", f"{THREADS}/{uid}/threads", params={"media_type": "TEXT", "text": text.thread(a), "access_token": tok}).json()["id"]
        pid = net.call("POST", f"{THREADS}/{uid}/threads_publish", params={"creation_id": cid, "access_token": tok}).json()["id"]
        link = net.call("GET", f"{THREADS}/{pid}", params={"fields": "permalink", "access_token": tok}).json().get("permalink")
        return Result(pid, link)


# ---- Email: one interface, two providers ----------------------------------------------------

class Email(Publisher):
    """The morning lesson to everyone who opted in. The provider holds the list and the one-click stop."""
    def provider(self) -> str | None:
        return os.environ.get("EMAIL_PROVIDER") or None

    def missing(self):
        p = self.provider()
        if p == "resend":
            need = ("RESEND_API_KEY", "RESEND_AUDIENCE_ID", "EMAIL_FROM")
        elif p == "buttondown":
            need = ("BUTTONDOWN_API_KEY",)
        else:
            return ["EMAIL_PROVIDER"]
        return [s for s in need if not os.environ.get(s)]

    def payload(self, a):
        e = text.email(a, config()["brand"]["site_url"])
        return {"provider": self.provider(), "subject": e["subject"], "text": e["text"]}

    def send(self, a):
        site = config()["brand"]["site_url"]
        if self.provider() == "resend":
            e = text.email(a, site, unsubscribe="{{{RESEND_UNSUBSCRIBE_URL}}}")
            h = {"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}", "Idempotency-Key": f"lesson-{a.id}"}
            b = net.call("POST", "https://api.resend.com/broadcasts", headers=h, json={
                "audience_id": os.environ["RESEND_AUDIENCE_ID"], "from": os.environ["EMAIL_FROM"],
                "subject": e["subject"], "html": e["html"], "text": e["text"], "name": f"lesson-{a.id}"}).json()
            net.call("POST", f"https://api.resend.com/broadcasts/{b['id']}/send", headers=h, json={})
            return Result(b["id"])
        e = text.email(a, site, unsubscribe="{{ unsubscribe_url }}")
        r = net.call("POST", "https://api.buttondown.com/v1/emails", json={"subject": e["subject"], "body": e["html"]},
                     headers={"Authorization": f"Token {os.environ['BUTTONDOWN_API_KEY']}"}).json()
        return Result(r["id"], r.get("absolute_url"))


class Site(Publisher):
    """The library page is built and deployed by site.yml on its own schedule; this only records it."""
    def send(self, a):
        return Result(a.id, f"{config()['brand']['site_url']}/library/{a.type}s/{a.id}/")


PUBLISHERS: dict[str, Publisher] = {
    "instagram_plate": InstagramPlate("instagram_plate", ("IG_ACCESS_TOKEN",), ("social/{id}/plate.png",), True),
    "instagram_carousel": InstagramCarousel("instagram_carousel", ("IG_ACCESS_TOKEN",), tuple(f"social/{{id}}/carousel-{i}.png" for i in range(1, 5)), True),
    "instagram_story": InstagramStory("instagram_story", ("IG_ACCESS_TOKEN",), ("social/{id}/story.png",), True),
    "instagram_reel": InstagramReel("instagram_reel", ("IG_ACCESS_TOKEN",), ("reels/{id}.mp4",), True),
    "youtube_short": YouTubeShort("youtube_short", ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"), ("reels/{id}.mp4",)),
    "threads": Threads("threads", ("THREADS_ACCESS_TOKEN",)),
    "email": Email("email", ()),
    "site": Site("site", ()),
}


def connections() -> dict[str, list[str]]:
    """Channel -> the secrets it still lacks. An empty list means connected."""
    return {ch: p.missing() for ch, p in PUBLISHERS.items()}


def run(a: Atom, *, live: bool | None = None, only: str | None = None, skip: set[str] = frozenset()) -> dict[str, str]:
    """Publish one atom to each of its channels. Returns channel -> outcome."""
    live = ledger.publish_live() if live is None else live
    out: dict[str, str] = {}
    for ch in a.channels:
        if (only and ch != only) or ch in skip:
            continue
        pub = PUBLISHERS[ch]
        absent = [str(p) for p in pub.paths(a) if not p.exists()]
        if absent:
            out[ch] = "failed"
            ledger.record(a.id, ch, "failed", error="not rendered: " + ", ".join(absent))
            continue
        if ledger.already_posted(a.id, ch):
            out[ch] = "already posted"
            continue
        missing = pub.missing()
        if not (live and a.publishable and not missing):
            why = "atom not approved" if not a.publishable else "PUBLISH_LIVE is off" if not live else "not connected: " + ", ".join(missing)
            print(f"dry run  {a.id:<28} {ch:<19} {why}")
            print("         " + json.dumps(pub.payload(a), ensure_ascii=False)[:400])
            ledger.record(a.id, ch, "dry_run", error=why)
            out[ch] = "dry run"
            continue
        try:
            res = pub.send(a)
            ledger.record(a.id, ch, "posted", external_id=res.external_id, url=res.url)
            if res.note:
                print(f"::warning::{res.note}")
            print(f"posted   {a.id:<28} {ch:<19} {res.url or res.external_id}")
            out[ch] = "posted"
        except Exception as e:  # noqa: BLE001  one channel failing never stops the others
            ledger.record(a.id, ch, "failed", error=str(e)[:500])
            ledger.event("publish_failed", {"atom": a.id, "channel": ch, "error": str(e)[:300]})
            print(f"::error::{a.id} {ch}: {e}")
            out[ch] = "failed"
    return out


CATCH_UP_DAYS = 1


def due(day: dt.date, all_atoms: list[Atom]) -> list[Atom]:
    """Approved atoms for today, or missed yesterday, with a channel still not posted.

    Older atoms are never swept up, so switching to live cannot release a backlog in one burst.
    Post an older atom on purpose with `daily --atom <id>`.
    """
    first = day - dt.timedelta(days=CATCH_UP_DAYS)
    return [a for a in all_atoms if a.publishable and first <= a.publish_on <= day
            and any(not ledger.already_posted(a.id, ch) for ch in a.channels)]

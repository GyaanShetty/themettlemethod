"""The atom: one written lesson, the single source for every output.

The YAML keeps its older fields (slug, summary, article, scenes for the reel script). The fields
below are what the plate, carousel, story, thread, email and dashboard read.
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
FOLDER_TYPE = {"models": "model", "concepts": "concept", "skills": "skill", "quotes": "quote", "laws": "law"}
Channel = Literal["instagram_plate", "instagram_carousel", "instagram_story", "instagram_reel",
                  "youtube_short", "threads", "email", "site"]
BANNED = re.compile(r"[!\U0001F300-\U0001FAFF☀-➿]")  # no exclamation marks, no emoji; U+2720 is allowed in templates only


class Atom(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    type: Literal["model", "concept", "skill", "quote", "law"]
    pillar: Literal["mind", "body", "faith", "relationships"]
    number: Optional[int] = None
    title: str
    kicker: str = Field(max_length=32)
    headline: str
    sub: str = Field(max_length=120)
    body: str
    source: Optional[str] = None
    image: str
    publish_on: dt.date
    status: Literal["draft", "approved", "scheduled", "published", "held"] = "draft"
    channels: list[Channel] = Field(min_length=1)

    @field_validator("headline")
    @classmethod
    def _headline(cls, v: str) -> str:
        lines = v.strip().split("\n")
        if len(lines) > 3:
            raise ValueError("headline has more than 3 lines")
        if any(len(line) > 24 for line in lines) and len(lines) > 1:
            raise ValueError("a headline line is over 24 characters; it will not fit at its size")
        if len(v.replace("\n", " ")) > 60:
            raise ValueError("headline is over 60 characters")
        if not v.rstrip().endswith("."):
            raise ValueError("headline ends with a full stop")
        if BANNED.search(v):
            raise ValueError("no exclamation marks or emoji")
        words = v.replace("\n", " ").split()
        if sum(w[:1].isupper() for w in words[1:]) > len(words) / 2 and len(words) > 3:
            raise ValueError("headline is in sentence case, not title case")
        return v.strip()

    @field_validator("kicker", "sub")
    @classmethod
    def _voice(cls, v: str) -> str:
        if BANNED.search(v):
            raise ValueError("no exclamation marks or emoji")
        return v.strip()

    @model_validator(mode="after")
    def _rules(self) -> "Atom":
        if self.type in ("quote", "law") and not self.source:
            raise ValueError(f"a {self.type} needs a source")
        if self.source and " · " not in self.source:
            raise ValueError("source reads 'Author · Work', for example 'Seneca · Letters, XIII'")
        if not image_path(self.image).exists():
            raise ValueError(f"image '{self.image}' is not in web/assets")
        return self

    @property
    def publishable(self) -> bool:
        """Only an approved atom may ever be posted."""
        return self.status in ("approved", "scheduled", "published")


def image_path(key: str) -> Path:
    base = ROOT / "web" / "assets" / key
    for ext in (".webp", ".jpg", ".png"):
        if base.with_suffix(ext).exists():
            return base.with_suffix(ext)
    return base.with_suffix(".webp")


def from_file(path: Path) -> Atom:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Atom(
        id=raw.get("id", raw.get("slug", path.stem)),
        type=raw.get("type", FOLDER_TYPE.get(path.parent.name, path.parent.name)),
        pillar=raw.get("pillar"), number=raw.get("number"), title=raw.get("title"),
        kicker=raw.get("kicker"), headline=raw.get("headline"),
        sub=raw.get("sub", raw.get("summary")), body=raw.get("body", raw.get("article")),
        source=raw.get("source"), image=raw.get("image"), publish_on=raw.get("publish_on"),
        status=raw.get("status", "draft"), channels=raw.get("channels", []),
    )


def all_atoms() -> list[Atom]:
    files = sorted(p for d in FOLDER_TYPE if (CONTENT / d).is_dir() for p in (CONTENT / d).glob("*.yaml"))
    return sorted((from_file(p) for p in files), key=lambda a: (a.publish_on, a.id))


def get(atom_id: str) -> Atom:
    for a in all_atoms():
        if a.id == atom_id:
            return a
    raise KeyError(atom_id)

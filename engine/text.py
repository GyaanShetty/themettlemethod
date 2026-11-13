"""Text outputs from an atom: the thread and the morning email (HTML and plain text)."""
from __future__ import annotations

import html
import re

from . import brand
from .atoms import Atom

THREAD_LIMIT = 500


def _plain(md: str) -> str:
    md = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", md)
    return re.sub(r"[*_`#>]", "", md)


def _sentences(a: Atom, n: int) -> list[str]:
    para = next((p for p in a.body.split("\n\n") if p.strip() and not p.lstrip().startswith(("#", "-", "*", "1."))), "")
    parts = re.split(r"(?<=[.?])\s+", " ".join(_plain(para).split()))
    return [p for p in parts if p][:n]


def thread(a: Atom) -> str:
    """Three to five lines, one idea, under the Threads limit."""
    lines = [a.headline.replace("\n", " "), a.sub] + _sentences(a, 2)
    if a.source:
        lines.append(a.source)
    lines = list(dict.fromkeys(lines))[:5]
    while len("\n\n".join(lines)) > THREAD_LIMIT and len(lines) > 3:
        lines.pop(-2 if a.source else -1)
    out = "\n\n".join(lines)
    if not 3 <= len(lines) <= 5 or len(out) > THREAD_LIMIT:
        raise ValueError(f"{a.id}: thread does not fit in 3 to 5 lines under {THREAD_LIMIT} characters")
    return out


def email(a: Atom, site_url: str, unsubscribe: str = "{{unsubscribe_url}}") -> dict:
    """The morning lesson. Table layout and inline styles, because mail clients ignore the rest."""
    c = lambda n: brand.color(n, "paper")  # noqa: E731
    url = f"{site_url.rstrip('/')}/library/{a.type}s/{a.id}/"
    paras = [p for p in a.body.split("\n\n") if p.strip() and not re.match(r"\s*(#|[-*] |\d+\. )", p)][:2]
    label = f"PILLAR {brand.PILLARS[a.pillar]} · {a.pillar.upper()}"
    serif, sans = "Marcellus, Georgia, 'Times New Roman', serif", "'Hanken Grotesk', Helvetica, Arial, sans-serif"
    body_html = "".join(f'<p style="margin:0 0 16px;font:400 17px/1.6 {sans};color:{c("ink")}">{html.escape(_plain(p))}</p>' for p in paras)
    src = f'<p style="margin:0 0 16px;font:400 12px {serif};letter-spacing:.12em;text-transform:uppercase;color:{c("ink-muted")}">{html.escape(a.source)}</p>' if a.source else ""
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>{html.escape(a.title)}</title></head>
<body style="margin:0;background:{c('paper')}"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{c('paper')}"><tr><td align="center" style="padding:32px 16px">
<table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%">
<tr><td style="padding-bottom:12px;border-bottom:1px solid {c('hairline')};font:400 12px {serif};letter-spacing:.2em;color:{c('ink-muted')}">&#10016; {label}</td></tr>
<tr><td style="padding:28px 0 8px;font:400 12px {serif};letter-spacing:.2em;text-transform:uppercase;color:{c('oxblood')}">{html.escape(a.kicker)}</td></tr>
<tr><td style="padding-bottom:12px;font:400 36px/1.1 {serif};color:{c('ink')}">{html.escape(a.headline).replace(chr(10), '<br>')}</td></tr>
<tr><td style="padding-bottom:24px;font:400 20px/1.5 {sans};color:{c('ink-muted')}">{html.escape(a.sub)}</td></tr>
<tr><td>{body_html}{src}</td></tr>
<tr><td style="padding:8px 0 32px"><a href="{url}" style="font:600 15px {sans};color:{c('oxblood')}">Read the full lesson</a></td></tr>
<tr><td style="padding-top:20px;border-top:1px solid {c('hairline')};font:400 13px/1.6 {sans};color:{c('ink-muted')}">The Mettle Method. Obey the process.<br>The daily lesson is free. <a href="{unsubscribe}" style="color:{c('ink-muted')}">Stop these emails in one click</a>.</td></tr>
</table></td></tr></table></body></html>"""
    text = "\n\n".join([label, a.headline.replace("\n", " "), a.sub] + [_plain(p) for p in paras] + ([a.source] if a.source else [])
                       + [f"Read the full lesson: {url}", f"The daily lesson is free. Stop these emails: {unsubscribe}"])
    return {"subject": f"{a.title}. {a.sub}"[:120].rstrip(), "html": doc, "text": text}

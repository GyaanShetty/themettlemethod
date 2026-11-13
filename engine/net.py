"""Every external call goes through here: a timeout, retries with backoff, and a line in the event log."""
from __future__ import annotations

import time
from urllib.parse import urlsplit

import requests

RETRY_ON = {408, 425, 429, 500, 502, 503, 504}


class CallFailed(RuntimeError):
    pass


def call(method: str, url: str, *, tries: int = 4, timeout: float = 60, log: bool = True, **kw) -> requests.Response:
    host, last = urlsplit(url).netloc, ""
    for attempt in range(1, tries + 1):
        try:
            r = requests.request(method, url, timeout=timeout, **kw)
            if r.status_code < 400:
                _log(log, host, method, r.status_code, attempt)
                return r
            last = f"{r.status_code} {r.text[:300]}"
            if r.status_code not in RETRY_ON:
                break
        except requests.RequestException as e:
            last = type(e).__name__
        if attempt < tries:
            time.sleep(min(2 ** attempt, 30))
    _log(log, host, method, last[:80], attempt)
    raise CallFailed(f"{method} {host}{urlsplit(url).path}: {last}")


def _log(log: bool, host: str, method: str, status, attempts: int) -> None:
    if log:
        from . import ledger
        ledger.event("external_call", {"host": host, "method": method, "status": status, "attempts": attempts})

"""Text to speech with word timings.

edge-tts (Microsoft neural voices, free) is the default and runs in CI.
espeak-ng is an offline fallback for local testing only; its word timings are estimated.
Every call returns a 48 kHz mono WAV and a list of (word, start, end) in seconds.
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Word:
    text: str
    start: float
    end: float


def _duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def _to_wav(src: Path, dst: Path) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-ac", "1", "-ar", "48000",
                    "-c:a", "pcm_s16le", str(dst)], check=True)


async def _edge(text: str, voice: str, rate: str, mp3: Path) -> list[Word]:
    import edge_tts

    comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    words: list[Word] = []
    with open(mp3, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7
                words.append(Word(chunk["text"], start, start + chunk["duration"] / 1e7))
    return words


def _espeak(text: str, wav: Path) -> list[Word]:
    raw = wav.with_suffix(".raw.wav")
    subprocess.run(["espeak-ng", "-s", "165", "-w", str(raw), text], check=True)
    _to_wav(raw, wav)
    raw.unlink()
    total = _duration(wav)
    toks = text.split()
    # weight by length; punctuation adds a pause
    weights = [len(t) + 2 + (6 if re.search(r"[.,!?;:]$", t) else 0) for t in toks]
    scale = (total - 0.15) / sum(weights)
    t, words = 0.08, []
    for tok, w in zip(toks, weights):
        dur = w * scale
        words.append(Word(tok, t, t + dur * 0.85))
        t += dur
    return words


def _attach_punct(text: str, words: list[Word]) -> list[Word]:
    """edge-tts drops punctuation from word events; put it back from the source text
    so captions read naturally."""
    out, pos = [], 0
    for w in words:
        i = text.find(w.text, pos)
        if i < 0:
            out.append(w)
            continue
        j = i + len(w.text)
        m = re.match(r"[^\s\w]*", text[j:])
        tail = m.group(0) if m else ""
        out.append(Word(w.text + tail, w.start, w.end))
        pos = j + len(tail)
    return out


def speak(text: str, out_wav: Path, voice: str, rate: str = "+0%") -> list[Word]:
    """Synthesize text to out_wav. Uses espeak-ng when TTS_ENGINE=espeak or edge-tts is unreachable."""
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    engine = os.environ.get("TTS_ENGINE", "edge")
    if engine == "edge":
        mp3 = out_wav.with_suffix(".mp3")
        try:
            # own thread: Playwright's sync API already runs an event loop in this one
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(1) as ex:
                words = ex.submit(asyncio.run, _edge(text, voice, rate, mp3)).result(timeout=120)
            _to_wav(mp3, out_wav)
            mp3.unlink()
            if not words:
                raise RuntimeError("edge-tts returned no word timings")
            return _attach_punct(text, words)
        except Exception as e:  # noqa: BLE001
            if not shutil.which("espeak-ng") or os.environ.get("CI"):
                raise
            print(f"  edge-tts unavailable ({type(e).__name__}); falling back to espeak-ng")
    return _espeak(text, out_wav)


def duration(path: Path) -> float:
    return _duration(path)

"""Render a mental-model atom to a vertical reel (1080x1920, 30 fps, H.264 + AAC).

Per scene: speak each line (word timings), build the scene's audio padded to a whole number of
frames, film the HTML scene frame by frame (a frame is only re-shot when its pixels change),
encode one mp4 per scene. Then join scenes with the concat demuxer (-c copy) and add the
normalised voice track (-c:v copy).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import wave
from array import array
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from . import tts
from .content import ROOT, config, load_model, segments

TPL = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"), autoescape=False)
RATE = 48000
GAP, LEAD, TAIL, CTA_TAIL = 0.16, 0.22, 0.42, 1.3
NO_CAPTIONS = {"quote", "cta"}
ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-g", "60"]


def _silence(sec: float) -> array:
    return array("h", bytes(2 * int(round(sec * RATE))))


def _read(path: Path) -> array:
    with wave.open(str(path)) as w:
        assert w.getframerate() == RATE and w.getnchannels() == 1
        a = array("h")
        a.frombytes(w.readframes(w.getnframes()))
        return a


def _write(path: Path, a: array) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(a.tobytes())


def _scene_audio(scene: dict, i: int, n: int, out: Path, cfg: dict, fps: int):
    """Speak the scene's lines; return (frames, words with scene-relative times, segment starts, voice length)."""
    pcm = _silence(0 if scene["layout"] == "hook" else LEAD)
    words, starts = [], []
    for k, line in enumerate(segments(scene)):
        if k:
            pcm += _silence(GAP)
        t0 = len(pcm) / RATE
        wav = out / f"s{i:02d}_{k}.wav"
        ws = tts.speak(line, wav, cfg["reels"]["voice"], cfg["reels"].get("rate", "+0%"), cfg["reels"].get("pitch", "+0Hz"))
        starts.append(round(t0, 3))
        words += [{"text": w.text, "s": round(t0 + w.start, 3), "e": round(t0 + w.end, 3)} for w in ws]
        pcm += _read(wav)
        wav.unlink()
    voice_end = len(pcm) / RATE
    pcm += _silence(CTA_TAIL if i == n - 1 else TAIL)
    frames = math.ceil(len(pcm) / RATE * fps)
    pcm += _silence(frames / fps - len(pcm) / RATE)   # pad to a whole frame so scenes stay in sync
    _write(out / f"s{i:02d}.wav", pcm[: int(round(frames / fps * RATE))])
    return frames, words, starts, voice_end


def _page_html(m: dict, scene: dict, words, starts, voice_end, cfg) -> str:
    b = cfg["brand"]
    site = b.get("site_url", "")
    data = {
        "scene": scene, "words": words, "segStarts": starts, "voiceDur": voice_end,
        "number": m["number"], "title": m["title"], "category": m["category"],
        "captions": scene.get("captions", scene["layout"] not in NO_CAPTIONS),
        "brand": {"name": b["name"], "tagline": b["tagline"], "handle": b["handle"],
                  "site": "" if "YOUR-" in site else site.replace("https://", "")},
    }
    from . import brand
    from .atoms import image_path
    data["image"] = image_path(m["image"]).as_uri() if m.get("image") else ""
    data["seal"] = (ROOT / "web" / "assets" / "seal.png").as_uri()
    data["pillar"] = f"PILLAR {brand.PILLARS[m['pillar']]} · {m['pillar'].upper()}" if m.get("pillar") else m["category"].upper()
    data["numeral"] = brand.roman(m["number"])
    return TPL.get_template("reel.html").render(data=data, brand_css=brand.css("ink"))


def _hash(*parts) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(json.dumps(p, sort_keys=True, default=str).encode())
    h.update((Path(__file__).parent / "templates" / "reel.html").read_bytes())
    h.update((ROOT / "brand" / "tokens.json").read_bytes())
    h.update(os.environ.get("TTS_ENGINE", "edge").encode())
    return h.hexdigest()[:16]


def render(slug: str, preview: bool = False) -> Path:
    from playwright.sync_api import sync_playwright

    m, cfg = load_model(slug), config()
    fps = cfg["reels"].get("fps", 30)
    out = ROOT / "build" / "reels" / slug
    out.mkdir(parents=True, exist_ok=True)
    n = len(m["scenes"])
    parts: list[Path] = []
    stills: list[Path] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        for i, scene in enumerate(m["scenes"]):
            key = _hash(scene, m["title"], m["number"], m["category"], m.get("image"), m.get("pillar"), cfg["brand"], cfg["reels"], i == n - 1)
            mp4, meta = out / f"s{i:02d}.mp4", out / f"s{i:02d}.json"
            cached = meta.exists() and json.loads(meta.read_text()).get("key") == key and (out / f"s{i:02d}.wav").exists()

            if cached:
                info = json.loads(meta.read_text())
            else:
                frames, words, starts, voice_end = _scene_audio(scene, i, n, out, cfg, fps)
                info = {"key": key, "frames": frames, "words": words, "starts": starts, "voice_end": voice_end}
                meta.write_text(json.dumps(info))
                if mp4.exists():
                    mp4.unlink()

            html = out / f"s{i:02d}.html"
            html.write_text(_page_html(m, scene, info["words"], info["starts"], info["voice_end"], cfg), encoding="utf-8")
            page.goto(html.as_uri())
            page.wait_for_function("window.READY === true")

            if preview:
                # the moment with the most on screen: just before the scene ends
                t = info["frames"] / fps - 0.35
                page.evaluate(f"render({t})")
                still = out / f"still_{i:02d}.jpg"
                page.screenshot(path=str(still), type="jpeg", quality=88)
                stills.append(still)
                continue

            if not mp4.exists():
                tmp = out / f"s{i:02d}.part.mp4"
                ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "image2pipe", "-framerate", str(fps),
                                       "-c:v", "mjpeg", "-i", "-", *ENC, "-r", str(fps), str(tmp)],
                                      stdin=subprocess.PIPE)
                last_key, last = None, b""
                shots = 0
                for f in range(info["frames"]):
                    k = page.evaluate(f"render({f / fps})")
                    if k != last_key:
                        last = page.screenshot(type="jpeg", quality=92)
                        last_key = k
                        shots += 1
                    ff.stdin.write(last)
                ff.stdin.close()
                if ff.wait() != 0:
                    raise RuntimeError(f"ffmpeg failed on scene {i}")
                tmp.rename(mp4)
                print(f"  scene {i} {scene['layout']:<9} {info['frames'] / fps:5.2f}s  {shots} shots / {info['frames']} frames")
            parts.append(mp4)
        browser.close()

    if preview:
        sheet = out / "preview.jpg"
        cols = min(4, len(stills))
        rows = math.ceil(len(stills) / cols)
        inputs = sum((["-i", str(s)] for s in stills), [])
        grid = "".join(f"[{k}:v]scale=360:640[v{k}];" for k in range(len(stills)))
        pads = len(stills)
        layout = "|".join(f"{(k % cols) * 360}_{(k // cols) * 640}" for k in range(pads))
        subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex",
                        grid + "".join(f"[v{k}]" for k in range(pads)) + f"xstack=inputs={pads}:layout={layout}:fill=black",
                        "-frames:v", "1", str(sheet)], check=True)
        return sheet

    # join scenes, then add sound
    lst = out / "scenes.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts))
    video = out / "video.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(video)], check=True)

    pcm = array("h")
    for i in range(n):
        pcm += _read(out / f"s{i:02d}.wav")
    voice = out / "voice.wav"
    _write(voice, pcm)

    final = ROOT / "build" / "reels" / f"{slug}.mp4"
    tmp = final.with_suffix(".part.mp4")
    music = cfg["reels"].get("music")
    if music:
        vol = cfg["reels"].get("music_volume", 0.1)
        af = ["-stream_loop", "-1", "-i", str(ROOT / music), "-filter_complex",
              f"[1:a]loudnorm=I=-16:TP=-1.5[v];[2:a]volume={vol}[m];[v][m]amix=inputs=2:duration=first:normalize=0[a]",
              "-map", "0:v", "-map", "[a]"]
    else:
        af = ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-map", "0:v", "-map", "1:a"]
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(voice), *af,
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest",
                    "-movflags", "+faststart", str(tmp)], check=True)
    tmp.rename(final)

    # poster for the website: the title scene, fully in
    title_i = next((k for k, s in enumerate(m["scenes"]) if s["layout"] == "title"), 0)
    t_in = sum(json.loads((out / f"s{k:02d}.json").read_text())["frames"] for k in range(title_i)) / fps + 1.2
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t_in:.2f}", "-i", str(final), "-frames:v", "1",
                    "-q:v", "3", str(ROOT / "build" / "reels" / f"{slug}.jpg")], check=True)
    return final

"""Video-Agent: KI-Stimme + Stock-Videos + Untertitel = fertiges Hochkant-Video (1080x1920)."""
import asyncio
import subprocess
from pathlib import Path

import requests

from core.storage import env

W, H = 1080, 1920


# ---------- Stimme ----------

async def _tts(text, voice, rate, mp3_path):
    import edge_tts

    try:
        com = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    except TypeError:  # ältere edge-tts-Versionen kennen "boundary" nicht
        com = edge_tts.Communicate(text, voice, rate=rate)
    marks = []
    with open(mp3_path, "wb") as f:
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                start = chunk["offset"] / 1e7
                marks.append((start, start + chunk["duration"] / 1e7, chunk["text"]))
    return marks


# ---------- Untertitel ----------

def _ass_time(t):
    h, rest = divmod(max(t, 0), 3600)
    m, s = divmod(rest, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _ass_color(hex_color):
    """'#FFD400' → ASS-Farbe '&H00D4FF&' (ASS speichert Blau-Grün-Rot)."""
    h = hex_color.lstrip("#").upper()
    return f"&H{h[4:6]}{h[2:4]}{h[0:2]}&"


def _word_timings(marks):
    """Macht aus Wort- oder Satzmarken eine Liste (start, ende, wort) pro Wort."""
    words = []
    for start, end, text in marks:
        parts = text.split()
        total = sum(len(p) for p in parts) or 1
        t = start
        for p in parts:
            d = (end - start) * len(p) / total
            words.append((t, t + d, p))
            t += d
    return words


def _group_words(words, max_words=3, max_chars=16):
    """Kurze, gut lesbare Häppchen: max. 3 Wörter / 16 Zeichen, Umbruch nach Satzzeichen."""
    groups, buf = [], []
    for w in words:
        if buf and (len(buf) >= max_words or len(" ".join(x[2] for x in buf + [w])) > max_chars):
            groups.append(buf)
            buf = []
        buf.append(w)
        if w[2].endswith((".", "!", "?", ",", ":", ";")):
            groups.append(buf)
            buf = []
    if buf:
        groups.append(buf)
    return groups


def _write_ass(marks, sub_cfg, font, path):
    base = _ass_color(sub_cfg.get("farbe", "#FFFFFF"))
    highlight = _ass_color(sub_cfg.get("hervorhebung", "#FFD400"))
    size = sub_cfg.get("groesse", 70)
    groups = _group_words(_word_timings(marks))

    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{font},{size},&H00{base[2:-1]},&H00{base[2:-1]},&H00000000,&H96000000,-1,0,0,0,100,100,1,0,1,5,2,2,120,120,560,1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for gi, group in enumerate(groups):
        # Gruppe bleibt stehen bis zur nächsten (kein Flackern bei kurzen Pausen)
        next_start = groups[gi + 1][0][0] if gi + 1 < len(groups) else group[-1][1] + 0.3
        clean = [w[2].replace("{", "(").replace("}", ")").upper() for w in group]
        for wi, (s, e, _) in enumerate(group):
            end = group[wi + 1][0] if wi + 1 < len(group) else next_start
            text = " ".join(
                f"{{\\c{highlight}}}{w}{{\\c{base}}}" if i == wi else w for i, w in enumerate(clean)
            )
            lines.append(f"Dialogue: 0,{_ass_time(s)},{_ass_time(end)},Default,,0,0,0,,{text}")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


# ---------- Stock-Videos ----------

def _pixabay_clip(query, used_ids):
    r = requests.get(
        "https://pixabay.com/api/videos/",
        params={"key": env("PIXABAY_API_KEY"), "q": query[:100], "lang": "en",
                "safesearch": "true", "min_height": 1080, "per_page": 20},
        timeout=30,
    )
    r.raise_for_status()
    for hit in r.json().get("hits", []):
        if hit["id"] in used_ids:
            continue
        # Pixabay-Videos sind meist Querformat → wir nehmen die größte Version
        # unter ~80 MB, damit nach dem Zuschnitt auf Hochformat genug Schärfe bleibt
        for size in ("large", "medium"):
            v = hit["videos"].get(size) or {}
            if v.get("url") and v.get("height", 0) >= 1080 and v.get("size", 0) < 80_000_000:
                used_ids.add(hit["id"])
                return v["url"]
    return None


def _stock_clip(query, used_ids):
    if env("PIXABAY_API_KEY", required=False):
        return _pixabay_clip(query, used_ids)
    return _pexels_clip(query, used_ids)


def _pexels_clip(query, used_ids):
    r = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": env("PEXELS_API_KEY")},
        params={"query": query, "orientation": "portrait", "per_page": 15},
        timeout=30,
    )
    r.raise_for_status()
    for v in r.json().get("videos", []):
        if v["id"] in used_ids:
            continue
        files = [f for f in v["video_files"] if f.get("height") and f.get("width")
                 and f["height"] >= 1280 and f["width"] < f["height"]]
        if files:
            used_ids.add(v["id"])
            return min(files, key=lambda f: f["height"])["link"]
    return None


def _download(url, path):
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for block in r.iter_content(1 << 20):
                f.write(block)


# ---------- Zusammenbau ----------

def _run(cmd, cwd):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg-Fehler: {result.stderr[-1500:]}")
    return result.stdout


def _duration(path, cwd):
    out = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], cwd)
    return float(out.strip())


def render(cfg, script, workdir):
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    vcfg = cfg["video"]
    scenes = script["scenes"]
    text = " ".join(s["text"].strip() for s in scenes)

    marks = asyncio.run(_tts(text, vcfg["stimme"], vcfg["sprechtempo"], workdir / "voice.mp3"))
    _write_ass(marks, vcfg.get("untertitel", {}), vcfg["schriftart"], workdir / "subs.ass")
    audio_len = _duration("voice.mp3", workdir)
    total = audio_len + 0.6

    # Jede Szene bekommt Bildschirmzeit passend zur Länge ihres Textes
    char_total = sum(len(s["text"]) for s in scenes)
    used = set()
    segments = []
    for i, scene in enumerate(scenes):
        dur = max(total * len(scene["text"]) / char_total, 1.5)
        url = _stock_clip(scene["search"], used) or _stock_clip(vcfg["ersatz_suche"], used)
        if not url:
            raise RuntimeError(f"Kein Stock-Video gefunden für '{scene['search']}'")
        raw = workdir / f"raw_{i}.mp4"
        _download(url, raw)
        seg = f"seg_{i}.mp4"
        _run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", raw.name, "-t", f"{dur:.2f}",
              "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps=30,setsar=1",
              "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "-pix_fmt", "yuv420p", seg], workdir)
        segments.append(seg)

    (workdir / "list.txt").write_text("".join(f"file '{s}'\n" for s in segments), encoding="utf-8")
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "video.mp4"], workdir)
    _run(["ffmpeg", "-y", "-i", "video.mp4", "-i", "voice.mp3", "-vf", "subtitles=subs.ass",
          "-af", "apad", "-shortest", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
          "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "final.mp4"], workdir)
    return workdir / "final.mp4"

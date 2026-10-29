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


def _subtitle_chunks(marks, max_words=3):
    """Teilt Wort- oder Satzmarken in kurze 1-3-Wort-Einblendungen (TikTok-Stil)."""
    chunks = []
    for start, end, text in marks:
        words = text.split()
        groups = [words[i : i + max_words] for i in range(0, len(words), max_words)]
        total_chars = sum(len(" ".join(g)) for g in groups) or 1
        t = start
        for g in groups:
            part = " ".join(g)
            d = (end - start) * len(part) / total_chars
            chunks.append((t, t + d, part))
            t += d
    # Lücken schließen, damit der Text nicht flackert
    merged = []
    for i, (s, e, txt) in enumerate(chunks):
        if i + 1 < len(chunks) and chunks[i + 1][0] - e < 0.4:
            e = chunks[i + 1][0]
        merged.append((s, e, txt))
    return merged


def _write_ass(marks, font, path):
    if marks and len(marks[0][2].split()) == 1:  # Wortmarken → zu Gruppen zusammenfassen
        grouped, buf = [], []
        for m in marks:
            buf.append(m)
            if len(buf) == 3 or m[2].endswith((".", "!", "?", ",")):
                grouped.append((buf[0][0], buf[-1][1], " ".join(x[2] for x in buf)))
                buf = []
        if buf:
            grouped.append((buf[0][0], buf[-1][1], " ".join(x[2] for x in buf)))
        chunks = _subtitle_chunks(grouped)
    else:
        chunks = _subtitle_chunks(marks)

    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{font},92,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,7,3,2,80,80,560,1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for s, e, txt in chunks:
        clean = txt.replace("{", "(").replace("}", ")").replace("\n", " ").upper()
        lines.append(f"Dialogue: 0,{_ass_time(s)},{_ass_time(e)},Default,,0,0,0,,{clean}")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


# ---------- Stock-Videos ----------

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
    _write_ass(marks, vcfg["schriftart"], workdir / "subs.ass")
    audio_len = _duration("voice.mp3", workdir)
    total = audio_len + 0.6

    # Jede Szene bekommt Bildschirmzeit passend zur Länge ihres Textes
    char_total = sum(len(s["text"]) for s in scenes)
    used = set()
    segments = []
    for i, scene in enumerate(scenes):
        dur = max(total * len(scene["text"]) / char_total, 1.5)
        url = _pexels_clip(scene["search"], used) or _pexels_clip(vcfg["ersatz_suche"], used)
        if not url:
            raise RuntimeError(f"Kein Stock-Video gefunden für '{scene['search']}'")
        raw = workdir / f"raw_{i}.mp4"
        _download(url, raw)
        seg = f"seg_{i}.mp4"
        _run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", raw.name, "-t", f"{dur:.2f}",
              "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps=30,setsar=1",
              "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", seg], workdir)
        segments.append(seg)

    (workdir / "list.txt").write_text("".join(f"file '{s}'\n" for s in segments), encoding="utf-8")
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "video.mp4"], workdir)
    _run(["ffmpeg", "-y", "-i", "video.mp4", "-i", "voice.mp3", "-vf", "subtitles=subs.ass",
          "-af", "apad", "-shortest", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
          "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "final.mp4"], workdir)
    return workdir / "final.mp4"

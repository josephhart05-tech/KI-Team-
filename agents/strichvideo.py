"""Strichmännchen-Video: animierte Szenen, Text Wort für Wort, eigene Musik – keine Stimme, keine Stock-Videos.

Jede Szene im Skript hat:
  text     – Bildschirmtext (max. ~12 Wörter). Wörter in *Sternchen* leuchten gold.
  motiv    – eins der Motive aus MOTIVE (siehe unten)
  stichwort – optional: kurze Zahl/Wort fürs Motiv (z. B. "TAG 30", "5 KURSE", "1 STD")
"""
import math
import subprocess
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
FPS = 30

BG = (10, 10, 10)
GOLD = (201, 162, 39)
CREAM = (243, 238, 227)
GREY = (120, 116, 108)
RED = (214, 72, 60)

MOTIVE = {
    "figur_denkt": "Figur grübelt, Fragezeichen über dem Kopf",
    "figur_frust": "Figur lässt den Kopf hängen, graue Wolke",
    "figur_jubel": "Figur reißt die Arme hoch, Funken",
    "figur_laptop": "Figur sitzt am Laptop und arbeitet",
    "figur_handy": "Figur starrt aufs Handy, Zeit verrinnt",
    "figur_laeuft": "Figur läuft los Richtung Ziel-Flagge",
    "treppe": "Figur steigt Stufe für Stufe eine Treppe hoch",
    "stapel": "Figur neben einem wachsenden Bücher-/Kurs-Stapel",
    "uhr": "große Uhr, Zeiger dreht sich",
    "kalender": "Kalenderblatt, Tage zählen hoch (stichwort = z. B. TAG 30)",
    "checkliste": "3 Punkte werden abgehakt",
    "chart": "Kurve: lange flach, dann steil nach oben",
    "zwei_wege": "Figur an einer Weggabelung",
    "gluehbirne": "Glühbirne geht über der Figur an",
    "zahl": "große Zahl/Wort zählt hoch (stichwort)",
}

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
_fonts = {}


def _font(size):
    if size not in _fonts:
        for p in _FONT_CANDIDATES:
            if Path(p).exists():
                _fonts[size] = ImageFont.truetype(p, size)
                break
        else:
            _fonts[size] = ImageFont.load_default(size)
    return _fonts[size]


def _ffmpeg():
    """ffmpeg vom System – oder aus pip (imageio-ffmpeg), falls apt bei GitHub ausfällt."""
    import shutil
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def _seg(t, a, b):
    return max(0.0, min(1.0, (t - a) / (b - a))) if b > a else 1.0


def _mix(c, a):
    """Farbe c mit Deckkraft a auf schwarzem Grund."""
    return tuple(int(BG[i] + (c[i] - BG[i]) * a) for i in range(3))


# ---------- Strichmännchen ----------

def _figure(d, x, y, s=1.0, pose="steht", t=0.0, color=CREAM, a=1.0):
    """Zeichnet eine Figur mit Füßen bei (x, y)."""
    c = _mix(color, a)
    lw = int(12 * s)
    head_r = 42 * s
    hip = (x, y - 150 * s)
    neck = (x, y - 300 * s)
    sway = math.sin(t * 6) * 4 * s
    if pose == "frust":
        neck = (x + 18 * s, y - 280 * s)
        head = (x + 45 * s, y - 300 * s - head_r * 0.6)
    else:
        head = (x + sway * 0.3, neck[1] - head_r - 6 * s)
    # Körper
    d.line([hip, neck], fill=c, width=lw)
    d.ellipse([head[0] - head_r, head[1] - head_r, head[0] + head_r, head[1] + head_r], outline=c, width=lw)
    # Beine
    if pose == "laeuft":
        ph = math.sin(t * 14)
        d.line([hip, (x + 60 * s * ph, y)], fill=c, width=lw)
        d.line([hip, (x - 60 * s * ph, y)], fill=c, width=lw)
    elif pose == "sitzt":
        knee = (x + 80 * s, y - 150 * s)
        d.line([hip, knee], fill=c, width=lw)
        d.line([knee, (x + 80 * s, y)], fill=c, width=lw)
    else:
        d.line([hip, (x - 45 * s, y)], fill=c, width=lw)
        d.line([hip, (x + 45 * s, y)], fill=c, width=lw)
    # Arme
    sh = (neck[0], neck[1] + 25 * s)
    if pose == "jubel":
        lift = math.sin(t * 10) * 15 * s
        d.line([sh, (x - 90 * s, sh[1] - 120 * s - lift)], fill=c, width=lw)
        d.line([sh, (x + 90 * s, sh[1] - 120 * s + lift)], fill=c, width=lw)
    elif pose == "denkt":
        d.line([sh, (x + 60 * s, sh[1] + 40 * s)], fill=c, width=lw)
        d.line([(x + 60 * s, sh[1] + 40 * s), (head[0] + 20 * s, head[1] + head_r)], fill=c, width=lw)
        d.line([sh, (x - 60 * s, sh[1] + 110 * s)], fill=c, width=lw)
    elif pose in ("tippt", "sitzt"):
        tap = math.sin(t * 30) * 8 * s
        d.line([sh, (x + 110 * s, sh[1] + 60 * s + tap)], fill=c, width=lw)
        d.line([sh, (x + 100 * s, sh[1] + 70 * s - tap)], fill=c, width=lw)
    elif pose == "handy":
        d.line([sh, (x + 50 * s, sh[1] + 20 * s)], fill=c, width=lw)
        d.line([(x + 50 * s, sh[1] + 20 * s), (x + 55 * s, head[1] + 10 * s)], fill=c, width=lw)
        d.rounded_rectangle([x + 40 * s, head[1] - 30 * s, x + 75 * s, head[1] + 30 * s],
                            radius=int(6 * s), outline=_mix(GOLD, a), width=int(6 * s))
        d.line([sh, (x - 50 * s, sh[1] + 120 * s)], fill=c, width=lw)
    elif pose == "frust":
        d.line([sh, (x - 10 * s, sh[1] + 150 * s)], fill=c, width=lw)
        d.line([sh, (x + 30 * s, sh[1] + 150 * s)], fill=c, width=lw)
    else:
        d.line([sh, (x - 70 * s, sh[1] + 110 * s)], fill=c, width=lw)
        d.line([sh, (x + 70 * s, sh[1] + 110 * s)], fill=c, width=lw)
    return head


def _ground(d, y=1420, a=1.0):
    d.line([(140, y), (940, y)], fill=_mix(GREY, 0.6 * a), width=4)


def _label(d, text, cx, cy, size, color, a=1.0):
    f = _font(size)
    w = d.textlength(text, font=f)
    d.text((cx - w / 2, cy - size / 2), text, font=f, fill=_mix(color, a))


# ---------- Motive ----------

def _motif(d, motiv, t, stichwort, a):
    G = 1420
    sw = (stichwort or "").upper()[:14]
    if motiv == "figur_denkt":
        _ground(d, G, a)
        head = _figure(d, 540, G, 1.1, "denkt", t, a=a)
        for i, dx in enumerate((-110, 0, 110)):
            q = _ease(_seg(t, 0.1 + i * 0.15, 0.35 + i * 0.15))
            bob = math.sin(t * 8 + i) * 10
            _label(d, "?", head[0] + dx, head[1] - 150 - 40 * q + bob, 90, GOLD, a * q)
    elif motiv == "figur_frust":
        _ground(d, G, a)
        head = _figure(d, 540, G, 1.1, "frust", t, a=a)
        cy = head[1] - 190
        for dx, r in ((-70, 55), (0, 75), (75, 55)):
            d.ellipse([head[0] + dx - r, cy - r, head[0] + dx + r, cy + r], fill=_mix((70, 70, 72), a))
        for i in range(7):
            yy = cy + 60 + ((t * 600 + i * 47) % 160)
            xx = head[0] - 90 + i * 30
            d.line([(xx, yy), (xx - 6, yy + 24)], fill=_mix((110, 130, 160), a * 0.8), width=4)
        if sw:
            _label(d, sw, 540, G + 110, 64, RED, a)
    elif motiv == "figur_jubel":
        _ground(d, G, a)
        jump = abs(math.sin(t * 9)) * 40
        head = _figure(d, 540, G - jump, 1.1, "jubel", t, a=a)
        for i in range(10):
            ang = i / 10 * 2 * math.pi + t * 2
            rr = 170 + 30 * math.sin(t * 7 + i)
            px, py = head[0] + math.cos(ang) * rr, head[1] + math.sin(ang) * rr
            d.ellipse([px - 7, py - 7, px + 7, py + 7], fill=_mix(GOLD, a))
        if sw:
            _label(d, sw, 540, G + 110, 64, GOLD, a)
    elif motiv == "figur_laptop":
        _ground(d, G, a)
        d.rectangle([380, G - 175, 440, G - 150], fill=_mix(GREY, a))  # Hocker
        _figure(d, 410, G, 1.0, "sitzt", t, a=a)
        d.line([(500, G - 230), (760, G - 230)], fill=_mix(CREAM, a), width=10)  # Tisch
        d.line([(740, G - 230), (740, G)], fill=_mix(CREAM, a), width=10)
        d.polygon([(560, G - 236), (700, G - 236), (720, G - 380), (590, G - 380)],
                  outline=_mix(GOLD, a), width=8)
        glow = 0.5 + 0.5 * math.sin(t * 6)
        d.line([(610, G - 340), (690, G - 340)], fill=_mix(GOLD, a * glow), width=6)
        if sw:
            _label(d, sw, 540, G + 110, 64, GOLD, a)
    elif motiv == "figur_handy":
        _ground(d, G, a)
        _figure(d, 470, G, 1.1, "handy", t, a=a)
        cx, cy, r = 760, G - 470, 85
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=_mix(CREAM, a), width=8)
        ang = t * 2 * math.pi * 3 - math.pi / 2
        d.line([(cx, cy), (cx + math.cos(ang) * 65, cy + math.sin(ang) * 65)], fill=_mix(RED, a), width=8)
        _label(d, sw or "2,5 STD", 760, cy + 140, 54, RED, a)
    elif motiv == "figur_laeuft":
        _ground(d, G, a)
        x = 220 + 480 * _ease(t)
        _figure(d, x, G, 1.0, "laeuft", t, a=a)
        d.line([(860, G), (860, G - 280)], fill=_mix(CREAM, a), width=8)
        wave_ = math.sin(t * 10) * 10
        d.polygon([(860, G - 280), (980, G - 245 + wave_), (860, G - 210)], fill=_mix(GOLD, a))
        if sw:
            _label(d, sw, 860, G - 330, 54, GOLD, a)
    elif motiv == "treppe":
        steps = 6
        sx, sy, stw, sth = 180, G, 120, 90
        shown = steps * _ease(_seg(t, 0, 0.7))
        for i in range(steps):
            q = max(0.0, min(1.0, shown - i))
            if q <= 0:
                continue
            x0, y0 = sx + i * stw, sy - (i + 1) * sth
            d.rectangle([x0, y0, x0 + stw - 8, sy], outline=_mix(GOLD, a * q), width=6)
        k = min(steps - 1, int(shown))
        fx = sx + k * stw + stw / 2
        fy = sy - (k + 1) * sth
        _figure(d, fx, fy, 0.75, "steht", t, a=a)
        if sw:
            _label(d, sw, 540, G + 110, 64, GOLD, a)
    elif motiv == "stapel":
        _ground(d, G, a)
        _figure(d, 330, G, 1.0, "denkt", t, a=a)
        n = 1 + int(6 * _ease(_seg(t, 0, 0.8)))
        for i in range(n):
            y1 = G - i * 62
            off = (i % 2) * 18
            d.rectangle([560 + off, y1 - 58, 820 + off, y1], outline=_mix(CREAM, a), width=6)
            d.line([(585 + off, y1 - 29), (700 + off, y1 - 29)], fill=_mix(GOLD, a), width=5)
        if sw:
            _label(d, sw, 690, G - n * 62 - 70, 58, RED, a)
    elif motiv == "uhr":
        cx, cy, r = 540, 1150, 230
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=_mix(CREAM, a), width=12)
        for i in range(12):
            ang = i / 12 * 2 * math.pi
            d.line([(cx + math.cos(ang) * (r - 30), cy + math.sin(ang) * (r - 30)),
                    (cx + math.cos(ang) * (r - 8), cy + math.sin(ang) * (r - 8))], fill=_mix(GREY, a), width=6)
        ang = t * 2 * math.pi * 2 - math.pi / 2
        d.line([(cx, cy), (cx + math.cos(ang) * 170, cy + math.sin(ang) * 170)], fill=_mix(GOLD, a), width=12)
        d.line([(cx, cy), (cx + math.cos(ang / 12 - 1) * 110, cy + math.sin(ang / 12 - 1) * 110)],
               fill=_mix(CREAM, a), width=14)
        if sw:
            _label(d, sw, 540, cy + r + 90, 72, GOLD, a)
    elif motiv == "kalender":
        x0, y0 = 340, 900
        d.rounded_rectangle([x0, y0, x0 + 400, y0 + 440], radius=24, outline=_mix(CREAM, a), width=10)
        d.rectangle([x0 + 5, y0 + 5, x0 + 395, y0 + 110], fill=_mix(RED, a))
        for rx in (x0 + 90, x0 + 310):
            d.line([(rx, y0 - 40), (rx, y0 + 30)], fill=_mix(CREAM, a), width=12)
        digits = "".join(ch for ch in sw if ch.isdigit())
        word = sw.replace(digits, "").strip() or "TAG"
        target = int(digits) if digits else 30
        val = max(1, int(round(target * _ease(_seg(t, 0, 0.65)))))
        _label(d, word, x0 + 200, y0 + 58, 56, CREAM, a)
        _label(d, str(val), x0 + 200, y0 + 270, 170, GOLD, a)
    elif motiv == "checkliste":
        items = [s.strip() for s in (stichwort or "").split("|") if s.strip()][:3] or ["", "", ""]
        for i in range(3):
            y = 940 + i * 170
            d.rounded_rectangle([200, y, 290, y + 90], radius=14, outline=_mix(CREAM, a), width=8)
            q = _ease(_seg(t, 0.15 + i * 0.22, 0.32 + i * 0.22))
            if q > 0:
                p1, p2, p3 = (218, y + 48), (240, y + 72), (275, y + 18)
                if q < 0.5:
                    m = q / 0.5
                    d.line([p1, (p1[0] + (p2[0] - p1[0]) * m, p1[1] + (p2[1] - p1[1]) * m)], fill=_mix(GOLD, a), width=12)
                else:
                    m = (q - 0.5) / 0.5
                    d.line([p1, p2, (p2[0] + (p3[0] - p2[0]) * m, p2[1] + (p3[1] - p2[1]) * m)],
                           fill=_mix(GOLD, a), width=12, joint="curve")
            if items[i] if i < len(items) else "":
                f = _font(56)
                d.text((330, y + 16), items[i].upper()[:18], font=f, fill=_mix(CREAM, a))
            else:
                d.line([(330, y + 45), (840, y + 45)], fill=_mix(GREY, a), width=10)
    elif motiv == "chart":
        x0, y0, x1, y1 = 180, 1450, 900, 850
        d.line([(x0, y1 - 20), (x0, y0), (x1, y0)], fill=_mix(GREY, a), width=6)
        p = _ease(_seg(t, 0, 0.8))
        pts = []
        for i in range(int(80 * p) + 1):
            u = i / 80
            v = 0.08 * u + (max(0, u - 0.62) / 0.38) ** 2 * 0.9
            pts.append((x0 + u * (x1 - x0), y0 - v * (y0 - y1)))
        if len(pts) > 1:
            d.line(pts, fill=_mix(GOLD, a), width=12, joint="curve")
            ex, ey = pts[-1]
            d.ellipse([ex - 14, ey - 14, ex + 14, ey + 14], fill=_mix(GOLD, a))
        if sw:
            _label(d, sw, 720, y1 - 60, 60, GOLD, a * _seg(t, 0.6, 0.8))
    elif motiv == "zwei_wege":
        _ground(d, G, a)
        d.line([(540, G), (540, G - 160)], fill=_mix(GREY, a), width=10)
        d.line([(540, G - 160), (300, G - 420)], fill=_mix(GREY, a), width=10)
        d.line([(540, G - 160), (780, G - 420)], fill=_mix(GOLD, a), width=10)
        parts = [s.strip() for s in (stichwort or "").split("|")]
        if len(parts) == 2:
            _label(d, parts[0].upper()[:10], 280, G - 480, 50, GREY, a)
            _label(d, parts[1].upper()[:10], 800, G - 480, 50, GOLD, a)
        _figure(d, 540, G + 10, 0.7, "denkt", t, a=a)
    elif motiv == "gluehbirne":
        _ground(d, G, a)
        head = _figure(d, 540, G, 1.1, "steht", t, a=a)
        on = _seg(t, 0.3, 0.45)
        bx, by = head[0], head[1] - 230
        if on > 0:
            for i in range(8):
                ang = i / 8 * 2 * math.pi
                d.line([(bx + math.cos(ang) * 95, by + math.sin(ang) * 95),
                        (bx + math.cos(ang) * 135, by + math.sin(ang) * 135)], fill=_mix(GOLD, a * on), width=8)
        d.ellipse([bx - 70, by - 80, bx + 70, by + 60], outline=_mix(GOLD if on else CREAM, a), width=10,
                  fill=_mix(GOLD, a * on * 0.35) if on else None)
        d.rectangle([bx - 30, by + 60, bx + 30, by + 95], outline=_mix(CREAM, a), width=8)
    else:  # "zahl" und Rückfall
        txt = sw or "!"
        digits = "".join(ch for ch in txt if ch.isdigit())
        if digits and len(digits) <= 6:
            val = int(round(int(digits) * _ease(_seg(t, 0, 0.6))))
            txt = txt.replace(digits, f"{val:,}".replace(",", "."), 1)
        size = 220 if len(txt) <= 5 else 150
        _label(d, txt, 540, 1150, size, GOLD, a)
        d.line([(300, 1300), (780, 1300)], fill=_mix(GOLD, a * 0.6), width=6)


# ---------- Text ----------

def _words(text):
    """'Das ist *wichtig*' → [(Wort, gold?)]."""
    out, inside = [], False
    for w in text.replace("\n", " ").split():
        gold = inside or "*" in w
        inside = (inside + w.count("*")) % 2 == 1
        out.append((w.replace("*", "").upper(), gold))
    return [(w, g) for w, g in out if w]


def _layout(words, size, max_w, draw):
    f = _font(size)
    lines, cur, cur_w = [], [], 0
    space = draw.textlength(" ", font=f)
    for w, g in words:
        ww = draw.textlength(w, font=f)
        if cur and cur_w + space + ww > max_w:
            lines.append(cur)
            cur, cur_w = [], 0
        cur.append((w, g, ww))
        cur_w += (space if cur_w else 0) + ww
    if cur:
        lines.append(cur)
    return lines, f, space


def _draw_text(img, d, text, lt, top=430, size=82, start=0.04, per_word=0.06):
    words = _words(text)
    if not words:
        return
    while size > 52:
        lines, f, space = _layout(words, size, 900, d)
        if len(lines) <= 4:
            break
        size -= 6
    lh = int(size * 1.18)
    per_word = min(per_word, 0.45 / max(1, len(words)))  # alle Wörter bis zur Szenenmitte sichtbar
    k = 0
    for li, line in enumerate(lines):
        total = sum(w[2] for w in line) + space * (len(line) - 1)
        x = (W - total) / 2
        y = top + li * lh
        for w, g, ww in line:
            q = _ease(_seg(lt, start + k * per_word, start + k * per_word + 0.12))
            k += 1
            if q > 0:
                col = GOLD if g else CREAM
                d.text((x, y + (1 - q) * 18), w, font=f, fill=_mix(col, q))
            x += ww + space


# ---------- Musik ----------

def _music(path, total, cuts, mood="ruhig"):
    import numpy as np
    sr = 44100
    n = int(total * sr)
    t = np.arange(n) / sr
    out = np.zeros(n)
    # Akkordfolge (Am – F – C – G), weiche Flächen
    chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (130.81, 196.0, 261.63), (196.0, 246.94, 293.66)]
    bar = 2.4 if mood == "ruhig" else 1.8
    for ci in range(int(total / bar) + 1):
        s, e = int(ci * bar * sr), min(n, int((ci + 1) * bar * sr) + int(0.3 * sr))
        if s >= n:
            break
        tt = np.arange(e - s) / sr
        env = np.minimum(1, tt / 0.4) * np.exp(-tt * 0.5)
        for f in chords[ci % 4]:
            out[s:e] += 0.05 * env * (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * 2 * f * tt))
        # Bass
        out[s:e] += 0.08 * env * np.sin(2 * np.pi * chords[ci % 4][0] / 2 * tt)
    # leiser Puls (Kick) auf jedem Viertel
    beat = bar / 4
    for bi in range(int(total / beat)):
        s = int(bi * beat * sr)
        tt = np.arange(int(0.25 * sr)) / sr
        f = 50 + 70 * np.exp(-tt * 30)
        seg = 0.18 * np.exp(-tt * 14) * np.sin(2 * np.pi * np.cumsum(f) / sr)
        out[s:s + len(seg)] += seg[: n - s]
    # Whoosh an jedem Szenenwechsel
    rng = np.random.default_rng(7)
    for c in cuts:
        s = int(max(0, c - 0.25) * sr)
        ln = int(0.5 * sr)
        nz = np.convolve(rng.standard_normal(ln), np.ones(40) / 40, "same")
        env = np.sin(np.linspace(0, np.pi, ln)) ** 2
        out[s:s + ln] += (0.35 * env * nz)[: max(0, n - s)]
    fade = np.minimum(1, t / 0.5) * np.minimum(1, (total - t) / 1.5)
    out *= fade
    out /= max(np.abs(out).max(), 1e-6) / 0.7
    st = np.stack([out, np.roll(out, 250)], 1)
    data = (st * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(data.tobytes())


# ---------- Zusammenbau ----------

def _scene_len(scene, first):
    n = len(scene.get("text", "").split())
    return max(3.0 if first else 3.2, min(6.0, 1.4 + n * 0.38))


def _base(vignette):
    img = Image.new("RGB", (W, H), BG)
    return Image.composite(img, Image.new("RGB", (W, H), (0, 0, 0)), vignette)


def _vignette():
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).ellipse([-300, -200, W + 300, H + 200], fill=255)
    return m.filter(ImageFilter.GaussianBlur(220))


def render(cfg, script, workdir):
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    vcfg = cfg.get("video", {})
    brand = (vcfg.get("marke") or {})
    scenes = [s for s in script["scenes"] if s.get("text")]
    hook = (script.get("hook_text") or "").strip()

    # Szene 0 = großer Hook-Titel über dem ersten Motiv
    lens = [_scene_len(s, i == 0) for i, s in enumerate(scenes)]
    outro = 2.2 if brand.get("abspann_titel") else 0
    total = sum(lens) + outro
    cuts, acc = [], 0.0
    for ln in lens:
        cuts.append(acc)
        acc += ln
    _music(workdir / "musik.wav", total, cuts + [acc], vcfg.get("musik_stimmung", "ruhig"))

    vig = _vignette()
    base = _base(vig)
    cmd = [_ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", "musik.wav", "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", "final.mp4"]
    proc = subprocess.Popen(cmd, cwd=workdir, stdin=subprocess.PIPE)
    frames = int(total * FPS)
    for fi in range(frames):
        now = fi / FPS
        img = base.copy()
        d = ImageDraw.Draw(img)
        if now < acc:
            si = max(i for i, c in enumerate(cuts) if c <= now)
            sc, ln = scenes[si], lens[si]
            lt = (now - cuts[si]) / ln
            fade = min(1.0, (now - cuts[si]) / 0.25, (cuts[si] + ln - now) / 0.2) if si < len(scenes) else 1
            fade = max(0.0, fade)
            _motif(d, sc.get("motiv", "zahl"), lt, sc.get("stichwort"), fade)
            if si == 0 and hook:
                _draw_text(img, d, hook if "*" in hook else f"*{hook}*", lt, top=300, size=96, start=0.0, per_word=0.05)
                # kleiner Text darunter erst nach dem Hook
                if lt > 0.35:
                    _draw_text(img, d, sc["text"], (lt - 0.35) / 0.65, top=640, size=58, start=0, per_word=0.05)
            else:
                _draw_text(img, d, sc["text"], lt, top=380)
        else:  # Abspann
            q = _ease((now - acc) / 0.5)
            _label(d, brand.get("abspann_titel", ""), 540, 860, 84, GOLD, q)
            if brand.get("abspann_text"):
                _label(d, brand["abspann_text"], 540, 980, 54, CREAM, q)
        if brand.get("text"):
            _label(d, brand["text"], 540, 190, 36, GOLD, 0.7)
        if script.get("serie"):
            _label(d, script["serie"].upper(), 540, 245, 32, CREAM, 0.6)
        proc.stdin.write(img.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg-Fehler beim Strichmännchen-Video")
    # Titelbild (Hook-Szene, Mitte)
    try:
        subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-ss", f"{min(lens[0] * 0.9, 2.5):.2f}",
                        "-i", "final.mp4", "-frames:v", "1", "titelbild.jpg"], cwd=workdir, check=True)
    except Exception:
        pass
    return workdir / "final.mp4"

"""DF-Story-Video: dunkle Strichmännchen-Geschichte mit Leucht-Effekten, Untertitel Wort für Wort,
eigene Musik – keine Stimme, keine Stock-Videos. (Stil der Reels vom 9. November.)

Jede Szene im Skript (script["scenes"]) hat:
  text    – Untertitel unten, 1 kurzer Satz (max. 12 Wörter). *Wort* = gold, ~Wort~ = rot.
  visual  – eins der Bilder aus MOTIVE
  titel   – optional: großer Leucht-Titel (max. 4 Wörter), titel_farbe: gold | rot | weiss
  zahl, label, anteil, pose, links, rechts, regeln – je nach visual (siehe MOTIVE)
"""
import math
import re
import subprocess
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
FPS = 30
G = 1140                      # Boden-Linie (Füße der Figuren)

WHITE = (240, 242, 246)
GOLD = (246, 197, 68)
RED = (255, 84, 84)
GREY = (154, 160, 170)

MOTIVE = {
    "figur": "Figur in der Landschaft (pose: steht | laeuft | jubel | handy | denkt | frust | laptop), optional mit titel",
    "uhr": "große Uhr mit drehendem Zeiger über der Figur, optional titel darunter (z. B. „KEINE ZEIT.“)",
    "zahl": "große leuchtende Zahl zählt hoch (zahl = z. B. 365, label = z. B. STUNDEN IM JAHR)",
    "ring": "Fortschrittsring (zahl = z. B. 1h, label = z. B. VON 24, anteil = z. B. 0.04)",
    "stapel": "Figur neben wachsendem Kurs-/Bücherstapel (label = z. B. 5 KURSE)",
    "treppe": "Figur steigt eine leuchtende Treppe hoch (label optional)",
    "vergleich": "zwei Figuren: links grau (links = Wort), rechts gold leuchtend (rechts = Wort)",
    "frage": "Figur mit leuchtenden Fragezeichen über dem Kopf",
    "regeln": "Mehrwert-Karte: titel (z. B. 20/80-REGEL) + regeln = 3 Zeilen [kurz, Stichwort, Erklärung max. 8 Wörter]",
    "ende": "Schlusskarte mit Aufforderung (titel = z. B. Speicher dir die 20/80-Regel)",
}

# ---------- Schriften ----------

_CACHE = Path.home() / ".cache" / "df-fonts"
_FONT_DIRS = [Path(__file__).resolve().parent.parent / "assets" / "fonts", _CACHE, Path("/usr/share/fonts/opentype/inter")]
_FALLBACK = ["/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
_INTER_ZIP = "https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip"
_WEIGHTS = ("Medium", "SemiBold", "Bold", "ExtraBold")
_fonts = {}
_checked = False


def _ensure_fonts():
    """Schrift Inter (wie in den Original-Reels) bei Bedarf einmal von GitHub laden."""
    global _checked
    if _checked:
        return
    _checked = True
    if any((d / f"Inter-Bold{e}").exists() for d in _FONT_DIRS for e in (".ttf", ".otf")):
        return
    try:
        import io
        import zipfile

        import requests
        r = requests.get(_INTER_ZIP, timeout=90)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
        _CACHE.mkdir(parents=True, exist_ok=True)
        names = z.namelist()
        for wgt in _WEIGHTS:
            for ext in (".ttf", ".otf"):
                hit = [n for n in names if n.endswith(f"/Inter-{wgt}{ext}") or n == f"Inter-{wgt}{ext}"]
                if hit:
                    (_CACHE / f"Inter-{wgt}{ext}").write_bytes(z.read(sorted(hit, key=len)[0]))
                    break
        print("Schrift Inter geladen:", sorted(p.name for p in _CACHE.iterdir()))
    except Exception as e:  # ohne Internet: Ersatzschrift
        print("Schrift Inter nicht ladbar, nutze Ersatzschrift:", e)


def _font(size, weight="Bold"):
    _ensure_fonts()
    key = (size, weight)
    if key not in _fonts:
        cands = [d / f"Inter-{weight}{ext}" for d in _FONT_DIRS for ext in (".ttf", ".otf")] + \
                [d / f"Inter-Bold{ext}" for d in _FONT_DIRS for ext in (".ttf", ".otf")] + [Path(p) for p in _FALLBACK]
        for p in cands:
            if p.exists():
                _fonts[key] = ImageFont.truetype(str(p), size)
                break
        else:
            _fonts[key] = ImageFont.load_default(size)
    return _fonts[key]


def _ffmpeg():
    """ffmpeg vom System – oder aus pip (imageio-ffmpeg), falls apt bei GitHub ausfällt."""
    import shutil
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


# ---------- Hilfen ----------

def _cl(x):
    return max(0.0, min(1.0, x))


def _seg(t, a, b):
    return _cl((t - a) / (b - a)) if b > a else 1.0


def _ease(x):
    x = _cl(x)
    return x * x * (3 - 2 * x)


def _eo(x):
    x = _cl(x)
    return 1 - (1 - x) ** 3


def _lerp(a, b, t):
    return a + (b - a) * t


def _rgba(c, a=1.0):
    return (int(c[0]), int(c[1]), int(c[2]), int(255 * _cl(a)))


class Frame:
    """Zwei Ebenen: scharf (sharp) und Leuchten (glow) – das Leuchten wird weichgezeichnet."""

    def __init__(self, base):
        self.base = base
        self.sharp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        self.glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.sharp)
        self.g = ImageDraw.Draw(self.glow)
        self.has_glow = False

    def line(self, pts, col, width, a=1.0, glow=False):
        self.d.line(pts, fill=_rgba(col, a), width=int(width), joint="curve")
        if glow:
            self.g.line(pts, fill=_rgba(col, a), width=int(width * 3))
            self.has_glow = True

    def ellipse(self, box, outline=None, fill=None, width=1, a=1.0, glow=False):
        self.d.ellipse(box, outline=_rgba(outline, a) if outline else None,
                       fill=_rgba(fill, a) if fill else None, width=int(width))
        if glow:
            self.g.ellipse(box, outline=_rgba(outline, a) if outline else None,
                           fill=_rgba(fill, a) if fill else None, width=int(width * 3))
            self.has_glow = True

    def rect(self, box, outline=None, fill=None, width=1, a=1.0, glow=False, radius=0):
        self.d.rounded_rectangle(box, radius=radius, outline=_rgba(outline, a) if outline else None,
                                 fill=_rgba(fill, a) if fill else None, width=int(width))
        if glow:
            self.g.rounded_rectangle(box, radius=radius, outline=_rgba(outline, a) if outline else None,
                                     fill=_rgba(fill, a) if fill else None, width=int(width * 3))
            self.has_glow = True

    def text(self, s, x, y, size, col, weight="Bold", align="center", a=1.0, glow=False, spacing=0):
        if a <= 0 or not s:
            return
        f = _font(size, weight)
        if spacing:
            w = sum(self.d.textlength(ch, font=f) for ch in s) + spacing * (len(s) - 1)
        else:
            w = self.d.textlength(s, font=f)
        x0 = x - w / 2 if align == "center" else x
        y0 = y - size * 0.8
        targets = [self.d] + ([self.g] if glow else [])
        for dr in targets:
            if spacing:
                cx = x0
                for ch in s:
                    dr.text((cx, y0), ch, font=f, fill=_rgba(col, a))
                    cx += dr.textlength(ch, font=f) + spacing
            else:
                dr.text((x0, y0), s, font=f, fill=_rgba(col, a))
        if glow:
            self.has_glow = True

    def compose(self, fade=0.0):
        img = self.base.copy()
        if self.has_glow:
            small = self.glow.resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(7))
            halo = small.resize((W, H), Image.BILINEAR)
            img.alpha_composite(halo)
            img.alpha_composite(halo)
        img.alpha_composite(self.sharp)
        out = img.convert("RGB")
        if fade > 0:
            out = Image.blend(out, Image.new("RGB", (W, H), (0, 0, 0)), _cl(fade))
        return out


# ---------- Hintergründe (einmal berechnet, dann wiederverwendet) ----------

_bg_cache = {}


def _background(kind="scene", gold=0.0):
    key = (kind, round(gold, 2))
    if key in _bg_cache:
        return _bg_cache[key]
    import numpy as np
    y = np.linspace(0, 1, H)[:, None]
    x = np.linspace(0, 1, W)[None, :]
    top, bot = np.array([24, 27, 35]), np.array([9, 10, 14])
    img = top[None, None, :] * (1 - y[..., None]) + bot[None, None, :] * y[..., None]
    img = np.broadcast_to(img, (H, W, 3)).copy()
    if gold > 0:  # warmes Leuchten in der Mitte
        dx, dy = (x - 0.5) * W, (y - 0.38) * H
        r = np.sqrt(dx ** 2 + dy ** 2) / 900
        warm = np.clip(1 - r, 0, 1) ** 2 * gold
        img += warm[..., None] * np.array([95, 62, 14])[None, None, :]
    vx, vy = (x - 0.5) * 2, (y - 0.5) * 2
    vig = np.clip(1 - 0.35 * (vx ** 2 + vy ** 2), 0.45, 1)
    img *= vig[..., None]
    im = Image.fromarray(np.clip(img, 0, 255).astype("uint8"), "RGB").convert("RGBA")
    if kind == "scene":
        d = ImageDraw.Draw(im)
        far = [(0, 1000), (120, 930), (230, 975), (360, 880), (470, 950), (600, 860), (720, 940),
               (850, 890), (960, 960), (1080, 910), (1080, G), (0, G)]
        near = [(0, 1060), (150, 1000), (300, 1050), (420, 990), (560, 1060), (700, 1010), (840, 1070),
                (980, 1015), (1080, 1050), (1080, G), (0, G)]
        d.polygon(far, fill=(31, 35, 45, 255))
        d.polygon(near, fill=(25, 28, 37, 255))
        gy = np.linspace(0, 1, H - G)[:, None, None]
        ground = np.array([16, 18, 25]) * (1 - gy) + np.array([5, 6, 9]) * gy
        ground = np.broadcast_to(ground, (H - G, W, 3)).astype("uint8")
        im.paste(Image.fromarray(ground, "RGB").convert("RGBA"), (0, G))
        d.line([(0, G), (W, G)], fill=(70, 78, 96, 255), width=3)
    _bg_cache[key] = im
    return im


# ---------- Strichmännchen ----------

def _fig(fr, x, y, s=1.0, pose="steht", t=0.0, col=WHITE, a=1.0, glow=True, amt=1.0):
    lw = 8 * s
    hr = 19 * s
    hip = (x, y - 92 * s)
    neck = (x, y - 172 * s)
    head = (x, neck[1] - hr - 5 * s)
    if pose == "frust":
        neck = (x + 10 * s, y - 165 * s)
        head = (x + 30 * s, neck[1] - hr * 0.4)

    def L(pts):
        fr.line(pts, col, lw, a, glow)

    L([hip, neck])
    fr.ellipse([head[0] - hr, head[1] - hr, head[0] + hr, head[1] + hr], outline=col, width=lw, a=a, glow=glow)
    if pose == "laeuft":
        ph = math.sin(t * 12) * 34 * s
        L([hip, (x + ph, y)])
        L([hip, (x - ph, y)])
    elif pose == "laptop":
        knee = (x + 48 * s, y - 92 * s)
        L([hip, knee])
        L([knee, (x + 48 * s, y)])
    else:
        L([hip, (x - 26 * s, y)])
        L([hip, (x + 26 * s, y)])
    sh = (neck[0], neck[1] + 14 * s)
    if pose == "jubel":
        up = amt * (1 + 0.15 * math.sin(t * 8))
        L([sh, (x - 55 * s, sh[1] + _lerp(70, -75, up) * s)])
        L([sh, (x + 55 * s, sh[1] + _lerp(70, -75, up) * s)])
    elif pose == "denkt":
        L([sh, (x + 38 * s, sh[1] + 30 * s), (head[0] + 12 * s, head[1] + hr)])
        L([sh, (x - 34 * s, sh[1] + 68 * s)])
    elif pose == "handy":
        L([sh, (x + 32 * s, sh[1] + 18 * s), (x + 36 * s, head[1] + 12 * s)])
        L([sh, (x - 34 * s, sh[1] + 68 * s)])
        fr.rect([x + 26 * s, head[1] - 10 * s, x + 50 * s, head[1] + 30 * s], outline=GOLD, width=4 * s,
                a=a, glow=True, radius=int(5 * s))
    elif pose == "laptop":
        tap = math.sin(t * 25) * 5 * s
        L([sh, (x + 70 * s, sh[1] + 40 * s + tap)])
        L([sh, (x + 64 * s, sh[1] + 46 * s - tap)])
    elif pose == "frust":
        L([sh, (x + 2 * s, sh[1] + 85 * s)])
        L([sh, (x + 22 * s, sh[1] + 85 * s)])
    else:
        sw = math.sin(t * 2) * 4 * s
        L([sh, (x - 36 * s, sh[1] + 70 * s + sw)])
        L([sh, (x + 36 * s, sh[1] + 70 * s - sw)])
    return head


def _laptop(fr, x, a=1.0):
    fr.line([(x - 20, G - 140), (x + 160, G - 140)], WHITE, 6, a)
    fr.line([(x + 140, G - 140), (x + 140, G)], WHITE, 6, a)
    fr.line([(x + 10, G - 144), (x + 100, G - 144), (x + 115, G - 230), (x + 30, G - 230), (x + 10, G - 144)],
            GOLD, 6, a, glow=True)


# ---------- Bild-Elemente ----------

def _clock(fr, cx, cy, r, t, a=1.0, col=WHITE):
    fr.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=10, a=a, glow=True)
    for i in range(12):
        an = i / 12 * 2 * math.pi
        fr.line([(cx + math.cos(an) * (r - 28), cy + math.sin(an) * (r - 28)),
                 (cx + math.cos(an) * (r - 12), cy + math.sin(an) * (r - 12))], col, 5, a)
    an = t * 2.4 - math.pi / 2
    fr.line([(cx, cy), (cx + math.cos(an) * r * 0.75, cy + math.sin(an) * r * 0.75)], col, 8, a, glow=True)
    fr.line([(cx, cy), (cx, cy - r * 0.5)], col, 10, a)
    fr.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill=col, a=a)


def _num_text(z, p):
    """'365' zählt hoch, '2,5 STD' bleibt Text."""
    m = re.match(r"^(\d[\d.]*)(.*)$", z.strip())
    if not m or "," in z:
        return z
    digits = m.group(1).replace(".", "")
    if not digits.isdigit() or len(digits) > 7:
        return z
    v = int(round(int(digits) * p))
    return f"{v:,}".replace(",", ".") + m.group(2)


def _wrap(s, n):
    out, cur = [], ""
    for w in str(s).split():
        if cur and len(cur) + 1 + len(w) > n:
            out.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        out.append(cur)
    return out


def _titel(fr, sc, lt, y=560, size=96):
    t = (sc.get("titel") or "").strip()
    if not t:
        return
    col = {"rot": RED, "weiss": WHITE}.get((sc.get("titel_farbe") or "gold").lower(), GOLD)
    lines = _wrap(t.upper(), 14)[:3]
    sz = size if max(len(l) for l in lines) <= 12 else int(size * 0.82)
    for i, ln in enumerate(lines):
        a = _ease(_seg(lt, 0.15 + i * 0.25, 0.5 + i * 0.25))
        fr.text(ln, 540, y + i * sz * 1.08, sz, col, "ExtraBold", a=a, glow=col != WHITE)


def _visual(fr, sc, lt, d):
    v = sc.get("visual", "figur")
    label = (sc.get("label") or "").upper()
    if v == "uhr":
        _fig(fr, 470, G, 1, "steht", lt)
        _clock(fr, 540, 470, 150, lt, _ease(_seg(lt, 0, 0.3)))
        _titel(fr, sc, lt, y=760)
    elif v == "zahl":
        z = str(sc.get("zahl") or "")
        p = _eo(_seg(lt, 0.2, min(2.2, d * 0.5)))
        fr.text(_num_text(z, p), 540, 640, 210 if len(z) <= 4 else 150, GOLD, "ExtraBold",
                a=_ease(_seg(lt, 0, 0.3)), glow=True)
        fr.text(label, 540, 730, 36, WHITE, "SemiBold", a=_ease(_seg(lt, 0.3, 0.6)), spacing=6)
        if sc.get("titel"):
            fr.text(sc["titel"], 540, 830, 44, WHITE, "SemiBold", a=_ease(_seg(lt, 1.2, 1.6)))
    elif v == "ring":
        cx, cy, r = 540, 560, 175
        fr.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(70, 74, 86), width=22)
        try:
            frac = float(sc.get("anteil") or 0.1)
        except (TypeError, ValueError):
            frac = 0.1
        end = -90 + 360 * _cl(frac) * _eo(_seg(lt, 0.3, 1.4))
        if end > -89:
            fr.d.arc([cx - r, cy - r, cx + r, cy + r], -90, end, fill=_rgba(GOLD), width=22)
            fr.g.arc([cx - r, cy - r, cx + r, cy + r], -90, end, fill=_rgba(GOLD), width=50)
            fr.has_glow = True
        fr.text(str(sc.get("zahl") or ""), cx, cy + 30, 120, GOLD, "ExtraBold", a=_ease(_seg(lt, 0.2, 0.5)), glow=True)
        fr.text(label, cx, cy + 90, 32, GREY, "SemiBold", a=_ease(_seg(lt, 0.4, 0.7)), spacing=6)
    elif v == "stapel":
        _fig(fr, 330, G, 1, "denkt", lt)
        n = 1 + int(6 * _eo(_seg(lt, 0.2, 2.0)))
        cols = [(120, 90, 180), (80, 140, 200), (200, 110, 90), (90, 170, 130), (190, 160, 80), (150, 150, 160)]
        for i in range(n):
            off = (i % 2) * 14 - 7
            fr.rect([600 + off, G - (i + 1) * 46, 820 + off, G - i * 46 - 4], fill=cols[i % 6], a=0.75, radius=6)
        if label:
            fr.text(label, 710, G - n * 46 - 60, 52, RED, "ExtraBold", a=_ease(_seg(lt, 1.0, 1.4)), glow=True)
        _titel(fr, sc, lt, y=520)
    elif v == "treppe":
        steps = 7
        shown = steps * _eo(_seg(lt, 0.2, d * 0.7))
        for i in range(steps):
            q = _cl(shown - i)
            if q <= 0:
                continue
            x0 = 200 + i * 95
            fr.rect([x0, G - (i + 1) * 70, x0 + 88, G], outline=GOLD, width=5, a=q, glow=True, radius=4)
        k = min(steps - 1, int(shown))
        _fig(fr, 244 + k * 95, G - (k + 1) * 70, 0.85, "jubel" if shown >= steps - 0.1 else "steht", lt,
             amt=_ease(_seg(lt, d * 0.7, d * 0.8)))
        if label:
            fr.text(label, 540, 520, 64, GOLD, "ExtraBold", a=_ease(_seg(lt, 0.3, 0.7)), glow=True)
        _titel(fr, sc, lt, y=520)
    elif v == "vergleich":
        a = _ease(_seg(lt, 0, 0.4))
        fr.line([(540, 420), (540, G + 40)], WHITE, 3, a * 0.15)
        _fig(fr, 270, G, 1, "frust", lt, col=(154, 156, 163), a=a, glow=False)
        g = _ease(_seg(lt, 0.6, 1.4))
        _fig(fr, 810, G, 1, "jubel", lt, col=(255, 230, 170), a=a, amt=g)
        fr.text((sc.get("links") or "").upper(), 270, 560, 54, GREY, "ExtraBold", a=a, spacing=3)
        fr.text((sc.get("rechts") or "").upper(), 810, 560, 54, GOLD, "ExtraBold", a=_ease(_seg(lt, 0.6, 1.0)),
                glow=True, spacing=3)
        if sc.get("titel"):
            fr.text(sc["titel"].upper(), 540, 300, 40, GREY, "ExtraBold", a=a, spacing=6)
    elif v == "frage":
        head = _fig(fr, 540, G, 1.1, "denkt", lt)
        for i, dx in enumerate((-90, 0, 90)):
            q = _ease(_seg(lt, 0.3 + i * 0.35, 0.6 + i * 0.35))
            fr.text("?", head[0] + dx, head[1] - 110 - 30 * q + math.sin(lt * 3 + i) * 8, 80, GOLD, "ExtraBold",
                    a=q, glow=True)
        _titel(fr, sc, lt, y=520)
    elif v == "regeln":
        a = _ease(_seg(lt, 0, 0.4))
        fr.text("DIE", 540, 330, 40, GREY, "ExtraBold", a=a, spacing=8)
        title = (sc.get("titel") or "METHODE").upper()
        fr.text(title, 540, 440, 92 if len(title) <= 14 else 70, GOLD, "ExtraBold", a=a, glow=True)
        rows = sc.get("regeln") or []
        for i, row in enumerate(rows[:3]):
            row = (list(row) + ["", "", ""])[:3]
            q = _ease(_seg(lt, 0.9 + i * 1.3, 1.4 + i * 1.3))
            y = 600 + i * 230
            fr.rect([110, y, 970, y + 190], fill=(255, 255, 255), a=0.05 * q, radius=26)
            fr.rect([110, y, 970, y + 190], outline=GOLD, width=2, a=0.35 * q, radius=26)
            fr.text(str(row[0]).upper()[:6], 210, y + 115, 50, GOLD, "ExtraBold", a=q, glow=True)
            fr.text(str(row[1])[:22], 320, y + 82, 46, WHITE, "Bold", align="left", a=q)
            for k, ln in enumerate(_wrap(str(row[2]), 34)[:2]):
                fr.text(ln, 320, y + 132 + k * 38, 32, GREY, "Medium", align="left", a=q)
    elif v == "ende":
        a = _ease(_seg(lt, 0, 0.5))
        fr.ellipse([440, 420, 640, 620], outline=GOLD, width=6, a=a, glow=True)
        fr.text("DF", 540, 555, 90, GOLD, "ExtraBold", a=a, glow=True)
        for k, ln in enumerate(_wrap(sc.get("titel") or "Folge für mehr", 22)[:3]):
            fr.text(ln, 540, 780 + k * 72, 62, WHITE, "ExtraBold", a=_ease(_seg(lt, 0.4 + k * 0.2, 0.8 + k * 0.2)))
        fr.text("@df_digitalefreiheit", 540, 1040, 38, GREY, "Medium", a=_ease(_seg(lt, 1.0, 1.4)))
    else:  # "figur"
        pose = sc.get("pose") or "steht"
        if pose == "laufen":
            pose = "laeuft"
        x = _lerp(260, 640, _eo(_seg(lt, 0, d * 0.8))) if pose == "laeuft" else 540
        if pose == "laptop":
            _laptop(fr, 600)
            x = 480
        _fig(fr, x, G, 1.1, pose, lt, amt=_ease(_seg(lt, 0.4, 1.0)))
        if label:
            fr.text(label, 760, G - 300, 50, RED if pose in ("handy", "frust") else GOLD, "ExtraBold",
                    a=_ease(_seg(lt, 0.6, 1.0)), glow=True)
        _titel(fr, sc, lt, y=560)


# ---------- Untertitel ----------

def _words(text):
    """'Er hat *sofort* angefangen, ~nie~ aufgehört' → [(Wort, Farbe|None)]."""
    out, mode = [], None
    for w in text.replace("\n", " ").split():
        col = mode
        opened = GOLD if w.count("*") % 2 == 1 else (RED if w.count("~") % 2 == 1 else None)
        if "*" in w and w.count("*") % 2 == 0:
            col = GOLD
        if "~" in w and w.count("~") % 2 == 0:
            col = RED
        if opened:
            if mode:
                mode = None
            else:
                mode = opened
                col = opened
        clean = w.replace("*", "").replace("~", "")
        if clean:
            out.append((clean, col))
    return out


def _caption(fr, text, lt, t0, t1, y=1330, size=58):
    words = _words(text)
    if not words:
        return
    f = _font(size, "Bold")
    for _ in range(4):
        sp = fr.d.textlength(" ", font=f)
        lines, lw = [[]], 0
        for w, c in words:
            ww = fr.d.textlength(w, font=f)
            if lines[-1] and lw + ww > 900:
                lines.append([])
                lw = 0
            lines[-1].append((w, c, ww))
            lw += ww + sp
        if len(lines) <= 3:
            break
        size -= 6
        f = _font(size, "Bold")
    n, k = len(words), 0
    for li, ln in enumerate(lines):
        tot = sum(x[2] for x in ln) + sp * (len(ln) - 1)
        x = 540 - tot / 2
        for w, c, ww in ln:
            tw = _lerp(t0, t1, k / n)
            on = _seg(lt, tw, tw + 0.12)
            col = c if (c and on > 0.5) else WHITE
            a = _lerp(0.25, 1, on)
            yy = y + li * size * 1.25 + (1 - _ease(on)) * 6 - size * 0.8
            fr.d.text((x, yy), w, font=f, fill=_rgba(col, a))
            if c and on > 0.5:
                fr.g.text((x, yy), w, font=f, fill=_rgba(col, 0.9))
                fr.has_glow = True
            x += ww + sp
            k += 1


def _watermark(fr):
    fr.text("DIGITALE FREIHEIT", 540, 1560, 26, (200, 200, 205), "SemiBold", a=0.35, spacing=7)


# ---------- Skript vorbereiten ----------

def _split_long(scenes, max_words=12):
    """Zu lange Untertitel automatisch auf zwei Szenen verteilen."""
    out = []
    for sc in scenes:
        words = (sc.get("text") or "").split()
        if len(words) <= max_words or sc.get("visual") in ("regeln", "ende"):
            out.append(sc)
            continue
        cut = len(words) // 2
        for i in range(len(words) // 2, len(words) - 2):
            if words[i - 1][-1:] in ".,:!?–":
                cut = i
                break
        first = dict(sc, text=" ".join(words[:cut]))
        second = dict(sc, text=" ".join(words[cut:]))
        out += _split_long([first], max_words) + _split_long([second], max_words)
    return out


def _duration(sc):
    v = sc.get("visual")
    if v == "regeln":
        return 6.8
    if v == "ende":
        return 3.4
    n = len((sc.get("text") or "").split())
    return max(3.0, min(6.0, 1.6 + n * 0.3))


# ---------- Musik ----------

def _music(path, total, cuts, mood="ruhig"):
    import numpy as np
    sr = 44100
    n = int(total * sr)
    t = np.arange(n) / sr
    out = np.zeros(n)
    chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (130.81, 196.0, 261.63), (196.0, 246.94, 293.66)]
    bar = 2.6 if mood == "ruhig" else 1.9
    for ci in range(int(total / bar) + 1):
        s, e = int(ci * bar * sr), min(n, int((ci + 1) * bar * sr) + int(0.4 * sr))
        if s >= n:
            break
        tt = np.arange(e - s) / sr
        env = np.minimum(1, tt / 0.6) * np.exp(-tt * 0.4)
        for f in chords[ci % 4]:
            out[s:e] += 0.045 * env * (np.sin(2 * np.pi * f * tt) + 0.25 * np.sin(2 * np.pi * 2.003 * f * tt))
        out[s:e] += 0.07 * env * np.sin(2 * np.pi * chords[ci % 4][0] / 2 * tt)
        for k, f in enumerate(chords[ci % 4]):  # leises Glöckchen
            s2 = s + int(k * bar / 3 * sr)
            if s2 < n:
                tt2 = np.arange(min(int(0.8 * sr), n - s2)) / sr
                out[s2:s2 + len(tt2)] += 0.03 * np.exp(-tt2 * 5) * np.sin(2 * np.pi * f * 4 * tt2)
    rng = np.random.default_rng(7)
    for c in cuts:  # weicher Whoosh bei jedem Szenenwechsel
        s = int(max(0, c - 0.3) * sr)
        ln = int(0.6 * sr)
        nz = np.convolve(rng.standard_normal(ln), np.ones(60) / 60, "same")
        env = np.sin(np.linspace(0, np.pi, ln)) ** 2
        out[s:s + ln] += (0.3 * env * nz)[: max(0, n - s)]
    tt = np.arange(min(int(2.0 * sr), n)) / sr  # tiefer Boom am Anfang
    out[: len(tt)] += 0.45 * np.exp(-tt * 2.2) * np.sin(2 * np.pi * np.cumsum(35 + 50 * np.exp(-tt * 1.5)) / sr)
    fade = np.minimum(1, t / 0.3) * np.minimum(1, (total - t) / 1.5)
    out *= fade
    out /= max(np.abs(out).max(), 1e-6) / 0.75
    st = np.stack([out, np.roll(out, 300)], 1)
    data = (st * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(data.tobytes())


# ---------- Zusammenbau ----------

_SCENE_BG = {"figur": ("scene", 0), "uhr": ("scene", 0), "stapel": ("scene", 0), "frage": ("scene", 0),
             "treppe": ("scene", 0.5), "vergleich": ("plain", 0.3), "zahl": ("plain", 0.7), "ring": ("plain", 0.6),
             "regeln": ("plain", 0.45), "ende": ("plain", 0.9)}


def render(cfg, script, workdir):
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    vcfg = cfg.get("video", {})
    scenes = _split_long([s for s in script["scenes"] if s.get("text") or s.get("visual") in ("regeln", "ende")])
    if scenes and scenes[-1].get("visual") != "ende":
        scenes.append({"visual": "ende", "titel": script.get("abspann") or (vcfg.get("marke") or {}).get(
            "abspann_text", "Folge für mehr")})
    lens = [_duration(s) for s in scenes]
    total = sum(lens)
    cuts, acc = [], 0.0
    for ln in lens:
        cuts.append(acc)
        acc += ln
    _music(workdir / "musik.wav", total, cuts[1:], vcfg.get("musik_stimmung", "ruhig"))

    cmd = [_ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", "musik.wav", "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", "final.mp4"]
    proc = subprocess.Popen(cmd, cwd=workdir, stdin=subprocess.PIPE)
    cover = None
    for fi in range(int(total * FPS)):
        now = fi / FPS
        si = max(i for i, c in enumerate(cuts) if c <= now)
        sc, d = scenes[si], lens[si]
        lt = now - cuts[si]
        kind, gold = _SCENE_BG.get(sc.get("visual"), ("scene", 0))
        fr = Frame(_background(kind, gold))
        _visual(fr, sc, lt, d)
        if sc.get("visual") not in ("regeln", "ende"):
            n = len((sc.get("text") or "").split())
            _caption(fr, sc.get("text") or "", lt, 0.2, min(d - 1.0, 0.2 + n * 0.26))
        if sc.get("visual") != "ende":
            _watermark(fr)
        fin = 0.1 if si == 0 else 0.25
        fout = 0.5 if si == len(scenes) - 1 else 0.25
        img = fr.compose(max(1 - lt / fin, 1 - (d - lt) / fout, 0))
        if si == 0 and cover is None and lt >= min(2.2, d - 0.4):
            cover = img
        proc.stdin.write(img.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg-Fehler beim Story-Video")
    if cover is not None:
        cover.save(workdir / "titelbild.jpg", quality=92)
    return workdir / "final.mp4"

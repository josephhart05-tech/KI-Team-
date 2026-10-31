"""Karussell-Agent: macht aus den Folien-Texten fertige Bilder (1080x1350) im Marken-Look."""
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
MARGIN = 96
FONT_DIRS = ["/usr/share/fonts/truetype/liberation", "/usr/share/fonts/truetype/dejavu", "C:/Windows/Fonts"]
FONT_FILES = {
    "bold": ["LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf", "arialbd.ttf"],
    "regular": ["LiberationSans-Regular.ttf", "DejaVuSans.ttf", "arial.ttf"],
}


def _font(kind, size):
    for d in FONT_DIRS:
        for name in FONT_FILES[kind]:
            path = Path(d) / name
            if path.exists():
                return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍←-⇿⬀-⯿]")
_STEP_PREFIX = re.compile(r"^\s*(schritt|tipp|punkt|step|fehler|grund)\s*\d+\s*[:.\-–]\s*", re.IGNORECASE)


def _clean(text, strip_step=False):
    """Emojis kann die Schrift nicht darstellen (würden als □ erscheinen) – also raus."""
    text = _EMOJI.sub("", text or "")
    if strip_step:
        text = _STEP_PREFIX.sub("", text)
    return " ".join(text.split())


def _hex(color):
    h = color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _wrap(draw, text, font, max_width):
    lines, line = [], ""
    for word in text.split():
        test = f"{line} {word}".strip()
        if draw.textlength(test, font=font) <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _fit(draw, text, kind, start_size, min_size, max_width, max_lines):
    """Größte Schrift, bei der der Text in max_lines Zeilen passt."""
    size = start_size
    while size > min_size:
        font = _font(kind, size)
        lines = _wrap(draw, text, font, max_width)
        if len(lines) <= max_lines:
            return font, lines
        size -= 4
    font = _font(kind, min_size)
    return font, _wrap(draw, text, font, max_width)


def _draw_lines(draw, lines, font, y, color, line_gap=1.25):
    for line in lines:
        draw.text((MARGIN, y), line, font=font, fill=color)
        y += int(font.size * line_gap)
    return y


def render(cfg, script, workdir):
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    gold = _hex(cfg["video"].get("marke", {}).get("farbe", "#D4AF37"))
    white, grey, black = (245, 245, 245), (150, 150, 150), (11, 11, 11)
    brand_text = cfg["video"].get("marke", {}).get("text", "")
    slides = script["slides"]
    paths = []

    for i, slide in enumerate(slides):
        img = Image.new("RGB", (W, H), black)
        d = ImageDraw.Draw(img)
        # dünner Goldrahmen + Akzentlinie
        d.rectangle([28, 28, W - 29, H - 29], outline=gold, width=3)
        max_w = W - 2 * MARGIN

        first, last = i == 0, i == len(slides) - 1
        title = _clean(slide.get("titel", ""), strip_step=not first).upper()
        title_font, title_lines = _fit(d, title, "bold", 112 if first else 78, 48, max_w, 4 if first else 3)
        body_font, body_lines = _fit(d, _clean(slide.get("text", "")), "regular", 50 if first else 46, 32, max_w, 7)

        title_h = len(title_lines) * int(title_font.size * 1.15)
        body_h = len(body_lines) * int(body_font.size * 1.35)
        # Inhalt vertikal mittig, aber nie über Abzeichen und Nummer
        number_h = 0 if first else 110
        y = max(230 if not first else 140, (H - number_h - title_h - 70 - body_h) // 2 + number_h)
        if not first:
            d.text((MARGIN, y - number_h), f"{i:02d}", font=_font("bold", 64), fill=gold)

        # Serien-Abzeichen oben links (z. B. "DF-TIPP #12"): schwarz auf Gold
        if script.get("serie"):
            badge_font = _font("bold", 30)
            badge = script["serie"].upper()
            bw = d.textlength(badge, font=badge_font)
            d.rectangle([MARGIN - 14, 62, MARGIN + bw + 14, 108], fill=gold)
            d.text((MARGIN, 68), badge, font=badge_font, fill=black)
        y = _draw_lines(d, title_lines, title_font, y, gold, 1.15)
        d.line([MARGIN, y + 20, MARGIN + 140, y + 20], fill=gold, width=5)
        _draw_lines(d, body_lines, body_font, y + 60, white, 1.35)

        # Fußzeile: Marke links, Seitenzahl / Wisch-Hinweis rechts
        foot = _font("bold", 30)
        d.text((MARGIN, H - 110), brand_text, font=foot, fill=gold)
        hint = f"{i + 1}/{len(slides)}" if last else f"{i + 1}/{len(slides)}  WISCHEN ›"
        d.text((W - MARGIN - d.textlength(hint, font=foot), H - 110), hint, font=foot, fill=grey)

        path = workdir / f"folie_{i + 1:02d}.png"
        img.save(path)
        paths.append(path)
    return paths

"""Konfiguration und Gedächtnis des Teams (JSON-Dateien im Ordner data/).

Profile: PROFIL=df (Standard, Digitale Freiheit) oder z. B. PROFIL=geschenkheld.
- config_<profil>.yaml ergänzt/überschreibt config.yaml
- posts.json ist gemeinsam (damit Freigaben in Telegram für alle Profile funktionieren),
  jeder Beitrag hat ein Feld "profil"
- state.json und learnings.md liegen pro Profil getrennt (data/<profil>/)
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PROFIL = (os.environ.get("PROFIL") or "df").strip().lower() or "df"
DATA = ROOT / "data"
PROFIL_DATA = DATA if PROFIL == "df" else DATA / PROFIL
OUTPUT = ROOT / "output"
POSTS_FILE = DATA / "posts.json"
STATE_FILE = PROFIL_DATA / "state.json"
LEARNINGS_FILE = PROFIL_DATA / "learnings.md"


def _merge(base, extra):
    out = dict(base)
    for k, v in (extra or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_config(profil=None):
    profil = (profil or PROFIL).lower()
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    extra = ROOT / f"config_{profil}.yaml"
    if profil != "df" and extra.exists():
        with open(extra, encoding="utf-8") as f:
            cfg = _merge(cfg, yaml.safe_load(f))
    cfg["profil"] = profil
    return cfg


def env(name, required=True):
    value = os.environ.get(name, "").strip()
    if required and not value:
        raise RuntimeError(f"Secret/Umgebungsvariable {name} fehlt (siehe ANLEITUNG.md)")
    return value


def now():
    return datetime.now(timezone.utc)


def now_iso():
    return now().isoformat(timespec="seconds")


def _load(path, default):
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def _save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_posts():
    return _load(POSTS_FILE, [])


def save_posts(posts):
    _save(POSTS_FILE, posts)


def profile_posts(posts, profil=None):
    """Nur die Beiträge eines Profils (alte Beiträge ohne Feld gehören zu Digitale Freiheit)."""
    profil = profil or PROFIL
    return [p for p in posts if p.get("profil", "df") == profil]


def load_state():
    return _load(STATE_FILE, {"telegram_offset": 0})


def save_state(state):
    _save(STATE_FILE, state)


def load_learnings():
    if LEARNINGS_FILE.exists():
        return LEARNINGS_FILE.read_text(encoding="utf-8")
    return "Noch keine Erkenntnisse – das Team sammelt gerade erste Daten."


def save_learnings(text):
    LEARNINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    LEARNINGS_FILE.write_text(text, encoding="utf-8")

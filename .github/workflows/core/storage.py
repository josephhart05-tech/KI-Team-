"""Konfiguration und Gedächtnis des Teams (JSON-Dateien im Ordner data/)."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUTPUT = ROOT / "output"
POSTS_FILE = DATA / "posts.json"
STATE_FILE = DATA / "state.json"
LEARNINGS_FILE = DATA / "learnings.md"


def load_config():
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


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
    DATA.mkdir(exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_posts():
    return _load(POSTS_FILE, [])


def save_posts(posts):
    _save(POSTS_FILE, posts)


def load_state():
    return _load(STATE_FILE, {"telegram_offset": 0})


def save_state(state):
    _save(STATE_FILE, state)


def load_learnings():
    if LEARNINGS_FILE.exists():
        return LEARNINGS_FILE.read_text(encoding="utf-8")
    return "Noch keine Erkenntnisse – das Team sammelt gerade erste Daten."


def save_learnings(text):
    DATA.mkdir(exist_ok=True)
    LEARNINGS_FILE.write_text(text, encoding="utf-8")

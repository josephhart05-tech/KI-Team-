"""Zugang zu kostenlosen Sprachmodellen: Gemini (Standard), Groq als Ersatz."""
import json
import os
import re
import time

import requests


class _NoKey(Exception):
    pass


_gemini_model_override = None


def _newest_gemini_flash(key):
    """Google schaltet alte Modelle ab – dann nehmen wir das neueste verfügbare Flash-Modell."""
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                     headers={"x-goog-api-key": key}, params={"pageSize": 200}, timeout=30)
    r.raise_for_status()
    candidates = []
    for m in r.json().get("models", []):
        name = m["name"].split("/")[-1]
        if "generateContent" not in m.get("supportedGenerationMethods", []):
            continue
        if "flash" not in name or any(x in name for x in ("image", "tts", "audio", "live", "embedding")):
            continue
        version = re.search(r"gemini-(\d+(?:\.\d+)?)", name)
        stable = not any(x in name for x in ("preview", "exp"))
        candidates.append((stable, float(version.group(1)) if version else 0, "lite" not in name, name))
    if not candidates:
        raise RuntimeError("Kein passendes Gemini-Modell gefunden")
    best = max(candidates)[3]
    print(f"Gemini-Modell automatisch gewählt: {best}")
    return best


def _gemini(prompt, model, json_mode):
    global _gemini_model_override
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise _NoKey()
    model = _gemini_model_override or model
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.9},
    }
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": key},
        json=body,
        timeout=120,
    )
    if r.status_code == 404 and not _gemini_model_override:
        _gemini_model_override = _newest_gemini_flash(key)
        return _gemini(prompt, model, json_mode)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _groq(prompt, model, json_mode):
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise _NoKey()
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.9,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json=body,
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def parse_json(text):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start : end + 1])


def ask(prompt, cfg, json_mode=False):
    providers = [
        (_gemini, cfg["llm"]["gemini_modell"]),
        (_groq, cfg["llm"]["groq_modell"]),
    ]
    last_error = None
    for fn, model in providers:
        for attempt in range(3):
            try:
                text = fn(prompt, model, json_mode)
                return parse_json(text) if json_mode else text.strip()
            except _NoKey:
                break
            except Exception as e:  # Rate-Limit, Netzwerk, kaputtes JSON → erneut versuchen
                last_error = e
                time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"Kein Sprachmodell erreichbar. Letzter Fehler: {last_error}")

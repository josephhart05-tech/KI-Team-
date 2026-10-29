"""Zugang zu kostenlosen Sprachmodellen: Gemini (Standard), Groq als Ersatz."""
import json
import os
import re
import time

import requests


class _NoKey(Exception):
    pass


# Gemini-Modelle in Reihenfolge der Bevorzugung. Wird bei Problemen um weitere Modelle ergänzt.
_gemini_models = None
_gemini_expanded = False
# 404 = abgeschaltet, 429 = Gratis-Limit erreicht, 5xx = überlastet → nächstes Modell probieren
_SWITCH_CODES = {404, 429, 500, 502, 503, 504}


def _gemini_flash_models(key):
    """Liste aller verfügbaren Flash-Modelle, beste zuerst (stabil vor Preview, neu vor alt)."""
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
    return [c[3] for c in sorted(candidates, reverse=True)][:6]


def _gemini(prompt, model, json_mode):
    global _gemini_models, _gemini_expanded
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise _NoKey()
    if _gemini_models is None:
        _gemini_models = [model]

    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.9},
    }
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"

    last = None
    i = 0
    while i < len(_gemini_models):
        name = _gemini_models[i]
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{name}:generateContent",
            headers={"x-goog-api-key": key},
            json=body,
            timeout=120,
        )
        if r.ok:
            if i > 0:  # funktionierendes Modell nach vorne, damit die nächsten Aufrufe es zuerst nehmen
                _gemini_models.insert(0, _gemini_models.pop(i))
                print(f"Gemini-Modell gewechselt zu: {name}")
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        if r.status_code not in _SWITCH_CODES:
            r.raise_for_status()
        last = f"{r.status_code} bei {name}"
        if not _gemini_expanded:
            _gemini_expanded = True
            _gemini_models += [m for m in _gemini_flash_models(key) if m not in _gemini_models]
        i += 1
    raise RuntimeError(f"Alle Gemini-Modelle gerade nicht verfügbar ({last})")


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
                print(f"Sprachmodell-Fehler (Versuch {attempt + 1}/3): {e}")
                time.sleep(15 * (attempt + 1))
    raise RuntimeError(f"Kein Sprachmodell erreichbar. Letzter Fehler: {last_error}")

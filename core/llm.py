"""Zugang zu kostenlosen Sprachmodellen: Gemini (Standard), Groq als Ersatz."""
import json
import os
import re
import time

import requests


class _NoKey(Exception):
    pass


def _gemini(prompt, model, json_mode):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise _NoKey()
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

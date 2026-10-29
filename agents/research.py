"""Recherche-Agent: sammelt, was die Zielgruppe gerade sucht und fragt, und wählt ein Thema."""
import random

import requests

from core import llm

UA = {"User-Agent": "Mozilla/5.0 (ki-team research bot)"}


def google_suggest(query, youtube=False):
    params = {"client": "firefox", "hl": "de", "gl": "de", "q": query}
    if youtube:
        params["ds"] = "yt"
    try:
        r = requests.get("https://suggestqueries.google.com/complete/search", params=params, headers=UA, timeout=15)
        return r.json()[1]
    except Exception:
        return []


def reddit_top(subreddit):
    try:
        r = requests.get(
            f"https://www.reddit.com/r/{subreddit}/top.json",
            params={"t": "week", "limit": 15},
            headers=UA,
            timeout=15,
        )
        return [c["data"]["title"] for c in r.json()["data"]["children"]]
    except Exception:
        return []  # Reddit blockt Cloud-Server manchmal – dann eben ohne


def collect_signals(cfg):
    signals = {"google": [], "youtube": [], "reddit": []}
    for term in cfg["recherche"]["suchbegriffe"]:
        for variant in (term, f"{term} wie", f"{term} ideen"):
            signals["google"] += google_suggest(variant)
        signals["youtube"] += google_suggest(term, youtube=True)
    for sub in cfg["recherche"].get("subreddits", []):
        signals["reddit"] += reddit_top(sub)
    return {k: list(dict.fromkeys(v))[:60] for k, v in signals.items()}


def pick_topic(cfg, posts, learnings, avoid=None, signals=None, wish=None):
    signals = signals or collect_signals(cfg)
    products = cfg.get("produkte") or []
    promo = bool(products) and random.random() < cfg.get("werbe_anteil", 0.4)
    recent = [p["topic"] for p in posts[-40:]]

    if promo:
        product_lines = "\n".join(f"- id={p['id']}: {p['name']} – {p['beschreibung']} (passt zu: {p['passt_zu']})" for p in products)
        product_task = f"Dieses Video soll ein Produkt sanft empfehlen. Wähle das passendste:\n{product_lines}\nSetze product_id auf dessen id."
    else:
        product_task = "Dieses Video ist reiner Mehrwert-Content ohne Werbung. Setze product_id auf null."

    prompt = f"""Du bist Recherche-Experte für Social-Media-Kurzvideos (Instagram Reels, TikTok).
Nische: {cfg['nische']['thema']}
Zielgruppe: {cfg['nische']['zielgruppe']}
Kernbotschaft des Kanals (jedes Thema muss darauf einzahlen): {cfg['nische'].get('kernbotschaft', '')}

Aktuelle Suchanfragen bei Google: {signals['google']}
Aktuelle Suchanfragen bei YouTube: {signals['youtube']}
Diskussionen auf Reddit diese Woche: {signals['reddit']}

Erkenntnisse aus unseren bisherigen Videos (sehr wichtig, daran orientieren):
{learnings}

Diese Themen hatten wir zuletzt schon (NICHT wiederholen):
{recent}

Diese Themenbereiche sind TABU, niemals wählen: {cfg['nische'].get('tabu_themen', '')}
{f"Diese Themen sind gerade an der Prüfung gescheitert, wähle etwas deutlich anderes: {avoid}" if avoid else ""}
{f"WICHTIG: Der Inhaber wünscht sich dieses Thema – nimm es und finde nur den besten Blickwinkel: {wish}" if wish else ""}

{product_task}

Wähle EIN konkretes Thema für ein 30-45-Sekunden-Video, das die Zielgruppe gerade wirklich interessiert
und realistisch ist (keine unseriösen Versprechen).
Antworte nur als JSON:
{{"topic": "...", "angle": "konkreter Blickwinkel / Aufhänger", "why": "warum das jetzt funktioniert", "product_id": null}}"""

    idea = llm.ask(prompt, cfg, json_mode=True)
    idea.setdefault("topic", cfg["nische"]["thema"])
    idea.setdefault("angle", idea["topic"])
    idea.setdefault("why", "")
    if idea.get("product_id") not in {p["id"] for p in products}:
        idea["product_id"] = None
    return idea

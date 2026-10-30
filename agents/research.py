"""Recherche-Agent: sammelt, was die Zielgruppe gerade sucht und fragt, und wählt ein Thema."""
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


FORMAT_NAMES = {"reel": "30-45-Sekunden-Reel (Kurzvideo)", "karussell": "Karussell-Post mit 6-8 Bildern zum Durchwischen"}


def next_plan(cfg, posts, settings):
    """Welches Ziel und welches Format ist als Nächstes dran? Wünsche per Telegram haben Vorrang."""
    strat = cfg["strategie"]
    goals, formats = strat["ziel_rotation"], strat["format_rotation"]
    n = len(posts)
    goal = settings.pop("naechstes_ziel", None) or goals[n % len(goals)]
    fmt = settings.pop("naechstes_format", None) or formats[n % len(formats)]
    return goal, fmt


def pick_topic(cfg, posts, learnings, goal, fmt, avoid=None, signals=None, wish=None):
    signals = signals or collect_signals(cfg)
    products = cfg.get("produkte") or []
    recent = [p["topic"] for p in posts[-40:]]
    goal_text = cfg["strategie"]["ziele"][goal]

    if goal == "monetarisierung" and products:
        product_lines = "\n".join(f"- id={p['id']}: {p['name']} – {p['beschreibung']} (passt zu: {p['passt_zu']})" for p in products)
        product_task = (f"Dieser Beitrag soll ein Produkt empfehlen. Wähle das passendste:\n{product_lines}\n"
                        "Setze product_id auf dessen id.\n"
                        "Das Thema MUSS eine echte, große Einstiegshürde der Zielgruppe ansprechen, die das Produkt löst – "
                        "z. B. 'Ich weiß nicht, was ich posten soll', 'Ich habe keine Follower', "
                        "'Wie verdient man mit Digistore24 überhaupt Geld?', 'Welches Produkt soll ich bewerben?', "
                        "'Ich habe neben dem Job keine Zeit'. Keine Detail- oder Nebenthemen.")
    else:
        product_task = "Dieser Beitrag ist reiner Mehrwert-Content ohne Werbung. Setze product_id auf null."

    prompt = f"""Du bist Recherche-Experte für virale Social-Media-Inhalte (Instagram, TikTok).
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

Format: {FORMAT_NAMES[fmt]}
Ziel dieses Beitrags: {goal_text}

{product_task}

Wähle EIN konkretes Thema, das genau dieses Ziel erreicht, die Zielgruppe gerade wirklich interessiert
und realistisch ist (keine unseriösen Versprechen). Denk an Formate, die viral gehen:
typische Fehler, Mythos vs. Wahrheit, Schritt-für-Schritt, Vorher/Nachher, "Niemand sagt dir …", Vergleiche.
Antworte nur als JSON:
{{"topic": "...", "angle": "konkreter Blickwinkel / Aufhänger", "why": "warum das jetzt funktioniert", "product_id": null}}"""

    idea = llm.ask(prompt, cfg, json_mode=True)
    idea.setdefault("topic", cfg["nische"]["thema"])
    idea.setdefault("angle", idea["topic"])
    idea.setdefault("why", "")
    if goal != "monetarisierung" or idea.get("product_id") not in {p["id"] for p in products}:
        idea["product_id"] = None
    idea["goal"], idea["format"] = goal, fmt
    return idea


def generate_ideas(cfg, posts, learnings):
    """10 virale Ideen (Reels + Karussells) für den Telegram-Befehl /ideen."""
    signals = collect_signals(cfg)
    recent = [p["topic"] for p in posts[-30:]]
    prompt = f"""Du bist Social-Media-Stratege für Instagram und TikTok.
Nische: {cfg['nische']['thema']}
Kernbotschaft: {cfg['nische'].get('kernbotschaft', '')}
Zielgruppe: {cfg['nische']['zielgruppe']}
Tabu-Themen: {cfg['nische'].get('tabu_themen', '')}
Aktuelle Suchanfragen: {signals['google'][:30]}
Was bei uns funktioniert: {learnings}
Schon gemacht (nicht wiederholen): {recent}

Erstelle 10 virale Ideen: 6 Reels und 4 Karussells, gemischt für die Ziele Wachstum, Interaktion und Monetarisierung.
Jede Idee: scroll-stoppender Hook + ein Satz, worum es geht. Keine Einkommensversprechen.
Antworte nur als JSON:
{{"ideen": [{{"format": "Reel", "ziel": "Wachstum", "hook": "...", "inhalt": "..."}}]}}"""
    return llm.ask(prompt, cfg, json_mode=True).get("ideen", [])

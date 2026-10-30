"""Content-Agent: schreibt Hooks, Skripte (Reels), Folien (Karussells), Captions und Hashtags."""
from core import llm


def product_by_id(cfg, product_id):
    return next((p for p in cfg.get("produkte") or [] if p["id"] == product_id), None)


def _context(cfg, idea, learnings, feedback):
    fix = f"\nDer letzte Entwurf wurde abgelehnt. Behebe diese Probleme:\n{feedback}\n" if feedback else ""
    return f"""Nische: {cfg['nische']['thema']}
Zielgruppe: {cfg['nische']['zielgruppe']}
Kernbotschaft des Kanals (der Beitrag zahlt darauf ein): {cfg['nische'].get('kernbotschaft', '')}
Tonalität: {cfg['nische']['tonalitaet']}
Sprache: {cfg['nische']['sprache']}

Thema: {idea['topic']}
Blickwinkel: {idea['angle']}
Ziel dieses Beitrags: {cfg['strategie']['ziele'][idea['goal']]}

Was bei uns funktioniert (unbedingt beachten):
{learnings}
{fix}"""


def _cta_rule(product):
    if product:
        return (f"Empfiehl am Ende natürlich und ehrlich das Produkt \"{product['name']}\" ({product['beschreibung']}) "
                "als logischen nächsten Schritt. Call-to-Action: 'Link in meiner Bio'. Keine Übertreibung.")
    return "Kein Produkt erwähnen. Call-to-Action passend zum Ziel (siehe oben)."


def _hook_rules():
    return """HOOK (das Wichtigste – entscheidet in 1-2 Sekunden, ob jemand weiterscrollt):
- Schreib zuerst 5 verschiedene Hook-Varianten mit unterschiedlichen Techniken:
  Neugier-Lücke ("Niemand sagt dir, dass …"), typischer Fehler ("Hör auf, … zu machen"),
  Widerspruch/Mythos ("Du brauchst keine … um …"), konkrete Zahl ("3 Dinge, die …"),
  direkte Ansprache eines Schmerzes ("Du willst nebenbei was aufbauen, hast aber keine Zeit?").
- Wähle davon die stärkste als "hook": max. 12 Wörter, konkret, ohne Floskeln, ohne Clickbait-Lüge."""


def _caption_rules(cfg):
    h = cfg["strategie"]["hashtags"]
    return f"""- caption_instagram: Zeile 1 = eigener scroll-stoppender Hook (max. 120 Zeichen, anders formuliert als im Beitrag).
  Dann Leerzeile, 2-4 kurze Zeilen Mehrwert (sparsam Emojis wie ✅ 👉 💡), Leerzeile,
  zum Schluss ein klarer Call-to-Action passend zum Ziel. Keine Hashtags.
- caption_tiktok: 1 Hook-Satz + Call-to-Action, max. 150 Zeichen, keine Hashtags.
- hashtags: genau {h['anzahl_instagram'] - 1} deutsche Hashtags ohne #, als Mischung:
  1 großer (sehr viele Beiträge), 2 mittlere, Rest Nische (spezifisch für Thema und Zielgruppe).
  Keine generischen Spam-Tags wie fyp, viral, explore, love."""


def write_script(cfg, idea, learnings, feedback=None):
    """Reel: gesprochenes Skript mit Szenen."""
    product = product_by_id(cfg, idea.get("product_id"))
    prompt = f"""Du bist ein erfahrener Short-Video-Texter für virale Instagram Reels und TikToks.
{_context(cfg, idea, learnings, feedback)}
{_hook_rules()}

SKRIPT:
- Gesprochener Text insgesamt 70-110 Wörter (ca. 30-45 Sekunden).
- Szene 1 ist der gewählte Hook (wörtlich). 5 bis 7 Szenen, jede = 1-2 kurze Sätze zum Vorlesen.
- Nach dem Hook sofort Spannung halten ("Und das Wichtigste kommt am Ende"), kein langes Intro.
- Konkret und umsetzbar, mit echtem Mehrwert. Keine Einkommensversprechen, keine Euro-Beträge als Versprechen.
- {_cta_rule(product)}
- "hook_text": der Hook als kurzer Bildschirm-Titel, max. 6 Wörter (erscheint groß in den ersten Sekunden).
- "search" ist ein englischer Suchbegriff (2-4 Wörter) für ein passendes Stock-Video,
  z. B. "woman typing laptop", "coffee morning desk". Keine Logos, keine Texte.
  Bevorzugter Bildstil: {cfg['video'].get('bildstil', 'passend zum Thema')}.

CAPTION & HASHTAGS:
{_caption_rules(cfg)}

Antworte nur als JSON:
{{"hook_varianten": ["...", "...", "...", "...", "..."], "hook": "...", "hook_text": "...",
"scenes": [{{"text": "...", "search": "..."}}], "caption_instagram": "...", "caption_tiktok": "...", "hashtags": ["..."]}}"""

    script = llm.ask(prompt, cfg, json_mode=True)
    script["format"] = "reel"
    script["product_id"] = product["id"] if product else None
    return script


def write_carousel(cfg, idea, learnings, feedback=None):
    """Karussell: 6-8 Folien zum Durchwischen."""
    product = product_by_id(cfg, idea.get("product_id"))
    prompt = f"""Du bist Experte für virale Instagram-Karussells (Bild-Posts zum Durchwischen).
{_context(cfg, idea, learnings, feedback)}
{_hook_rules()}

FOLIEN:
- 6 bis 8 Folien. Folie 1: der gewählte Hook als "titel" (max. 8 Wörter) + kurzer Untertitel als "text",
  der neugierig auf Folie 2 macht ("Wisch weiter 👉").
- Folien 2 bis vorletzte: je ein konkreter Punkt. "titel" max. 6 Wörter, "text" max. 25 Wörter.
  Jede Folie muss alleine verständlich sein und Lust auf die nächste machen.
- Letzte Folie: Zusammenfassung + Call-to-Action. {_cta_rule(product)}
- Konkret und umsetzbar, mit echtem Mehrwert. Keine Einkommensversprechen.

CAPTION & HASHTAGS:
{_caption_rules(cfg)}

Antworte nur als JSON:
{{"hook_varianten": ["...", "...", "...", "...", "..."], "hook": "...",
"slides": [{{"titel": "...", "text": "..."}}], "caption_instagram": "...", "caption_tiktok": "...", "hashtags": ["..."]}}"""

    script = llm.ask(prompt, cfg, json_mode=True)
    script["format"] = "karussell"
    script["product_id"] = product["id"] if product else None
    return script


def spoken_text(script):
    """Der eigentliche Inhalt als Fließtext (für den Prüfer)."""
    if script.get("format") == "karussell":
        return " ".join(f"{s.get('titel', '')}. {s.get('text', '')}" for s in script.get("slides", []))
    return " ".join(s["text"].strip() for s in script["scenes"])


def first_line(script):
    if script.get("format") == "karussell":
        return script["slides"][0]["titel"]
    return script["scenes"][0]["text"]


def _hashtags(cfg, script, platform):
    h = cfg["strategie"]["hashtags"]
    limit = h["anzahl_instagram"] if platform == "instagram" else h["anzahl_tiktok"]
    brand = h.get("marke", "").lstrip("#")
    tags = [t.lstrip("#").replace(" ", "") for t in script.get("hashtags", []) if t.strip()]
    tags = [t for t in tags if t.lower() != brand.lower()][: limit - (1 if brand else 0)]
    if brand:
        tags.append(brand)
    return " ".join("#" + t for t in tags)


def build_caption(cfg, script, platform):
    tags = _hashtags(cfg, script, platform)
    if platform == "instagram":
        parts = [script["caption_instagram"], tags]
        if script.get("product_id"):
            parts.insert(0, cfg["kennzeichnung"]["instagram"])
    else:
        parts = [script["caption_tiktok"], tags]
        if script.get("product_id"):
            parts.append(cfg["kennzeichnung"]["tiktok"])
    return "\n\n".join(p for p in parts if p)

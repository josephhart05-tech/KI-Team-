"""Content-Agent: schreibt Skript, Szenen und Captions für das Video."""
from core import llm


def product_by_id(cfg, product_id):
    return next((p for p in cfg.get("produkte") or [] if p["id"] == product_id), None)


def write_script(cfg, idea, learnings, feedback=None):
    product = product_by_id(cfg, idea.get("product_id"))
    if product:
        cta_rule = (f"Empfiehl am Ende natürlich und ehrlich das Produkt \"{product['name']}\" ({product['beschreibung']}). "
                    "Call-to-Action: 'Link in meiner Bio'. Keine Übertreibung.")
    else:
        cta_rule = "Kein Produkt. Call-to-Action: zum Speichern oder Folgen auffordern."

    fix = f"\nDer letzte Entwurf wurde abgelehnt. Behebe diese Probleme:\n{feedback}\n" if feedback else ""

    prompt = f"""Du bist ein erfahrener Short-Video-Texter für Instagram Reels und TikTok.
Nische: {cfg['nische']['thema']}
Zielgruppe: {cfg['nische']['zielgruppe']}
Tonalität: {cfg['nische']['tonalitaet']}
Sprache: {cfg['nische']['sprache']}

Thema: {idea['topic']}
Blickwinkel: {idea['angle']}

Was bei uns funktioniert (unbedingt beachten):
{learnings}
{fix}
Regeln:
- Gesprochener Text insgesamt 70-110 Wörter (ca. 30-45 Sekunden).
- Szene 1 ist der Hook: max. 12 Wörter, muss in 2 Sekunden neugierig machen.
- 5 bis 7 Szenen. Jede Szene = 1-2 kurze Sätze, die vorgelesen werden.
- Konkret und umsetzbar, mit echtem Mehrwert. Keine Einkommensversprechen, keine konkreten Euro-Beträge als Versprechen.
- {cta_rule}
- "search" ist ein englischer Suchbegriff (2-4 Wörter) für ein passendes Stock-Video im Hochformat,
  z. B. "woman typing laptop", "coffee morning desk". Keine Logos, keine Texte.
  Bevorzugter Bildstil: {cfg['video'].get('bildstil', 'passend zum Thema')}.
- caption_instagram: 2-5 Sätze, Mehrwert + Frage an die Community, ohne Hashtags.
- caption_tiktok: 1-2 kurze Sätze, ohne Hashtags.
- hashtags: 5-8 passende deutsche Hashtags ohne #.

Antworte nur als JSON:
{{"hook": "...", "scenes": [{{"text": "...", "search": "..."}}], "caption_instagram": "...", "caption_tiktok": "...", "hashtags": ["..."]}}"""

    script = llm.ask(prompt, cfg, json_mode=True)
    script["product_id"] = product["id"] if product else None
    return script


def spoken_text(script):
    return " ".join(s["text"].strip() for s in script["scenes"])


def build_caption(cfg, script, platform):
    tags = " ".join("#" + t.lstrip("#").replace(" ", "") for t in script.get("hashtags", []))
    if platform == "instagram":
        parts = [script["caption_instagram"], tags]
        if script.get("product_id"):
            parts.insert(0, cfg["kennzeichnung"]["instagram"])
    else:
        parts = [script["caption_tiktok"], tags]
        if script.get("product_id"):
            parts.append(cfg["kennzeichnung"]["tiktok"])
    return "\n\n".join(p for p in parts if p)

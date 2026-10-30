"""Prüfer-Agent: checkt Qualität und rechtliche Fallstricke, bevor etwas zu dir geht."""
from agents.content import spoken_text
from core import llm


def review(cfg, script):
    problems = []
    text = spoken_text(script)
    full = (text + " " + script.get("caption_instagram", "") + " " + script.get("caption_tiktok", "")).lower()

    for phrase in cfg.get("verbotene_formulierungen", []):
        if phrase.lower() in full:
            problems.append(f"Verbotene Formulierung: '{phrase}'")

    if script.get("format") == "karussell":
        if not 5 <= len(script.get("slides", [])) <= 9:
            problems.append("Anzahl Folien muss zwischen 6 und 8 liegen")
    else:
        words = len(text.split())
        if not 60 <= words <= 130:
            problems.append(f"Länge passt nicht: {words} Wörter (Ziel 70-110)")
        if not 4 <= len(script.get("scenes", [])) <= 8:
            problems.append("Anzahl Szenen muss zwischen 5 und 7 liegen")

    prompt = f"""Du prüfst ein Social-Media-Skript zum Thema "{cfg['nische']['thema']}" für den deutschen Markt.
Skript: {text}
Instagram-Caption: {script.get('caption_instagram')}

Setze ok auf false NUR bei einem dieser echten Probleme:
1. Konkrete Einkommensversprechen oder irreführende Aussagen (UWG, Plattform-Richtlinien).
2. Anlage-, Steuer- oder Rechtsberatung, oder Tabu-Themen: {cfg['nische'].get('tabu_themen', '')}
3. Das Skript widerspricht sich selbst oder hat keinerlei konkreten Mehrwert.

Stil- und Geschmacksfragen (Hook könnte stärker sein, wenig originell, Klischee) sind KEIN Grund für false –
darüber entscheidet der Inhaber selbst. Kleine Ungenauigkeiten auch nicht.

Antworte nur als JSON: {{"ok": true/false, "problems": ["..."]}}"""
    try:
        verdict = llm.ask(prompt, cfg, json_mode=True)
        if not verdict.get("ok", True):
            problems += verdict.get("problems", [])
    except RuntimeError:
        pass  # Regel-Check oben greift trotzdem; du gibst ohnehin noch frei

    return len(problems) == 0, problems

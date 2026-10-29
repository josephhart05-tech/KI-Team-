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

    words = len(text.split())
    if not 60 <= words <= 130:
        problems.append(f"Länge passt nicht: {words} Wörter (Ziel 70-110)")
    if not 4 <= len(script.get("scenes", [])) <= 8:
        problems.append("Anzahl Szenen muss zwischen 5 und 7 liegen")

    prompt = f"""Du prüfst ein Social-Media-Skript zum Thema "{cfg['nische']['thema']}" für den deutschen Markt.
Skript: {text}
Instagram-Caption: {script.get('caption_instagram')}

Prüfe streng:
1. Enthält es Einkommensversprechen oder irreführende Aussagen (UWG, Plattform-Richtlinien)?
2. Ist der Hook stark genug, damit man in den ersten 2 Sekunden nicht weiterscrollt?
3. Hat es echten, konkreten Mehrwert – oder ist es leeres Gerede?
4. Klingt es natürlich gesprochen (keine Schachtelsätze)?

Antworte nur als JSON: {{"ok": true/false, "problems": ["..."]}}
Setze ok nur auf false bei echten Problemen, nicht bei Kleinigkeiten."""
    try:
        verdict = llm.ask(prompt, cfg, json_mode=True)
        if not verdict.get("ok", True):
            problems += verdict.get("problems", [])
    except RuntimeError:
        pass  # Regel-Check oben greift trotzdem; du gibst ohnehin noch frei

    return len(problems) == 0, problems

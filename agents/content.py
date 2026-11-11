"""Content-Agent: schreibt Hooks, Skripte (Reels), Folien (Karussells), Captions und Hashtags."""
from core import llm


def product_by_id(cfg, product_id):
    return next((p for p in cfg.get("produkte") or [] if p["id"] == product_id), None)


def _context(cfg, idea, learnings, feedback):
    fix = f"\nDer letzte Entwurf wurde abgelehnt. Behebe diese Probleme:\n{feedback}\n" if feedback else ""
    if idea.get("fakten"):
        fix += (f"\nECHTE FAKTEN VOM INHABER (Ich-Perspektive). Verwende NUR diese Erlebnisse, Zahlen und Ergebnisse – "
                f"erfinde keine weiteren Fortschritte, Zahlen oder Erfolge dazu:\n{idea['fakten']}\n")
    story = cfg["nische"].get("meine_geschichte", "")
    if story:
        fix += (f"\nDIE ECHTE GESCHICHTE DES INHABERS (darf in Ich-Form verwendet werden, wenn es zum Thema passt – "
                f"nichts hinzuerfinden, keine Details ausschmücken, die hier nicht stehen):\n{story}\n")
    pains = cfg["nische"].get("pain_points") or []
    if pains:
        fix += ("\nSCHMERZPUNKTE DER ZIELGRUPPE – der Beitrag muss mindestens einen davon direkt ansprechen, "
                "am besten schon im Hook, und dann Mut machen bzw. einen ersten machbaren Schritt zeigen:\n- "
                + "\n- ".join(pains) + "\n")
    setup = cfg["nische"].get("mein_setup", "")
    if setup:
        fix += (f"\nSO ARBEITET DER INHABER WIRKLICH (sein Content-System). Wenn der Beitrag in Ich-Form beschreibt, "
                f"wie er arbeitet, plant oder Content erstellt: NUR das hier verwenden, keine anderen Tools, "
                f"Abläufe oder Zeitangaben erfinden:\n{setup}\n"
                "Allgemeine Tipps für den Zuschauer ('du kannst z. B. Canva nutzen') sind erlaubt – "
                "aber nie als eigenes Vorgehen des Inhabers ausgeben.\n")
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
  Schreib nur den Hook-Text selbst, ohne den Namen der Technik davor.
- Wähle davon die stärkste als "hook": max. 12 Wörter, konkret, ohne Floskeln, ohne Clickbait-Lüge.

EHRLICHKEIT:
- Jedes Versprechen im Beitrag wird auch eingelöst. Wer "das Wichtigste kommt am Ende" sagt,
  bringt den wichtigsten Inhaltspunkt auch am Ende – vor dem Call-to-Action, nicht stattdessen.
- Keine unbelegten Tatsachenbehauptungen wie "die meisten", "der Hauptgrund", "90 % scheitern".
  Stattdessen vorsichtig formulieren: "viele", "einer der häufigsten Gründe", "oft".
- Anleitungen zu Tools (z. B. Digistore24) nur so beschreiben, wie sie sicher funktionieren –
  im Zweifel allgemeiner formulieren ("achte auf die Stornoquote") statt eine Funktion zu erfinden."""


def _caption_rules(cfg):
    h = cfg["strategie"]["hashtags"]
    return f"""- caption_instagram: Zeile 1 = eigener scroll-stoppender Hook (max. 120 Zeichen, anders formuliert als im Beitrag).
  Dann Leerzeile, 2-4 kurze Zeilen Mehrwert (sparsam Emojis wie ✅ 👉 💡), Leerzeile,
  zum Schluss ein klarer Call-to-Action passend zum Ziel. Keine Hashtags.
- caption_tiktok: 1 Hook-Satz + Call-to-Action, max. 150 Zeichen, keine Hashtags.
- hashtags: genau {h['anzahl_instagram'] - 1} deutsche Hashtags ohne #, in dieser Reihenfolge:
  1. ein GROSSER, bekannter Hashtag mit sehr vielen Beiträgen (z. B. nebeneinkommen, affiliatemarketing, onlinebusiness),
  2.-3. mittlere, 4. ein Nischen-Hashtag (spezifisch für Thema und Zielgruppe).
  Keine generischen Spam-Tags wie fyp, viral, explore, love."""


def _value_rule():
    return """MEHRWERT-PFLICHT: Der Beitrag nennt mindestens ein KONKRETES Tool, Beispiel oder einen konkreten Schritt
mit Namen (z. B. "Digistore24-Marktplatz nach Gravity sortieren", "Canva", "Pixabay", "3 Posts pro Woche").
Nie nur andeuten ("es gibt Quellen", "ich zeige dir wie") – der Zuschauer muss etwas Konkretes mitnehmen,
auch wenn er nicht auf den Link klickt."""


def write_script(cfg, idea, learnings, feedback=None):
    """Reel: animiertes Strichmännchen-Video mit Szenen (Text im Bild, keine Stimme)."""
    from agents.strichvideo import MOTIVE
    product = product_by_id(cfg, idea.get("product_id"))
    motive = ", ".join(f"{k} ({v})" for k, v in MOTIVE.items())
    prompt = f"""Du bist ein erfahrener Texter für virale Strichmännchen-Erklärvideos auf Instagram und TikTok (ohne Stimme, Text im Bild).
{_context(cfg, idea, learnings, feedback)}
{_hook_rules()}

SKRIPT – Strichmännchen-STORY ohne Stimme (dunkler Look, leuchtende Grafiken, Untertitel unten):
- Erzähle eine kleine Geschichte mit EINER Figur mit Vornamen (z. B. Lena, Max, Tom, Sarah), in der sich die
  Zielgruppe wiedererkennt. Beispiel-Ablauf: "18 Uhr. Lena kommt von der Arbeit und sagt: Ich hab keine Zeit." →
  "Dann scrollt sie 2,5 Stunden durchs Handy." → "Dabei bräuchte sie nur eine Stunde am Tag." →
  "Eine Stunde pro Tag sind 365 Stunden im Jahr." → Methode mit 3 Schritten → Ergebnis → Pointe.
- 6 bis 8 Szenen in dieser Reihenfolge:
  1. Hook-Szene: Alltagssituation + großer Leucht-"titel" (max. 3 Wörter, z. B. „KEINE ZEIT.“, titel_farbe "rot").
  2.-3. Problem / Wiedererkennung (konkrete Zahl oder Situation).
  4. Wendepunkt mit Zahl ("zahl" oder "ring").
  5. GENAU EINE "regeln"-Szene = der Mehrwert: Methode mit Namen + 3 konkrete Schritte.
  6. Ergebnis ("vergleich" oder "treppe").
  7. Pointe in einem Satz.
- "text" = Untertitel: genau EIN kurzer Satz, HÖCHSTENS 10 Wörter. Kürzer ist besser. Normale Groß-/Kleinschreibung.
  1-3 Schlüsselwörter oder Zahlen in *Sternchen* (leuchten gold), Probleme in ~Tilden~ (leuchten rot).
- "visual": genau einer dieser Schlüssel: {motive}
  Felder je nach visual: "titel", "titel_farbe" (gold|rot|weiss), "pose", "zahl", "label" (max. 3 Wörter),
  "anteil" (0-1), "links", "rechts" (je 1 Wort).
- "regeln"-Szene: KEIN "text". "titel" = Name der Methode (max. 18 Zeichen, z. B. "60-MINUTEN-METHODE"),
  "regeln" = genau 3 Einträge ["kurz" (max. 6 Zeichen, z. B. "20 MIN", "1.", "STOP"), "Stichwort" (1-2 Wörter),
  "Erklärung" (max. 8 Wörter, konkret und umsetzbar)].
- Keine Einkommensversprechen, keine Euro-Beträge als Versprechen. Zahlen nur, wenn sie logisch stimmen.
- {_cta_rule(product)}
{_value_rule()}
- "abspann": Aufforderung für die Schlusskarte, max. 6 Wörter (z. B. "Speicher dir die 60-Minuten-Methode").
- "hook_text": der Hook in max. 7 Wörtern (für die Übersicht).

CAPTION & HASHTAGS:
{_caption_rules(cfg)}

Antworte nur als JSON:
{{"hook_varianten": ["...", "...", "...", "...", "..."], "hook": "...", "hook_text": "...", "abspann": "...",
"scenes": [{{"visual": "uhr", "titel": "...", "titel_farbe": "rot", "text": "..."}},
  {{"visual": "zahl", "zahl": "365", "label": "STUNDEN IM JAHR", "text": "..."}},
  {{"visual": "regeln", "titel": "...", "regeln": [["...", "...", "..."], ["...", "...", "..."], ["...", "...", "..."]]}}], "caption_instagram": "...", "caption_tiktok": "...", "hashtags": ["..."]}}"""

    script = llm.ask(prompt, cfg, json_mode=True)
    for sc in script.get("scenes", []):
        if sc.get("visual") not in MOTIVE:
            sc["visual"] = "zahl" if sc.get("zahl") else "figur"
        sc.setdefault("text", "")
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
  Titel NICHT mit "Schritt 1:", "Tipp 2:" o. Ä. beginnen – die Nummer steht schon groß auf der Folie.
- Keine Emojis in titel oder text der Folien (nur in den Captions).
- Der Call-to-Action muss zum Inhalt passen: "Kommentiere 1, 2 oder 3" nur, wenn es genau diese Punkte gibt.
- Letzte Folie: Zusammenfassung + Call-to-Action. {_cta_rule(product)}
- Konkret und umsetzbar, mit echtem Mehrwert. Keine Einkommensversprechen.
{_value_rule()}

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
    parts = []
    for s in script["scenes"]:
        parts.append((s.get("text") or "").replace("*", "").replace("~", "").strip())
        parts += [" – ".join(str(x) for x in r) + "." for r in s.get("regeln") or []]
    return " ".join(p for p in parts if p)


def first_line(script):
    if script.get("format") == "karussell":
        return script["slides"][0]["titel"]
    first = script["scenes"][0] if script.get("scenes") else {}
    return (script.get("hook_text") or first.get("text") or first.get("titel") or "").replace("*", "").replace("~", "")


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
    serie = f"— {script['serie']} | DF · Digitale Freiheit" if script.get("serie") else ""
    if platform == "instagram":
        parts = [script["caption_instagram"], serie, tags]
        if script.get("product_id"):
            parts.insert(0, cfg["kennzeichnung"]["instagram"])
    else:
        parts = [script["caption_tiktok"], tags]
        if script.get("product_id"):
            parts.append(cfg["kennzeichnung"]["tiktok"])
    return "\n\n".join(p for p in parts if p)

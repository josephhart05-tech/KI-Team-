"""Geschäftsführerin: plant die Woche, setzt Prioritäten, steuert die Produktion und hält dich auf Kurs."""
from datetime import date, timedelta

from agents import research
from core import llm
from core.storage import now

DAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
TIMES = ["morgens", "nachmittags"]
GOAL_ICONS = {"wachstum": "🚀", "einblick": "📖", "interaktion": "💬", "monetarisierung": "💰"}
PRIO_ICONS = {"hoch": "🔴", "mittel": "🟡", "niedrig": "🟢"}


def _gf(cfg):
    return cfg.get("geschaeftsfuehrung") or {}


def name(cfg):
    return _gf(cfg).get("name", "Clara")


def today():
    return now().date()


def week_number(cfg):
    start = _gf(cfg).get("neustart_datum")
    if not start:
        return None
    return max(1, (today() - date.fromisoformat(start)).days // 7 + 1)


def current_plan(state):
    plan = state.get("wochenplan")
    if not plan:
        return None
    start = date.fromisoformat(plan["woche_start"])
    return plan if start <= today() < start + timedelta(days=7) else None


def next_slot(state):
    """Nächster offener Slot von heute. Verpasste Tage werden übersprungen statt nachgeholt –
    sonst würde das Team dem Plan dauerhaft hinterherlaufen."""
    plan = current_plan(state)
    if not plan:
        return None
    for slot in plan["slots"]:
        slot_day = date.fromisoformat(slot["datum"])
        if slot["status"] == "offen" and slot_day < today():
            slot["status"] = "uebersprungen"
        elif slot["status"] == "offen" and slot_day == today():
            return slot
    return None


def make_week_plan(cfg, posts, state, learnings):
    """Plant 14 Beiträge (2 pro Tag) und die Aufgaben für dich. Sonntags für die kommende Woche."""
    t = today()
    monday = t + timedelta(days=1) if t.weekday() == 6 else t - timedelta(days=t.weekday())
    settings = state.get("settings", {})
    allowed = list(dict.fromkeys(research.active_goals(cfg, settings, has_journal=True)))
    goal_texts = "\n".join(f"- {g}: {cfg['strategie']['ziele'][g]}" for g in allowed)
    week = week_number(cfg)
    webinar_week = _gf(cfg).get("webinar_ab_woche", 5)
    signals = research.collect_signals(cfg)
    recent = [p["topic"] for p in posts[-30:]]
    rejected = [p["topic"] for p in posts if p.get("status") == "rejected"][-10:]
    numbers = [f"{z['datum']}: {z['text']}" for z in state.get("zahlen", [])[-4:]]
    open_tasks = [a["text"] for a in state.get("aufgaben", []) if not a.get("erledigt")]

    prompt = f"""Du bist {name(cfg)}, die Geschäftsführerin eines kleinen KI-Content-Teams.
Du planst, setzt Prioritäten und sorgst dafür, dass der Inhaber Schritt für Schritt vorankommt.
Stil: klar, strukturiert, freundlich, motivierend, per du.

DAS BUSINESS
Nische: {cfg['nische']['thema']}
Kernbotschaft: {cfg['nische'].get('kernbotschaft', '')}
Zielgruppe: {cfg['nische']['zielgruppe']}
Geschichte des Inhabers: {cfg['nische'].get('meine_geschichte', '')}
Schmerzpunkte der Zielgruppe: {cfg['nische'].get('pain_points', [])}
Tabu-Themen: {cfg['nische'].get('tabu_themen', '')}

PROJEKTSTAND
Woche {week or '?'} seit dem Neustart. Plan: Wochen 1 bis {webinar_week - 1} nur Vertrauen und Mehrwert.
Ab Woche {webinar_week} prüfst du die Zahlen und empfiehlst das Webinar erst, wenn Views und Interaktionen gut genug sind.
Webinar-Beiträge sind aktuell: {'AN' if settings.get('monetarisierung_aktiv') else 'AUS'}
Vom Inhaber gemeldete Zahlen: {numbers or 'noch keine'}
Erkenntnisse aus bisherigen Beiträgen: {learnings}
Zuletzt produziert (nicht wiederholen): {recent}
Vom Inhaber abgelehnt (daraus lernen): {rejected or 'nichts'}
Offene Aufgaben aus der Vorwoche: {open_tasks or 'keine'}
Aktuelle Suchanfragen der Zielgruppe: {signals['google'][:25]}

ERLAUBTE ZIELE (nur diese verwenden):
{goal_texts}
Format: immer "reel" (animiertes Strichmännchen-Video ohne Stimme). Keine Karussells.
"einblick"-Beiträge brauchen einen echten Tagebuch-Eintrag des Inhabers – plane höchstens 3 pro Woche
und lege für jeden eine Aufgabe an ("Bis Mi: Tagebuch-Eintrag zu ...").

AUFGABE
1. Ein Wochenziel und ein Fokus-Thema, das die Woche zusammenhält (roter Faden statt Zufall).
2. Genau 14 Slots: Mo morgens, Mo nachmittags, Di morgens, ... So nachmittags.
   Jeder Slot: ziel, format, konkretes thema (1 Satz), welcher pain_point getroffen wird.
   Abwechslungsreich, aufeinander aufbauend, keine Wiederholungen.
3. 3 bis 6 Aufgaben für den Inhaber selbst (was nur ein Mensch kann), mit prio hoch/mittel/niedrig.
   Z. B. Tagebuch-Einträge, Stories mit Umfrage, 15 Min. täglich in der Nische kommentieren,
   sonntags Zahlen melden mit /zahlen, Profil-Pflege. Konkret und machbar neben dem Job.
4. Eine kurze Empfehlung (2-4 Sätze) zur Lage – ab Woche {webinar_week} inkl. Einschätzung, ob das Webinar starten sollte.

Antworte nur als JSON:
{{"wochenziel": "...", "fokus": "...",
"slots": [{{"ziel": "...", "format": "reel", "thema": "...", "pain_point": "..."}}],
"aufgaben": [{{"text": "...", "prio": "hoch"}}],
"empfehlung": "..."}}"""

    data = llm.ask(prompt, cfg, json_mode=True)
    raw = data.get("slots") or []
    slots = []
    for i in range(14):
        s = raw[i] if i < len(raw) else {}
        goal = s.get("ziel") if s.get("ziel") in allowed else allowed[i % len(allowed)]
        fmt = s.get("format") if s.get("format") in ("reel", "karussell") else "reel"
        slots.append({
            "datum": (monday + timedelta(days=i // 2)).isoformat(), "zeit": TIMES[i % 2],
            "ziel": goal, "format": fmt, "thema": s.get("thema", ""), "pain_point": s.get("pain_point", ""),
            "status": "offen",
        })

    carried = [a for a in state.get("aufgaben", []) if not a.get("erledigt")]
    new = [{"text": a["text"], "prio": a.get("prio", "mittel"), "erledigt": False}
           for a in data.get("aufgaben", []) if a.get("text")]
    state["aufgaben"] = (carried + new)[:8]
    state["wochenplan"] = {
        "woche_start": monday.isoformat(), "wochenziel": data.get("wochenziel", ""),
        "fokus": data.get("fokus", ""), "slots": slots,
    }
    return state["wochenplan"], data.get("empfehlung", "")


def _slot_line(slot):
    d = date.fromisoformat(slot["datum"])
    mark = {"erstellt": "✅", "uebersprungen": "⏭"}.get(slot["status"], "▫️")
    fmt = "Karussell" if slot["format"] == "karussell" else "Reel"
    return f"{mark} {DAYS[d.weekday()]} {slot['zeit']} · {GOAL_ICONS.get(slot['ziel'], '')} {fmt}: {slot['thema']}"


def format_tasks(state):
    tasks = state.get("aufgaben", [])
    if not tasks:
        return "Keine offenen Aufgaben. 🎉"
    order = {"hoch": 0, "mittel": 1, "niedrig": 2}
    lines = []
    for i, a in sorted(enumerate(tasks, 1), key=lambda x: (x[1].get("erledigt", False), order.get(x[1].get("prio"), 1))):
        icon = "✅" if a.get("erledigt") else PRIO_ICONS.get(a.get("prio"), "🟡")
        lines.append(f"{icon} {i}. {a['text']}")
    return "\n".join(lines) + "\n\nErledigt? Schreib /erledigt und die Nummer."


def format_plan(cfg, plan, state, recommendation=""):
    week = week_number(cfg)
    text = (f"🗓 Wochenplan von {name(cfg)}" + (f" – Woche {week} seit dem Neustart" if week else "") +
            f"\n\n🎯 Wochenziel: {plan['wochenziel']}\n🧭 Fokus: {plan['fokus']}\n\n" +
            "\n".join(_slot_line(s) for s in plan["slots"]) +
            f"\n\n📋 Deine Aufgaben diese Woche:\n{format_tasks(state)}")
    if recommendation:
        text += f"\n\n💬 {name(cfg)} meint:\n{recommendation}"
    return text


def briefing(cfg, state, posts):
    plan = current_plan(state)
    week = week_number(cfg)
    lines = [f"☀️ Guten Morgen! Dein Briefing von {name(cfg)}" + (f" (Woche {week})" if week else "")]
    if plan:
        todays = [s for s in plan["slots"] if s["datum"] == today().isoformat()]
        lines.append(f"\n🎯 Wochenziel: {plan['wochenziel']}")
        if todays:
            lines.append("\n📅 Heute produziert das Team:\n" + "\n".join(_slot_line(s) for s in todays))
        needs_journal = [s for s in plan["slots"] if s["ziel"] == "einblick" and s["status"] == "offen"]
        if needs_journal and not state.get("tagebuch"):
            lines.append("\n📖 Für die geplanten Einblicke brauche ich einen echten Tagebuch-Eintrag von dir: /tagebuch …")
    pending = sum(1 for p in posts if p.get("status") == "pending")
    if pending:
        lines.append(f"\n⏳ {pending} Beitrag/Beiträge warten auf deine Freigabe.")
    open_tasks = [a for a in state.get("aufgaben", []) if not a.get("erledigt")]
    if open_tasks:
        top = sorted(open_tasks, key=lambda a: {"hoch": 0, "mittel": 1, "niedrig": 2}.get(a.get("prio"), 1))[:3]
        lines.append("\n📋 Deine Top-Aufgaben:\n" + "\n".join(f"{PRIO_ICONS.get(a.get('prio'), '🟡')} {a['text']}" for a in top))
    lines.append("\nAlle Aufgaben: /aufgaben · Wochenplan: /plan")
    return "\n".join(lines)


def assess_numbers(cfg, state, text):
    """Kurze Einschätzung, wenn du per /zahlen deine Werte meldest."""
    week = week_number(cfg)
    history = [f"{z['datum']}: {z['text']}" for z in state.get("zahlen", [])[-6:]]
    webinar_week = _gf(cfg).get("webinar_ab_woche", 5)
    prompt = f"""Du bist {name(cfg)}, Geschäftsführerin eines kleinen Content-Business (Nische: {cfg['nische']['thema']}).
Woche {week or '?'} seit dem Neustart. Das Webinar soll frühestens ab Woche {webinar_week} kommen –
und nur, wenn Views und Interaktionen gut genug sind.
Bisher gemeldete Zahlen: {history}
Neu gemeldet: {text}

Gib eine ehrliche, kurze Einschätzung (max. 5 Sätze, per du): Entwicklung, was gut läuft, eine konkrete Empfehlung
für nächste Woche. Ab Woche {webinar_week}: sag klar, ob du /webinar an empfiehlst oder noch wartest – mit Begründung.
Erfinde keine Zahlen und vergleiche nicht mit erfundenen Durchschnittswerten."""
    return llm.ask(prompt, cfg)

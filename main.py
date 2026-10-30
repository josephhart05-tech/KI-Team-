"""KI-Team für Affiliate-Content auf Instagram und TikTok.

Befehle:
  python main.py create [--dry-run]   Recherche → Skript → Prüfung → Video → Telegram-Freigabe
  python main.py check                Freigaben aus Telegram abholen und veröffentlichen
  python main.py learn                Zahlen holen und Erkenntnisse aktualisieren
  python main.py refresh-ig-token F   Instagram-Token verlängern und in Datei F schreiben
  python main.py telegram-id          Zeigt deine Telegram-Chat-ID (Einrichtung)
  python main.py tiktok-auth          Holt den TikTok-Refresh-Token (Einrichtung, optional)
"""
import json
import os
import sys
import traceback
from datetime import datetime, timedelta
from urllib.parse import quote, unquote

from agents import analyst, carousel, content, publisher, research, reviewer, video
from core import telegram
from core.storage import (OUTPUT, env, load_config, load_learnings, load_posts, load_state, now, now_iso,
                          save_posts, save_state)


def create(dry_run=False):
    cfg = load_config()
    posts = load_posts()
    state = load_state()
    learnings = load_learnings()

    settings = state.setdefault("settings", {})
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and settings.get("pausiert"):
        print("Automatik pausiert (/weiter in Telegram startet sie wieder).")
        return
    wish = (state.get("ideen") or [None])[0]
    goal, fmt = research.next_plan(cfg, posts, settings)
    fmt = os.environ.get("FORCE_FORMAT") or fmt  # Testlauf: Format frei wählbar
    print(f"Ziel: {goal} | Format: {fmt}")
    writer = content.write_carousel if fmt == "karussell" else content.write_script

    signals = research.collect_signals(cfg)
    failed_topics = []
    script, ok, problems = None, False, None
    for attempt in range(3):  # bis zu 3 Themen, je 3 Skript-Versuche
        idea = research.pick_topic(cfg, posts, learnings, goal, fmt, avoid=failed_topics, signals=signals,
                                   wish=wish if attempt == 0 else None)
        print(f"Thema: {idea['topic']} ({idea['angle']})")
        problems = None
        for _ in range(3):
            script = writer(cfg, idea, learnings, feedback="\n".join(problems) if problems else None)
            ok, problems = reviewer.review(cfg, script)
            if ok:
                break
            print("Prüfer hat Probleme gefunden, neuer Versuch:", problems)
        if ok:
            break
        failed_topics.append(idea["topic"])
        print("Thema verworfen, wähle ein neues.")
    if not ok:
        raise RuntimeError(f"Kein Skript hat die Prüfung bestanden: {problems}")

    post_id = now().strftime("%Y%m%d-%H%M")
    workdir = OUTPUT / post_id
    if fmt == "karussell":
        media = carousel.render(cfg, script, workdir)
    else:
        media = video.render(cfg, script, workdir)
    caption_ig = content.build_caption(cfg, script, "instagram")
    caption_tt = content.build_caption(cfg, script, "tiktok")

    if dry_run:
        (workdir / "skript.json").write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Testlauf fertig ({goal}, {fmt}): {media}\n\nHook-Varianten: {script.get('hook_varianten')}\n\n"
              f"Instagram:\n{caption_ig}\n\nTikTok:\n{caption_tt}")
        return

    product = content.product_by_id(cfg, script.get("product_id"))
    label = f"{GOAL_LABELS.get(goal, goal)} · {'Karussell' if fmt == 'karussell' else 'Reel'}"
    if fmt == "karussell":
        video_url = None
        telegram.send_photos(media, f"Neuer Entwurf ({label}): {idea['topic']}")
    else:
        video_url = publisher.upload_video(media)
        telegram.send_video(media, f"Neuer Entwurf ({label}): {idea['topic']}")
    telegram.send_message(
        f"{label}\nThema: {idea['topic']}\nWarum: {idea['why']}\n"
        f"Produkt: {product['name'] if product else 'keins (Mehrwert)'}\n\n"
        f"--- Instagram ---\n{caption_ig}\n\n--- TikTok ---\n{caption_tt}",
        buttons=[[{"text": "✅ Posten", "callback_data": f"ok:{post_id}"},
                  {"text": "❌ Verwerfen", "callback_data": f"no:{post_id}"}]],
    )
    posts.append({
        "id": post_id, "status": "pending", "created_at": now_iso(),
        "goal": goal, "format": fmt,
        "topic": idea["topic"], "angle": idea["angle"], "hook": content.first_line(script),
        "product_id": script.get("product_id"), "script": script,
        "caption_instagram": caption_ig, "caption_tiktok": caption_tt, "video_url": video_url,
    })
    save_posts(posts)
    if wish and state.get("ideen"):
        state["ideen"].pop(0)
    save_state(state)  # verbrauchte Wünsche (/idee, /ziel, /format) entfernen
    print(f"Entwurf {post_id} an Telegram geschickt.")


GOAL_LABELS = {"wachstum": "🚀 Wachstum", "interaktion": "💬 Interaktion", "monetarisierung": "💰 Monetarisierung"}


COMMANDS = [
    ("neu", "Sofort einen neuen Beitrag erstellen"),
    ("idee", "Themenwunsch, z. B. /idee Was ist Digistore24?"),
    ("ziel", "Ziel für den nächsten Beitrag: wachstum, interaktion, monetarisierung"),
    ("format", "Format für den nächsten Beitrag: reel oder karussell"),
    ("ideen", "10 virale Reel- und Karussell-Ideen"),
    ("pause", "Automatische Videos anhalten"),
    ("weiter", "Automatische Videos wieder starten"),
    ("status", "Überblick über deine Videos"),
    ("hilfe", "Alle Befehle anzeigen"),
]


def _trigger_workflow(file_name):
    import requests
    r = requests.post(
        f"https://api.github.com/repos/{env('GITHUB_REPOSITORY')}/actions/workflows/{file_name}/dispatches",
        headers={"Authorization": f"Bearer {env('GITHUB_TOKEN')}", "Accept": "application/vnd.github+json"},
        json={"ref": os.environ.get("GITHUB_REF_NAME", "main")},
        timeout=30,
    )
    r.raise_for_status()


def _handle_command(text, state, posts, cfg):
    cmd, _, arg = text.strip().partition(" ")
    cmd = cmd.lstrip("/").split("@")[0].lower()
    arg = arg.strip()
    settings = state.setdefault("settings", {})

    if cmd == "neu":
        _trigger_workflow("create.yml")
        return "🎬 Alles klar, ich erstelle ein neues Video. Es kommt in ca. 3–5 Minuten."
    if cmd == "idee":
        if not arg:
            return "Schreib dein Thema dahinter, z. B.: /idee Was ist Digistore24?"
        state.setdefault("ideen", []).append(arg)
        return f"💡 Notiert! Kommt beim nächsten Video dran ({len(state['ideen'])} Wunsch/Wünsche in der Warteschlange)."
    if cmd == "ziel":
        goals = cfg["strategie"]["ziel_rotation"]
        choice = arg.lower()
        if choice not in goals:
            return f"Bitte eins davon angeben: {', '.join(goals)}\nz. B. /ziel monetarisierung"
        settings["naechstes_ziel"] = choice
        return f"🎯 Der nächste Beitrag hat das Ziel: {GOAL_LABELS.get(choice, choice)}"
    if cmd == "format":
        choice = arg.lower().replace("carousel", "karussell")
        if choice not in ("reel", "karussell"):
            return "Bitte reel oder karussell angeben, z. B. /format karussell"
        settings["naechstes_format"] = choice
        return f"🖼 Der nächste Beitrag wird ein {'Karussell' if choice == 'karussell' else 'Reel'}."
    if cmd == "ideen":
        ideas = research.generate_ideas(cfg, posts, load_learnings())
        lines = [f"{i}. [{x.get('format', '')} · {x.get('ziel', '')}]\n„{x.get('hook', '')}“\n{x.get('inhalt', '')}"
                 for i, x in enumerate(ideas, 1)]
        return ("💡 10 Ideen für dich\n\n" + "\n\n".join(lines) +
                "\n\nGefällt dir eine? Schick sie mit /idee … und sie kommt als Nächstes dran.")
    if cmd == "pause":
        settings["pausiert"] = True
        return "⏸ Automatische Videos pausiert. Mit /weiter geht's wieder los – /neu funktioniert trotzdem."
    if cmd == "weiter":
        settings["pausiert"] = False
        return "▶️ Läuft wieder – die nächsten Videos kommen um ca. 7 und 16 Uhr."
    if cmd == "status":
        count = lambda s: sum(1 for p in posts if p.get("status") == s)
        goal, fmt = research.next_plan(cfg, posts, dict(settings))
        return (f"📊 Status deines KI-Teams\n\n"
                f"Beiträge gesamt: {len(posts)}\n"
                f"✅ Veröffentlicht: {count('published')}\n"
                f"❌ Verworfen: {count('rejected')}\n"
                f"⏳ Warten auf dich: {count('pending')}\n\n"
                f"Als Nächstes: {GOAL_LABELS.get(goal, goal)} · {'Karussell' if fmt == 'karussell' else 'Reel'}\n"
                f"Automatik: {'⏸ pausiert' if settings.get('pausiert') else '▶️ aktiv'}\n"
                f"Themenwünsche in der Warteschlange: {len(state.get('ideen', []))}")
    return "🤖 Das kann ich:\n\n" + "\n".join(f"/{c} – {d}" for c, d in COMMANDS)


def _publish(cfg, p):
    plats = cfg["plattformen"]
    if p.get("format") == "karussell":
        # Karussells werden immer selbst gepostet (Bilder liegen oben im Chat)
        if plats["instagram"]["aktiv"]:
            telegram.send_message("📸 Instagram-Karussell: Speichere die Bilder oben und poste sie zusammen "
                                  "als Beitrag (+ → Beitrag → mehrere auswählen, in der richtigen Reihenfolge).\n\n"
                                  f"Caption zum Kopieren:\n{p['caption_instagram']}")
        if plats["tiktok"]["aktiv"]:
            telegram.send_message("🎵 TikTok-Fotopost: + → Hochladen → Fotos → alle Bilder auswählen. "
                                  "Bei Werbung 'Werbeinhalt' anschalten.\n\n"
                                  f"Caption zum Kopieren:\n{p['caption_tiktok']}")
        p["status"], p["published_at"] = "published", now_iso()
        return
    if plats["instagram"]["aktiv"] and plats["instagram"].get("modus") == "telegram" and not p.get("ig_done"):
        telegram.send_message("📸 Instagram: Speichere das Video oben und lade es als Reel hoch. "
                              "Bei Videos mit Produkt die erste Zeile 'Werbung' drin lassen.\n\n"
                              f"Caption zum Kopieren:\n{p['caption_instagram']}")
        p["ig_done"] = True
    elif plats["instagram"]["aktiv"] and not p.get("ig_media_id"):
        p["ig_media_id"], p["ig_link"] = publisher.instagram_publish_reel(cfg, p["video_url"], p["caption_instagram"])
        telegram.send_message(f"📸 Auf Instagram veröffentlicht: {p['ig_link']}")

    if plats["tiktok"]["aktiv"] and not p.get("tiktok_done"):
        if plats["tiktok"]["modus"] == "entwurf":
            file = publisher.download_video(p["video_url"], OUTPUT / p["id"] / "final.mp4")
            publisher.tiktok_upload_draft(file)
            telegram.send_message("🎵 TikTok: Video liegt als Entwurf in deiner App (Posteingang). "
                                  "Öffnen, ggf. 'Werbeinhalt' + 'KI-generiert' anschalten, posten.\n\n"
                                  f"Caption zum Kopieren:\n{p['caption_tiktok']}")
        else:
            telegram.send_message("🎵 TikTok: Speichere das Video oben und lade es in TikTok hoch. "
                                  "Bei Werbung 'Werbeinhalt' anschalten, außerdem 'KI-generiert'.\n\n"
                                  f"Caption zum Kopieren:\n{p['caption_tiktok']}")
        p["tiktok_done"] = True

    p["status"], p["published_at"] = "published", now_iso()


def check():
    cfg = load_config()
    posts = load_posts()
    state = load_state()
    by_id = {p["id"]: p for p in posts}
    my_chat = str(telegram.chat_id())

    if state.get("commands_version") != len(COMMANDS):
        telegram.set_commands(COMMANDS)
        state["commands_version"] = len(COMMANDS)

    for upd in telegram.get_updates(state["telegram_offset"] + 1):
        state["telegram_offset"] = upd["update_id"]
        msg = upd.get("message") or {}
        if str(msg.get("chat", {}).get("id")) == my_chat and msg.get("text", "").startswith("/"):
            try:
                reply = _handle_command(msg["text"], state, posts, cfg)
            except Exception as e:
                reply = f"⚠️ Befehl fehlgeschlagen: {str(e)[:300]}"
            telegram.send_message(reply)
            continue
        cb = upd.get("callback_query")
        if not cb or str(cb["from"]["id"]) != my_chat:
            continue  # nur deine eigenen Klicks zählen
        action, _, post_id = cb.get("data", "").partition(":")
        p = by_id.get(post_id)
        if not p or p["status"] != "pending":
            telegram.answer_callback(cb["id"], "Schon erledigt")
            continue
        p["status"] = "approved" if action == "ok" else "rejected"
        p["decided_at"] = now_iso()
        telegram.answer_callback(cb["id"], "Wird veröffentlicht ✅" if action == "ok" else "Verworfen – ich lerne daraus")
        msg = cb.get("message") or {}
        if msg:
            telegram.remove_buttons(msg["chat"]["id"], msg["message_id"])

    for p in posts:
        if p["status"] == "approved":
            try:
                _publish(cfg, p)
            except Exception as e:
                p["attempts"] = p.get("attempts", 0) + 1
                if p["attempts"] >= 3:
                    p["status"] = "error"
                telegram.send_message(f"⚠️ Veröffentlichen von {p['id']} fehlgeschlagen "
                                      f"(Versuch {p['attempts']}/3): {e}")
                traceback.print_exc()
        elif p["status"] == "pending" and now() - datetime.fromisoformat(p["created_at"]) > timedelta(hours=36):
            p["status"] = "expired"

    save_state(state)
    save_posts(posts)


def learn():
    cfg = load_config()
    posts = load_posts()
    ig = cfg["plattformen"]["instagram"]
    if ig["aktiv"] and ig.get("modus") != "telegram":
        print(f"Zahlen für {analyst.collect_metrics(cfg, posts)} Videos aktualisiert")
    save_posts(posts)
    text = analyst.update_learnings(cfg, posts)
    if text and now().weekday() == 6:  # sonntags Wochenbericht
        telegram.send_message(f"📊 Wochenbericht deines KI-Teams\n\n{text}")


def refresh_ig_token(out_file):
    token = publisher.instagram_refresh_token(load_config())
    if not token:
        print("Facebook-Login: Seiten-Token läuft nicht ab, keine Verlängerung nötig.")
        return
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(token)
    print("Instagram-Token verlängert.")


def telegram_id():
    for upd in telegram.get_updates(0):
        chat = (upd.get("message") or {}).get("chat")
        if chat:
            print(f"Deine TELEGRAM_CHAT_ID: {chat['id']}")
            return
    print("Keine Nachricht gefunden. Schreib deinem Bot zuerst 'hallo' in Telegram und starte dann erneut.")


def tiktok_auth():
    import requests
    key, secret = env("TIKTOK_CLIENT_KEY"), env("TIKTOK_CLIENT_SECRET")
    redirect = env("TIKTOK_REDIRECT_URI")
    print("1) Öffne diesen Link im Browser und erlaube den Zugriff:\n")
    print(f"https://www.tiktok.com/v2/auth/authorize/?client_key={key}&scope=video.upload"
          f"&response_type=code&redirect_uri={quote(redirect, safe='')}&state=kiteam\n")
    url = input("2) Füge hier die komplette Adresse ein, auf die du weitergeleitet wurdest: ").strip()
    code = unquote(url.split("code=")[1].split("&")[0])
    data = requests.post("https://open.tiktokapis.com/v2/oauth/token/", data={
        "client_key": key, "client_secret": secret, "code": code,
        "grant_type": "authorization_code", "redirect_uri": redirect}, timeout=30).json()
    print("\nTIKTOK_REFRESH_TOKEN (als GitHub-Secret speichern, 1 Jahr gültig):\n", data.get("refresh_token", data))


def _run_job(name, fn):
    """Bei Fehlern bekommst du eine Telegram-Nachricht statt still zu scheitern."""
    try:
        fn()
    except Exception as e:
        try:
            telegram.send_message(f"⚠️ KI-Team: '{name}' ist fehlgeschlagen: {str(e)[:500]}")
        except Exception:
            pass
        raise


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "create":
        dry = "--dry-run" in sys.argv
        create(dry) if dry else _run_job("Video erstellen", create)
    elif cmd == "check":
        _run_job("Freigaben prüfen", check)
    elif cmd == "learn":
        _run_job("Lernen", learn)
    elif cmd == "refresh-ig-token":
        refresh_ig_token(sys.argv[2])
    elif cmd == "telegram-id":
        telegram_id()
    elif cmd == "tiktok-auth":
        tiktok_auth()
    else:
        print(__doc__)

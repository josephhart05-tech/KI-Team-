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
import sys
import traceback
from datetime import datetime, timedelta
from urllib.parse import quote, unquote

from agents import analyst, content, publisher, research, reviewer, video
from core import telegram
from core.storage import (OUTPUT, env, load_config, load_learnings, load_posts, load_state, now, now_iso,
                          save_posts, save_state)


def create(dry_run=False):
    cfg = load_config()
    posts = load_posts()
    learnings = load_learnings()

    idea = research.pick_topic(cfg, posts, learnings)
    print(f"Thema: {idea['topic']} ({idea['angle']})")

    script, problems = None, None
    for _ in range(3):
        script = content.write_script(cfg, idea, learnings, feedback="\n".join(problems) if problems else None)
        ok, problems = reviewer.review(cfg, script)
        if ok:
            break
        print("Prüfer hat Probleme gefunden, neuer Versuch:", problems)
    else:
        raise RuntimeError(f"Kein Skript hat die Prüfung bestanden: {problems}")

    post_id = now().strftime("%Y%m%d-%H%M")
    path = video.render(cfg, script, OUTPUT / post_id)
    caption_ig = content.build_caption(cfg, script, "instagram")
    caption_tt = content.build_caption(cfg, script, "tiktok")

    if dry_run:
        (OUTPUT / post_id / "skript.json").write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Testlauf fertig: {path}\n\nInstagram:\n{caption_ig}\n\nTikTok:\n{caption_tt}")
        return

    video_url = publisher.upload_video(path)
    product = content.product_by_id(cfg, script.get("product_id"))
    telegram.send_video(path, f"Neuer Entwurf: {idea['topic']}")
    telegram.send_message(
        f"Thema: {idea['topic']}\nWarum: {idea['why']}\n"
        f"Produkt: {product['name'] if product else 'keins (Mehrwert-Video)'}\n\n"
        f"--- Instagram ---\n{caption_ig}\n\n--- TikTok ---\n{caption_tt}",
        buttons=[[{"text": "✅ Posten", "callback_data": f"ok:{post_id}"},
                  {"text": "❌ Verwerfen", "callback_data": f"no:{post_id}"}]],
    )
    posts.append({
        "id": post_id, "status": "pending", "created_at": now_iso(),
        "topic": idea["topic"], "angle": idea["angle"], "hook": script["scenes"][0]["text"],
        "product_id": script.get("product_id"), "script": script,
        "caption_instagram": caption_ig, "caption_tiktok": caption_tt, "video_url": video_url,
    })
    save_posts(posts)
    print(f"Entwurf {post_id} an Telegram geschickt.")


def _publish(cfg, p):
    plats = cfg["plattformen"]
    if plats["instagram"]["aktiv"] and not p.get("ig_media_id"):
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

    for upd in telegram.get_updates(state["telegram_offset"] + 1):
        state["telegram_offset"] = upd["update_id"]
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
    if cfg["plattformen"]["instagram"]["aktiv"]:
        print(f"Zahlen für {analyst.collect_metrics(cfg, posts)} Videos aktualisiert")
    save_posts(posts)
    text = analyst.update_learnings(cfg, posts)
    if text and now().weekday() == 6:  # sonntags Wochenbericht
        telegram.send_message(f"📊 Wochenbericht deines KI-Teams\n\n{text}")


def refresh_ig_token(out_file):
    token = publisher.instagram_refresh_token(load_config())
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

"""Telegram-Bot: schickt dir Videos zur Freigabe und empfängt deine Antworten."""
import requests

from core.storage import env


def _api(method, **kwargs):
    token = env("TELEGRAM_BOT_TOKEN")
    r = requests.post(f"https://api.telegram.org/bot{token}/{method}", timeout=120, **kwargs)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram-Fehler bei {method}: {data.get('description')}")
    return data["result"]


def chat_id():
    return env("TELEGRAM_CHAT_ID")


def send_message(text, buttons=None):
    payload = {"chat_id": chat_id(), "text": text[:4000], "disable_web_page_preview": True}
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}
    return _api("sendMessage", json=payload)


def send_video(path, caption=""):
    with open(path, "rb") as f:
        return _api(
            "sendVideo",
            data={"chat_id": chat_id(), "caption": caption[:1000], "supports_streaming": "true"},
            files={"video": f},
        )


def send_photos(paths, caption=""):
    """Schickt bis zu 10 Bilder als ein Album (für Karussells)."""
    import json
    files, media = {}, []
    for i, path in enumerate(paths[:10]):
        files[f"f{i}"] = open(path, "rb")
        media.append({"type": "photo", "media": f"attach://f{i}", **({"caption": caption[:1000]} if i == 0 else {})})
    try:
        return _api("sendMediaGroup", data={"chat_id": chat_id(), "media": json.dumps(media)}, files=files)
    finally:
        for f in files.values():
            f.close()


def get_updates(offset):
    return _api("getUpdates", json={"offset": offset, "timeout": 0, "allowed_updates": ["callback_query", "message"]})


def set_commands(commands):
    """Zeigt die Befehle im Telegram-Menü (/) an."""
    _api("setMyCommands", json={"commands": [{"command": c, "description": d} for c, d in commands]})


def answer_callback(callback_id, text):
    try:
        _api("answerCallbackQuery", json={"callback_query_id": callback_id, "text": text})
    except RuntimeError:
        pass  # Antwort kam zu spät (älter als ein paar Minuten) – unkritisch


def remove_buttons(message_chat_id, message_id):
    try:
        _api("editMessageReplyMarkup", json={
            "chat_id": message_chat_id,
            "message_id": message_id,
            "reply_markup": {"inline_keyboard": []},
        })
    except RuntimeError:
        pass

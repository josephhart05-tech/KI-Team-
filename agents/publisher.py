"""Publisher-Agent: Video-Hosting (Cloudinary), Instagram-Reels und TikTok-Entwürfe."""
import hashlib
import time
from pathlib import Path

import requests

from core.storage import env


# ---------- Cloudinary: Instagram braucht eine öffentliche Video-URL ----------

def upload_video(path):
    cloud = env("CLOUDINARY_CLOUD_NAME")
    api_key = env("CLOUDINARY_API_KEY")
    secret = env("CLOUDINARY_API_SECRET")
    ts = str(int(time.time()))
    params = f"folder=ki-team&timestamp={ts}"
    signature = hashlib.sha1((params + secret).encode()).hexdigest()
    with open(path, "rb") as f:
        r = requests.post(
            f"https://api.cloudinary.com/v1_1/{cloud}/video/upload",
            data={"api_key": api_key, "timestamp": ts, "folder": "ki-team", "signature": signature},
            files={"file": f},
            timeout=300,
        )
    r.raise_for_status()
    return r.json()["secure_url"]


def download_video(url, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for block in r.iter_content(1 << 20):
                f.write(block)
    return path


# ---------- Instagram (Instagram API mit Instagram-Login) ----------

def _ig_base(cfg):
    ig = cfg["plattformen"]["instagram"]
    # "facebook" = Instagram-API über Facebook-Login (Seiten-Token, läuft nicht ab)
    host = "graph.facebook.com" if ig.get("login") == "facebook" else "graph.instagram.com"
    return f"https://{host}/{ig['api_version']}"


def _ig_check(r):
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"Instagram-Fehler: {data['error'].get('message')}")
    return data


def instagram_publish_reel(cfg, video_url, caption):
    base, token, uid = _ig_base(cfg), env("IG_ACCESS_TOKEN"), env("IG_USER_ID")
    container = _ig_check(requests.post(f"{base}/{uid}/media", data={
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption[:2200],
        "share_to_feed": "true",
        "access_token": token,
    }, timeout=60))["id"]

    for _ in range(40):  # Instagram verarbeitet das Video – bis zu ~7 Minuten warten
        time.sleep(10)
        status = _ig_check(requests.get(f"{base}/{container}", params={
            "fields": "status_code,status", "access_token": token}, timeout=30))
        if status.get("status_code") == "FINISHED":
            break
        if status.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram konnte das Video nicht verarbeiten: {status.get('status')}")
    else:
        raise RuntimeError("Instagram-Verarbeitung dauert zu lange – nächster Versuch beim nächsten Lauf")

    media_id = _ig_check(requests.post(f"{base}/{uid}/media_publish", data={
        "creation_id": container, "access_token": token}, timeout=60))["id"]
    link = _ig_check(requests.get(f"{base}/{media_id}", params={
        "fields": "permalink", "access_token": token}, timeout=30)).get("permalink")
    return media_id, link


def instagram_refresh_token(cfg):
    if cfg["plattformen"]["instagram"].get("login") == "facebook":
        return None  # Seiten-Token läuft nicht ab – nichts zu tun
    r = requests.get("https://graph.instagram.com/refresh_access_token", params={
        "grant_type": "ig_refresh_token", "access_token": env("IG_ACCESS_TOKEN")}, timeout=30)
    return _ig_check(r)["access_token"]


# ---------- TikTok (Content Posting API → Entwurf in deiner App) ----------

def tiktok_access_token():
    r = requests.post("https://open.tiktokapis.com/v2/oauth/token/", data={
        "client_key": env("TIKTOK_CLIENT_KEY"),
        "client_secret": env("TIKTOK_CLIENT_SECRET"),
        "grant_type": "refresh_token",
        "refresh_token": env("TIKTOK_REFRESH_TOKEN"),
    }, timeout=30)
    data = r.json()
    if "access_token" not in data:
        raise RuntimeError(f"TikTok-Login fehlgeschlagen: {data}")
    return data["access_token"]


def tiktok_upload_draft(video_path):
    token = tiktok_access_token()
    size = Path(video_path).stat().st_size
    r = requests.post(
        "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"},
        json={"source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": size, "total_chunk_count": 1}},
        timeout=60,
    )
    data = r.json()
    if data.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(f"TikTok-Fehler: {data['error']}")
    with open(video_path, "rb") as f:
        up = requests.put(data["data"]["upload_url"], data=f.read(), headers={
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{size - 1}/{size}",
        }, timeout=300)
    up.raise_for_status()
    return data["data"]["publish_id"]

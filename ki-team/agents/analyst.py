"""Analyst-Agent: misst den Erfolg jedes Videos und leitet daraus Regeln ab – das ist das 'Lernen'."""
from datetime import datetime, timedelta

import requests

from core import llm
from core.storage import env, now, now_iso, save_learnings

METRIC_SETS = [
    "views,reach,saved,shares,likes,comments,total_interactions",
    "reach,saved,shares,likes,comments",
]


def _ig_insights(cfg, media_id):
    base = f"https://graph.instagram.com/{cfg['plattformen']['instagram']['api_version']}"
    for metrics in METRIC_SETS:
        r = requests.get(f"{base}/{media_id}/insights", params={
            "metric": metrics, "access_token": env("IG_ACCESS_TOKEN")}, timeout=30)
        data = r.json()
        if "data" in data:
            return {m["name"]: m["values"][0]["value"] for m in data["data"] if m.get("values")}
    return None


def score(metrics):
    if not metrics:
        return 0
    views = metrics.get("views") or metrics.get("reach") or 0
    return views + 5 * metrics.get("shares", 0) + 3 * metrics.get("saved", 0) + 2 * metrics.get("comments", 0)


def collect_metrics(cfg, posts):
    cutoff = now() - timedelta(days=30)
    updated = 0
    for p in posts:
        if p.get("status") != "published" or not p.get("ig_media_id"):
            continue
        if datetime.fromisoformat(p["published_at"]) < cutoff:
            continue
        metrics = _ig_insights(cfg, p["ig_media_id"])
        if metrics:
            p["metrics"], p["metrics_at"], p["score"] = metrics, now_iso(), score(metrics)
            updated += 1
    return updated


def update_learnings(cfg, posts):
    measured = [p for p in posts if p.get("metrics")]
    rejected = [p for p in posts if p.get("status") == "rejected"][-15:]
    if len(measured) < 3 and len(rejected) < 3:
        return None  # zu wenig Daten für sinnvolle Schlüsse

    # Videos brauchen ein paar Tage, bis die Zahlen aussagekräftig sind
    rows = []
    for p in sorted(measured, key=lambda x: x.get("score", 0), reverse=True)[:40]:
        rows.append(f"- Score {p['score']} | Thema: {p['topic']} | Hook: {p['hook']} | "
                    f"Werbung: {'ja' if p.get('product_id') else 'nein'} | Zahlen: {p['metrics']}")
    rejected_rows = [f"- Thema: {p['topic']} | Hook: {p['hook']}" for p in rejected]

    prompt = f"""Du bist Social-Media-Analyst. Nische: {cfg['nische']['thema']}.
Hier sind unsere Instagram-Reels, sortiert nach Erfolg (Score = Views + 5×Shares + 3×Saves + 2×Kommentare):
{chr(10).join(rows) or 'noch keine'}

Diese Entwürfe hat der Inhaber ABGELEHNT (daraus lernen, was er nicht will):
{chr(10).join(rejected_rows) or 'keine'}

Leite daraus konkrete, umsetzbare Regeln für künftige Videos ab. Vergleiche die besten mit den schwächsten:
welche Themen, Hook-Arten, Formulierungen, mit/ohne Werbung funktionieren?
Schreibe auf Deutsch als Markdown:
## Was funktioniert
(max. 6 Stichpunkte)
## Was vermeiden
(max. 5 Stichpunkte)
## Themenideen für die nächsten Tage
(5 Stichpunkte)
Nur Regeln, die die Daten wirklich stützen. Kurz und konkret."""

    text = llm.ask(prompt, cfg)
    save_learnings(f"_Zuletzt aktualisiert: {now_iso()} – basierend auf {len(measured)} Videos_\n\n{text}\n")
    return text

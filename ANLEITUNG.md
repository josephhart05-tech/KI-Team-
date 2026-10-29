# Dein KI-Team – Einrichtung Schritt für Schritt

## So sieht dein Tag danach aus

1. **7 Uhr und 16 Uhr:** Das Team recherchiert, schreibt ein Skript, lässt es prüfen und baut ein fertiges Video.
2. **Telegram meldet sich** mit Video und Captions, dazu die Knöpfe **✅ Posten** / **❌ Verwerfen**.
3. **Du tippst auf ✅.** Spätestens 30 Minuten später ist das Reel auf Instagram. Für TikTok bekommst du das Video plus die Caption zum Kopieren und lädst es mit zwei Klicks hoch.
4. **Jeden Abend** holt der Analyst die Zahlen (Views, Shares, Saves, Kommentare) und schreibt neue Regeln in `data/learnings.md`. Auch deine abgelehnten Videos sind ein Signal. Am **Sonntag** bekommst du einen Wochenbericht.

Kosten: **0 €**. Alles läuft über Gratis-Kontingente.

| Agent | Datei | Aufgabe |
|---|---|---|
| Recherche | `agents/research.py` | Google-/YouTube-Suchanfragen, Reddit, wählt das Thema |
| Content | `agents/content.py` | Hook, Skript, Szenen, Captions, Hashtags |
| Prüfer | `agents/reviewer.py` | keine Einkommensversprechen, Länge, Qualität, Werbekennzeichnung |
| Video | `agents/video.py` | KI-Stimme, Stock-Videos, Untertitel → 1080×1920 MP4 |
| Publisher | `agents/publisher.py` | Instagram-Reel, TikTok |
| Analyst | `agents/analyst.py` | misst den Erfolg und leitet daraus Regeln ab |

---

## Schritt 1 – GitHub (hier wohnt dein Team)

1. Auf [github.com](https://github.com) ein Konto anlegen.
2. Oben rechts **+ → New repository**. Name z. B. `ki-team`, **Private** auswählen, dann **Create repository**.
3. Auf der leeren Seite auf **„uploading an existing file“** klicken und den **kompletten Inhalt** des Ordners `ki-team` hineinziehen, also alle Dateien *und* die Ordner `.github`, `agents`, `core` und `data`. Danach **Commit changes**.
   - Wichtig: Der Ordner `.github` muss mit hochgeladen werden, sonst läuft nichts automatisch.
4. Im Repository auf **Settings → Actions → General**, ganz unten bei *Workflow permissions* **„Read and write permissions“** auswählen und speichern.

Geheime Schlüssel trägst du immer hier ein: **Settings → Secrets and variables → Actions → New repository secret**.

## Schritt 2 – Gehirn: Gemini (kostenlos)

1. [aistudio.google.com](https://aistudio.google.com) → **Get API key** → **Create API key**.
2. Als Secret speichern: `GEMINI_API_KEY`

*Optional als Ersatz-Gehirn:* bei [console.groq.com](https://console.groq.com) einen Key erstellen und als `GROQ_API_KEY` speichern. Dann läuft das Team auch weiter, wenn Gemini einmal hakt.

> Hinweis: In der Gratis-Stufe darf Google die Eingaben zur Verbesserung nutzen. Für Social-Media-Skripte ist das unkritisch. Gib dort nur keine privaten Daten ein.

## Schritt 3 – Stock-Videos: Pixabay (kostenlos)

[pixabay.com/api/docs](https://pixabay.com/api/docs/) → Konto anlegen und einloggen → auf der Seite steht bei „Parameters → key“ dein API-Key → Secret `PIXABAY_API_KEY`
(Alternativ geht auch ein Pexels-Key als `PEXELS_API_KEY`, falls Pexels wieder Schlüssel vergibt.)

## Schritt 4 – Video-Hosting: Cloudinary (kostenlos)

Instagram holt Videos nur von einer öffentlichen Adresse ab, deshalb wird das Video kurz bei Cloudinary abgelegt.
[cloudinary.com](https://cloudinary.com) → kostenlos registrieren → im Dashboard stehen drei Werte:
- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`

## Schritt 5 – Telegram (deine Freigabe-Zentrale)

1. In Telegram **@BotFather** öffnen → `/newbot` → Namen vergeben → du bekommst einen **Token**. Secret: `TELEGRAM_BOT_TOKEN`
2. Deinen neuen Bot öffnen und ihm **„hallo“** schreiben.
3. In GitHub: **Actions → „Einrichtung - Telegram-Chat-ID anzeigen“ → Run workflow**. Danach den Lauf anklicken, im Log steht deine ID.
4. Secret: `TELEGRAM_CHAT_ID`

## Schritt 6 – Erster Testlauf (es wird noch nichts gepostet)

**Actions → „0 - Testlauf (ohne Posten)“ → Run workflow.** Nach etwa 3–5 Minuten den Lauf öffnen und unten bei **Artifacts** `testvideo` herunterladen. Dort liegen das Video und das Skript.
Gefällt es dir nicht? Sag mir, was anders sein soll (Stimme, Tempo, Stil), dann passen wir es an.

## Schritt 7 – Instagram verbinden

1. In der Instagram-App: **Einstellungen → Kontotyp und Tools → zu professionellem Konto wechseln** (Creator oder Business, beides kostenlos).
2. [developers.facebook.com](https://developers.facebook.com) → **Meine Apps → App erstellen** → als Anwendungsfall **„Nachrichten und Inhalte auf Instagram verwalten“** wählen (*Instagram API mit Instagram-Login*).
3. Unter **Instagram → API-Einrichtung mit Instagram-Login**: dein Instagram-Konto hinzufügen und **Token generieren**. Diese Berechtigungen müssen dabei sein: `instagram_business_basic`, `instagram_business_content_publish`, `instagram_business_manage_insights`.
   Den Token als Secret `IG_ACCESS_TOKEN` speichern.
   - Weil du nur dein eigenes Konto nutzt, brauchst du **keine App-Prüfung** durch Meta.
4. Deine Instagram-User-ID findest du so: diese Adresse im Browser öffnen (TOKEN durch deinen Token ersetzen):
   `https://graph.instagram.com/v23.0/me?fields=user_id,username&access_token=TOKEN`
   Den Wert bei `user_id` als Secret `IG_USER_ID` speichern.
5. **Token automatisch verlängern** (der Instagram-Token läuft sonst nach 60 Tagen ab):
   GitHub → Profilbild → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.
   Nur dein `ki-team`-Repository auswählen, Berechtigung **Secrets: Read and write**, Ablauf z. B. 1 Jahr.
   Als Secret `GH_PAT` speichern.

## Schritt 8 – TikTok

Ab Werk steht der **Telegram-Modus** an. Du bekommst das Video in Telegram, speicherst es und lädst es in TikTok hoch. Dafür musst du nichts einrichten.

Wenn du möchtest, dass die Videos automatisch als **Entwurf in deiner TikTok-App** landen, braucht es eine TikTok-Entwickler-App. Das richten wir gemeinsam ein, sobald der Rest läuft.

Beim Posten auf TikTok bitte immer anschalten: **„Werbeinhalt“** (bei Videos mit Produkt) und **„KI-generierter Inhalt“**.

## Schritt 9 – Deine Produkte eintragen

In GitHub die Datei `config.yaml` öffnen → Stift-Symbol → bei `produkte:` das Beispiel durch deine echten Affiliate-Produkte ersetzen. Wichtig ist, dass `beschreibung` und `passt_zu` gut ausgefüllt sind, denn danach wählt das Team das passende Produkt aus.
In deine **Instagram- und TikTok-Bio** gehört ein Link-Sammelseite (z. B. Linktree, kostenlos) mit deinen Affiliate-Links.

## Schritt 10 – Live gehen

Ab jetzt läuft alles automatisch. Wenn du sofort starten willst: **Actions → „1 - Video erstellen“ → Run workflow**.

---

## Übersicht aller Secrets

| Secret | Pflicht? | Woher |
|---|---|---|
| `GEMINI_API_KEY` | ja | Schritt 2 |
| `GROQ_API_KEY` | optional | Schritt 2 |
| `PIXABAY_API_KEY` | ja | Schritt 3 |
| `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` | ja | Schritt 4 |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | ja | Schritt 5 |
| `IG_ACCESS_TOKEN`, `IG_USER_ID` | ja | Schritt 7 |
| `GH_PAT` | empfohlen | Schritt 7.5 |
| `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_REFRESH_TOKEN` | nur im Entwurf-Modus | Schritt 8 |

## Gratis-Grenzen

- **GitHub Actions** (privates Repository): 2.000 Minuten pro Monat. Das Team braucht etwa 1.300–1.500.
- **Gemini** Gratis-Stufe: reicht für mehrere Videos pro Tag locker.
- **Cloudinary**: 25 Credits pro Monat. Bei 2 Videos am Tag reicht das. Alte Videos kannst du dort gelegentlich löschen.

## Rechtliches (bitte ernst nehmen)

- **Werbekennzeichnung:** Videos mit Produkt bekommen automatisch „Werbung | enthält Affiliate-Link“ bzw. `#werbung`.
- **Impressum:** Wer in Deutschland geschäftlich auf Social Media auftritt, braucht ein Impressum. Das geht z. B. als Link in der Bio auf deiner Link-Sammelseite.
- **Keine Einkommensversprechen:** Der Prüfer blockt Formulierungen wie „garantiert“ oder „schnell reich“. Die Liste kannst du in `config.yaml` erweitern.
- **Nebenjob:** Kläre, ob dein Arbeitsvertrag eine Nebentätigkeit erlaubt, und melde ein Gewerbe an, falls noch nicht geschehen.

## Anpassen

Alles Wichtige steht in `config.yaml`: Nische, Zielgruppe, Tonalität, Stimme, Tempo, Werbeanteil, verbotene Wörter.
Die Uhrzeiten stehen in `.github/workflows/create.yml` (in UTC, also deutsche Zeit minus 1 bzw. 2 Stunden).

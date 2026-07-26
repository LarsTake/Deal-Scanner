# Einrichtung und Integrationen

## Lokal und Docker

Installiert werden Python 3.12, `uv`, Node.js 24, pnpm 10 und für Desktop-Builds Rust/Cargo.
`uv sync --all-packages --frozen` und `pnpm install --frozen-lockfile` stellen die gesperrten
Abhängigkeiten her. Danach starten `uv run --package deal-scanner-api uvicorn
deal_scanner_api.main:app --reload`, `deal-scanner-scheduler` und `deal-scanner-worker` die drei
Prozesse. `docker compose up --build` verwendet dieselben Verträge und persistente Volumes.
Marktdaten-CSV werden auf der Preis-Seite ausgewählt: Im Browser übernimmt ein beschränktes
Dateifeld den Import, in Tauri ein nativer Dialog. Beide Wege verwenden denselben API-Vertrag.

Die PostgreSQL-/RLS-Abnahme kann auch ohne Docker gegen eine lokale PostgreSQL-17-Laufzeit
ausgeführt werden. Das Skript erzeugt dafür einen kurzlebigen Cluster auf einem freien
Loopback-Port und entfernt ihn nach dem Test wieder:

```powershell
$env:DEAL_SCANNER_POSTGRES_BIN='C:\Pfad\zu\pgsql\bin'
.\infrastructure\scripts\test-postgres-local.ps1 -FullSuite
```

## Supabase

Ein Projekt wird ausschließlich über die SQL-Dateien in
`infrastructure/supabase/migrations` migriert. In Produktion müssen Auth-Modus, Projekt-URL,
JWKS-Audience, PostgreSQL-Verbindung und die eingeschränkte Datenbankrolle gesetzt werden.
Die Publishable-Konfiguration darf in Web/desktop stehen; Service-Role-Key und DB-Passwort nur
im Server-Secret-Store. Die Buckets `listing-images` und `mail-archive` bleiben privat.
Die gepinnte CLI wird mit `pnpm exec supabase --workdir infrastructure <Befehl>` aufgerufen;
`supabase start` und `supabase status` benötigen einen laufenden Docker-kompatiblen Dienst.

Für lokale Passwort-Recovery ist die Site URL `http://127.0.0.1:4200` konfiguriert. Die
Redirect-Allowlist enthält `http://127.0.0.1:4200/login` und `http://localhost:4200/login`.
Die Recovery-Mail verlinkt nicht direkt auf Supabases einmalig nutzbare Confirmation URL,
sondern auf `{{ .RedirectTo }}?token_hash={{ .TokenHash }}&type=recovery`. Dadurch verbrauchen
Mail-Sicherheitsprüfungen den Link nicht vor dem Benutzer. Das Login verifiziert den Token,
zeigt das Formular für das neue Passwort an und meldet die Recovery-Sitzung danach ab.
Für frei gehostete Supabase-Projekte erfordert diese angepasste Mailvorlage einen eigenen
SMTP-Versand; SMTP-Zugangsdaten gehören ausschließlich in Supabase und niemals ins Repository.

Scheduler und Analyse-Worker authentifizieren sich ebenfalls an der API. Im Entwicklungsmodus
kann dafür `DEAL_SCANNER_DEVELOPMENT_USER_ID` verwendet werden. In Produktion ist ein gültiges,
eng begrenztes Benutzer-JWT als `DEAL_SCANNER_API_TOKEN` Pflicht; Prozesse verweigern ohne Token
den Start, statt unbemerkt in einer 401-Retry-Schleife zu laufen.

## eBay

Eine eBay-Developer-Anwendung benötigt Client-ID und Client-Secret. Zuerst wird `sandbox`,
danach ausdrücklich read-only `production` verwendet. Das Server-UI speichert nur die Referenz
auf das Secret, niemals dessen Wert. Marketplace ist standardmäßig `EBAY_DE`. Ohne Credentials
überspringt der Scheduler den Lauf und erzeugt keine erfundenen Marktdaten.

Für einen Production-Keyset muss zusätzlich die **Marketplace Account Deletion**-Benachrichtigung
eingerichtet werden. Graper stellt dafür diesen öffentlichen Handler bereit:

```text
https://<öffentliche-domain>/api/v1/webhooks/ebay/account-deletion
```

Die URL muss über öffentlich erreichbares HTTPS auf Port 443 verfügbar sein; `localhost`, private
IP-Adressen und selbstsignierte Zertifikate akzeptiert eBay nicht. Die produktive Umgebung erhält:

```dotenv
DEAL_SCANNER_EBAY_ENVIRONMENT=production
DEAL_SCANNER_EBAY_PRODUCTION_CLIENT_ID=<Production-App-ID>
DEAL_SCANNER_EBAY_PRODUCTION_CLIENT_SECRET=<Production-Cert-ID>
DEAL_SCANNER_EBAY_DELETION_ENDPOINT_URL=https://<öffentliche-domain>/api/v1/webhooks/ebay/account-deletion
DEAL_SCANNER_EBAY_DELETION_VERIFICATION_TOKEN=<32-80-Zeichen-Token>
```

Die umgebungsspezifischen Werte überschreiben beim Start die generischen eBay-Felder gemeinsam;
dadurch kann ein Production Client ID nicht versehentlich mit dem Sandbox Client Secret kombiniert
werden.

Endpoint-URL und Verification Token werden anschließend exakt identisch im eBay Developer Portal
unter **Alerts & Notifications → Marketplace Account Deletion** eingetragen. Der GET-Aufruf
beantwortet eBays Challenge. POST-Benachrichtigungen werden erst nach Prüfung der
`X-EBAY-SIGNATURE` gegen den über die eBay Notification API geladenen öffentlichen Schlüssel
verarbeitet. Danach löscht Graper Verkäufer, zugehörige Angebote, Snapshots, Auswertungen,
Beobachtungen und private Listing-Bilder irreversibel. Nur die Notification-ID und Löschzähler
bleiben als personenbezugsfreier Wiederholschutz bestehen. Ein ungültig signierter Aufruf erhält
HTTP 412 und verändert keine Daten.

## E-Mail und Browser-Erweiterung

IMAP benötigt Host, Benutzer, Passwort und eine enge Absender-Allowlist. Unbekannte Formate
landen in Quarantäne; Original-EMLs werden archiviert. Die gebaute MV3-Erweiterung liegt unter
`apps/browser-extension/dist` und wird in Chrome/Edge als entpackte Erweiterung geladen. Sie
importiert nur nach Nutzeraktion sichtbare Kleinanzeigen-Daten und verwendet ein kurzlebiges,
widerrufbares Pairing-Token. Nach dem Import zeigt sie auf sichtbaren Karten die vorhandenen
Deal-, Risiko- und Datenqualitätswerte oder den Status **Bereits bekannt** an.

Für die dauerhafte Verbindung zuerst in der Desktop-App mit E-Mail und Passwort anmelden. Unter
**Einstellungen → Dauerhafte Kontoverbindung** wird anschließend ein widerrufbares Geräte-Token
erzeugt. Die API speichert ausschließlich dessen SHA-256-Hash; Passwort, Supabase-Access-Token
und Refresh-Token verlassen die Desktop-App nicht. API-Adresse und Geräte-Token werden einmalig
in der Erweiterung gespeichert und überstehen Browser- und Desktop-Neustarts. Das Token ist nur
für Browser- und Bildimporte gültig und kann in den Einstellungen jederzeit widerrufen werden.

Für die direkte Desktop-Kopplung unter **Einstellungen → Sichere Desktop-Kopplung** eine neue
Kopplung erzeugen und die angezeigte API-Adresse samt Token in der Erweiterung speichern. Tauri
bindet dafür fünf Minuten lang einen zufälligen Port ausschließlich an `127.0.0.1`. Der lokale
Proxy akzeptiert nur Browser- und Bildimport, begrenzt Requests auf 2 MiB, folgt keinen Redirects
und reicht das Supabase-JWT intern an die konfigurierte API weiter. **Widerrufen** beendet den
Listener sofort; spätestens nach fünf Minuten endet er automatisch. Alternativ kann die
Erweiterung weiterhin direkt die Server-API mit einem dort erzeugten Pairing-Token verwenden.

Für einen automatischen Kleinanzeigen-Import wird auf Kleinanzeigen zuerst eine Suche gespeichert
und die E-Mail-Benachrichtigung aktiviert. Das empfangende Postfach wird anschließend in `.env`
eingetragen:

```dotenv
DEAL_SCANNER_IMAP_HOST=imap.example.de
DEAL_SCANNER_IMAP_USERNAME=name@example.de
DEAL_SCANNER_IMAP_PASSWORD=APP_PASSWORT
DEAL_SCANNER_IMAP_ALLOWED_SENDERS=kleinanzeigen.de
DEAL_SCANNER_SCHEDULER_INTERVAL_SECONDS=300
```

Danach muss der Scheduler neu gestartet werden. Er liest alle fünf Minuten ungelesene
Suchbenachrichtigungen, akzeptiert nur freigegebene Absender und übergibt gefundene Anzeigen an
denselben Analyse- und Bewertungsprozess wie Browser- und manuelle Importe. Ein direktes,
permanentes Scraping von Kleinanzeigen ist nicht Teil der Integration.

## Ollama, OCR und Benachrichtigungen

Der lokale Worker verwendet feste Modellrollen: `gemma4:12b` extrahiert Produkte, Komponenten
und Attribute, `gpt-oss:latest` prüft unabhängig Risiken, Widersprüche und fehlende Angaben,
`gemma4:12b` liest sichtbaren Text aus Angebotsbildern und `qwen3-embedding:0.6b` erzeugt
semantische Vektoren für Komponenten- und Angebotsähnlichkeit. Die Zuordnung wird über
`DEAL_SCANNER_OLLAMA_EXTRACTION_MODEL`, `DEAL_SCANNER_OLLAMA_REASONING_MODEL`,
`DEAL_SCANNER_OLLAMA_VISION_MODEL` und `DEAL_SCANNER_OLLAMA_EMBEDDING_MODEL` geändert.
`DEAL_SCANNER_OLLAMA_TEXT_MODEL` bleibt nur als Legacy-Fallback erhalten.

Modellausgaben werden gegen Pydantic-/JSON-Schemata validiert. Bei Vision-Fehlern fällt der
Worker auf Tesseract zurück, wenn dessen Kommando auffindbar ist. Ohne Textmodell bleibt der
Regelpfad funktionsfähig. Desktop ist der Standardkanal; `DEAL_SCANNER_NTFY_URL` aktiviert
optional ntfy.

## ERP und Migration

`POST /api/v1/erp/exports/{listingId}` liefert das stabile Mock-Format `erp-purchase-v1`.
Es enthält Kauf- und Nebenkosten, Verkäuferdaten, erkannte Komponenten, Bildreferenzen mit
Hashes sowie die letzte Marktwert-/Score-Auswertung. Ein echter Adapter ersetzt nur den Port,
nicht die öffentliche Route. Neue Datenbankschemata
werden als weitere, vorwärtsgerichtete Supabase-Migration ergänzt; historische Snapshots,
Analysen und Audit-Ereignisse werden nie überschrieben.

## Fehlerdiagnose

- `/api/v1/health/live` prüft den Prozess, `/health/ready` die Datenbank und `/system/status`
  zeigt Workspace-bezogene Laufzustände.
- `401/403`: JWT-Audience, JWKS-URL, Workspace-Mitgliedschaft und Datenbankrolle prüfen.
- `409`: Idempotenz-, Versions- oder Lease-Konflikt; aktuellen Datensatz laden und erneut anwenden.
- `422`: RFC-9457-Details bzw. KI-Schemaverletzung lesen; fehlerhafte KI-Ausgaben werden verworfen.
- Keine eBay-/IMAP-Daten: Provider aktiviert, Secret-Referenz und Prozess-Umgebung prüfen.
- Desktop-Build: Plattformabhängige Tauri-Voraussetzungen und Signatur-Secrets prüfen.

## Credential-gesteuerte Live-Abnahme

Die externen Prüfungen sind strikt read-only und standardmäßig deaktiviert. Nach dem Setzen der
in `.env.example` aufgeführten Supabase-, eBay-Sandbox-/Produktions-, IMAP- und Ollama-Werte:

```powershell
$env:DEAL_SCANNER_RUN_LIVE_TESTS='1'
uv run pytest tests/live -m live -ra
```

Fehlende Integrationen werden einzeln übersprungen. Die eBay-Prüfungen beziehen ausschließlich
OAuth-Tokens, IMAP führt nur Login/NOOP aus und Ollama/Supabase werden nur über Health-/Tags-Endpunkte gelesen.
`DEAL_SCANNER_SUPABASE_DB_URL` aktiviert zusätzlich die read-only Prüfung der migrierten
Kerntabellen, aktivierten RLS-Flags und privaten Storage-Buckets. Der eBay-Smoke ruft nach OAuth
eine einzelne read-only Browse-Suche mit `limit=1` auf.
`DEAL_SCANNER_RUN_OLLAMA_INFERENCE_TESTS=1` aktiviert zusätzlich einen bewusst separaten,
rechenintensiveren Modellaufruf, dessen Ausgabe gegen den produktiven Pydantic-Vertrag validiert wird.

## Desktop-Signierung und Notarisierung

Der Desktop-Workflow erzeugt ohne Zertifikate weiterhin unsignierte Installationsartefakte. Für
einen signierten und notarisierten Apple-Silicon-Build werden folgende GitHub-Secrets hinterlegt:

- `APPLE_CERTIFICATE`: base64-kodiertes Developer-ID-`.p12`
- `APPLE_CERTIFICATE_PASSWORD` und `KEYCHAIN_PASSWORD`
- `APPLE_ID`, `APPLE_PASSWORD` (app-spezifisch) und `APPLE_TEAM_ID`

Der Workflow importiert das Zertifikat nur, wenn es vorhanden ist. Tauri übernimmt anschließend
Codesign und Notarisierung. Windows-Code-Signing benötigt bewusst eine konkrete Zertifikatswahl
(beispielsweise Azure Artifact Signing oder einen eigenen `signCommand`) und wird erst zusammen
mit den zugehörigen Azure-/Zertifikats-Secrets aktiviert; die unsignierten MSI-/NSIS-Artefakte
bleiben unabhängig davon reproduzierbar.

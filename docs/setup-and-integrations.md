# Einrichtung und Integrationen

## Lokal und Docker

Installiert werden Python 3.12, `uv`, Node.js 24, pnpm 10 und für Desktop-Builds Rust/Cargo.
`uv sync --all-packages --frozen` und `pnpm install --frozen-lockfile` stellen die gesperrten
Abhängigkeiten her. Danach starten `uv run --package deal-scanner-api uvicorn
deal_scanner_api.main:app --reload`, `deal-scanner-scheduler` und `deal-scanner-worker` die drei
Prozesse. `docker compose up --build` verwendet dieselben Verträge und persistente Volumes.

## Supabase

Ein Projekt wird ausschließlich über die SQL-Dateien in
`infrastructure/supabase/migrations` migriert. In Produktion müssen Auth-Modus, Projekt-URL,
JWKS-Audience, PostgreSQL-Verbindung und die eingeschränkte Datenbankrolle gesetzt werden.
Die Publishable-Konfiguration darf in Web/desktop stehen; Service-Role-Key und DB-Passwort nur
im Server-Secret-Store. Die Buckets `listing-images` und `raw-emails` bleiben privat.

## eBay

Eine eBay-Developer-Anwendung benötigt Client-ID und Client-Secret. Zuerst wird `sandbox`,
danach ausdrücklich read-only `production` verwendet. Das Server-UI speichert nur die Referenz
auf das Secret, niemals dessen Wert. Marketplace ist standardmäßig `EBAY_DE`. Ohne Credentials
überspringt der Scheduler den Lauf und erzeugt keine erfundenen Marktdaten.

## E-Mail und Browser-Erweiterung

IMAP benötigt Host, Benutzer, Passwort und eine enge Absender-Allowlist. Unbekannte Formate
landen in Quarantäne; Original-EMLs werden archiviert. Die gebaute MV3-Erweiterung liegt unter
`apps/browser-extension/dist` und wird in Chrome/Edge als entpackte Erweiterung geladen. Sie
importiert nur nach Nutzeraktion sichtbare Kleinanzeigen-Daten und verwendet ein kurzlebiges,
widerrufbares Pairing-Token.

## Ollama, OCR und Benachrichtigungen

`DEAL_SCANNER_OLLAMA_TEXT_MODEL` aktiviert strukturierte Textanalyse; leere Konfiguration lässt
den Regelpfad vollständig funktionsfähig. Modellausgaben werden gegen
`schemas/ai/v1/text-analysis.schema.json` validiert. Tesseract aktiviert OCR, wenn das Kommando
auffindbar ist. Desktop ist der Standardkanal; `DEAL_SCANNER_NTFY_URL` aktiviert optional ntfy.

## ERP und Migration

`POST /api/v1/erp/exports/{listingId}` liefert das stabile Mock-Format `erp-purchase-v1`.
Ein echter Adapter ersetzt nur den Port, nicht die öffentliche Route. Neue Datenbankschemata
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

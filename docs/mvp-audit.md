# MVP-Abdeckungsmatrix

Diese Matrix ordnet jeden verbindlichen Punkt aus Abschnitt 33 des Lastenhefts einem
Implementierungs- und Prüfnachweis zu. Ein grüner lokaler Nachweis ersetzt nicht die in
`acceptance.md` aufgeführten, credential-abhängigen Live-Smoke-Tests.

| Nr. | MVP-Anforderung | Implementierungsnachweis | Prüfnachweis | Status |
|---:|---|---|---|---|
| 1 | Angular-Tauri-Desktop-App | `apps/desktop`, Browserbetrieb und Tauri-Shell | Angular-Test/Build, Cargo-Check, native CI-Builds | lokal erfüllt |
| 2 | FastAPI-Backend | versionierte REST-API unter `/api/v1`, RFC-9457-Fehler | API- und Schema-Tests | lokal erfüllt |
| 3 | Supabase-Schema/Migrationen | einzige SQL-Migrationsquelle unter `infrastructure/supabase/migrations` | Migration und RLS gegen PostgreSQL 17 in CI | lokal geprüft, CI konfiguriert |
| 4 | Docker Compose | API, Scheduler und Regel-Worker mit Healthchecks und Limits | Compose-Konfigurationsprüfung, Multi-Arch-CI | CI konfiguriert; Docker-Lauf extern offen |
| 5 | Suchaufträge | vollständiges CRUD, Filter, Intervalle und Schwellenwerte | API-Flow und Angular-Build | lokal erfüllt |
| 6 | eBay-Provider | Browse API, OAuth, `EBAY_DE`, Delta-Fenster, Deduplizierung und Backoff | Provider-Mocks; Sandbox/Produktion extern | lokal erfüllt, live offen |
| 7 | Manueller Link-Import | URL-/Payload-Import mit Idempotenz und offizieller eBay-Auflösung | API-Deduplizierungs- und Historientests | lokal erfüllt |
| 8 | Kleinanzeigen-Erweiterung | Manifest V3, sichtbare Karten/Detaildaten und widerrufbares Pairing | DOM-Fixtures, Extension-Build, Pairing-API-Test | lokal erfüllt |
| 9 | E-Mail-Importer | Absenderprüfung, versionierter Parser, Archiv, Retry und Quarantäne | Mail-Fixtures; IMAP-Verbindung extern | lokal erfüllt, live offen |
| 10 | Regelbasierte Produkterkennung | Regeln, Aliase, Normalisierung und Fuzzy Matching vor KI | RTX/QR/DJI/ELRS-Normalisierungstests | lokal erfüllt |
| 11 | Lokaler Ollama-Provider | typisierter AI-Port, Modell- und Health-Vertrag | Adapter-/Schema-Tests; Modelllauf extern | lokal erfüllt, live offen |
| 12 | Strukturierte Textanalyse | versioniertes Pydantic-/JSON-Schema mit Evidenz und Konfidenz | ungültige Modellausgabe wird verworfen | lokal erfüllt |
| 13 | Kategorieprofile | versionierte YAML-Profile für PC, Simracing, FPV und allgemein | Build-Validierung und Extraktionstests | lokal erfüllt |
| 14 | Risiko-Score | evidenzbasierte, versionierte Signale; fehlende Daten neutral | Risiko- und Worker-Ergebnistests | lokal erfüllt |
| 15 | Deal-Score | Preisvorteil, Qualität, Zustand, Vollständigkeit, Wiederverkauf und Relevanz | Scoring- und API-Flow-Tests | lokal erfüllt |
| 16 | Marktwertdatenmodell | Beobachtungen, gewichtete Quantile, MAD, Zeitgewicht und Qualitätsgrenzen | Marktwert-/Ausreißer-/Mindestmengen-Tests | lokal erfüllt |
| 17 | Worker/Job-Leasing | Registrierung, Heartbeat, atomarer Claim, Renew, Retry und Dead-Letter | Lifecycle- und konkurrierender `SKIP LOCKED`-Test | lokal geprüft, PostgreSQL-CI konfiguriert |
| 18 | Manuelle Produktkorrektur | append-only Feedback, neue Analyseversion und Konfliktprüfung | Korrektur-, Historien- und Offline-Konflikttest | lokal erfüllt |
| 19 | Dashboard/Übersicht | Dashboard, Karten, Filter, Detail, Verlauf, Vergleiche und Systemstatus | Angular-Test, Typecheck und Build | lokal erfüllt |
| 20 | Kernfunktionstests | Unit-, API-, Provider-, Parser-, DB-, Schema-, Extension- und Build-Tests | lokale Prüfkette und CI-Workflows | lokal geprüft, CI konfiguriert |

Zusätzliche Plananforderungen wie private Bildablage, SHA-256/pHash, OCR-Vertrag,
Desktop-Benachrichtigungen, ntfy-Adapter, ERP-Mock, Offline-Outbox, OpenAPI-generierter Client,
strukturierte Logs, Secret-Scan und Audit-Ereignisse sind ebenfalls implementiert. Die genaue
Trennung zwischen lokal reproduzierbarer Abnahme und externen Voraussetzungen steht in
`acceptance.md`.

# Deal Scanner

Deal Scanner erfasst Angebote über klar abgegrenzte Provider, archiviert Rohdaten als
unveränderliche Snapshots und erzeugt nachvollziehbare Marktwert-, Deal- und Risikoauswertungen.
Die Anwendung läuft als Angular-Weboberfläche und als Tauri-Desktop-App; API, Scheduler und
Analyse-Worker sind getrennte Python-Prozesse.

## Schnellstart

Voraussetzungen: Python 3.12, `uv`, Node.js 24, `pnpm` 10. Für Tauri zusätzlich Rust und die
plattformabhängigen Tauri-Systembibliotheken; für den Serverbetrieb Docker.

```powershell
Copy-Item .env.example .env
uv sync --all-packages
pnpm install
uv run --package deal-scanner-api uvicorn deal_scanner_api.main:app --reload
pnpm --filter @deal-scanner/desktop start
```

Ohne Supabase-Konfiguration startet die API bewusst im Entwicklungsmodus mit SQLite und einem
lokalen Testnutzer. Produktionsbetrieb verweigert diesen Auth-Modus.

## Qualitätsprüfungen

```powershell
uv run pytest
uv run ruff check .
uv run mypy packages/python apps/server-api apps/scheduler apps/analysis-worker providers
pnpm typecheck
pnpm build
```

Ein nativer Windows-Release wird mit
`pnpm --filter @deal-scanner/desktop tauri build` erzeugt. Die Installer liegen anschließend
unter `apps/desktop/src-tauri/target/release/bundle`.

Die Architektur, Sicherheitsgrenzen und Live-Konfiguration sind in [docs/architecture.md](docs/architecture.md)
und [docs/security.md](docs/security.md) beschrieben. Die klare Trennung zwischen lokal
verifizierter Abnahme und credential-abhängigen Live-Smokes steht in
[docs/acceptance.md](docs/acceptance.md).

Provider-, Supabase-, Worker-, ERP- und Erweiterungs-Setup samt Fehlerdiagnose steht in
[docs/setup-and-integrations.md](docs/setup-and-integrations.md). Die Abdeckung des vollständigen
MVP ist in [docs/mvp-audit.md](docs/mvp-audit.md) den Implementierungs- und Testnachweisen zugeordnet.

Das fachliche Datenmodell und der HTTP-Vertrag sind in
[docs/data-model-and-api.md](docs/data-model-and-api.md) zusammengefasst. Wie weitere Kategorien,
Provider, Analysemodelle und Adapter ergänzt werden, beschreibt [docs/extending.md](docs/extending.md).

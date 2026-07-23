# Deal Scanner

Deal Scanner erfasst Angebote über klar abgegrenzte Provider, archiviert Rohdaten als
unveränderliche Snapshots und erzeugt nachvollziehbare Marktwert-, Deal- und Risikoauswertungen.
Die Anwendung läuft als Angular-Weboberfläche und als Tauri-Desktop-App; API, Scheduler und
Analyse-Worker sind getrennte Python-Prozesse.

## Schnellstart

Voraussetzungen: Python 3.12, `uv`, Node.js 24, `pnpm` 10. Die Supabase-CLI ist als exakt
gepinntes Workspace-Werkzeug enthalten. Für Tauri werden zusätzlich Rust und die
plattformabhängigen Tauri-Systembibliotheken benötigt; für den Serverbetrieb Docker.

macOS:

```bash
cp .env.example .env
./infrastructure/scripts/start-local.sh --install
```

Falls Werkzeuge fehlen, installiert Homebrew die macOS-Voraussetzungen:

```bash
brew install uv rustup
rustup default stable
corepack enable
```

Windows:

```powershell
Copy-Item .env.example .env
.\infrastructure\scripts\start-local.ps1 -Install
```

Der Startbefehl prüft API und Oberfläche und startet zusätzlich Scheduler sowie Analyse-Worker,
damit importierte Angebote nicht in der Warteschlange liegen bleiben. Unter `cmd.exe` lautet der
erste Befehl `copy .env.example .env`; das Startskript wird dort mit
`%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe -ExecutionPolicy Bypass -File infrastructure\scripts\start-local.ps1 -Install`
aufgerufen. Bei späteren Starts kann `--install` beziehungsweise `-Install` entfallen.

Ohne Supabase-Konfiguration startet die API bewusst im Entwicklungsmodus mit SQLite und einem
lokalen Testnutzer. Produktionsbetrieb verweigert diesen Auth-Modus.

## Qualitätsprüfungen

```powershell
uv run pytest
uv run ruff check .
uv run mypy packages/python apps/server-api apps/scheduler apps/analysis-worker providers
pnpm typecheck
pnpm test
pnpm build
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml --lib
```

Mit einer lokalen PostgreSQL-17-Laufzeit führt
`infrastructure/scripts/test-postgres-local.ps1 -FullSuite` zusätzlich alle Migrationen,
Workspace-/Storage-RLS und den konkurrierenden Job-Claim in einem kurzlebigen Testcluster aus.

Ein nativer macOS- oder Windows-Release wird mit
`pnpm --filter @deal-scanner/desktop tauri build` erzeugt. Die Installer liegen anschließend
unter `apps/desktop/src-tauri/target/release/bundle`.

Die Architektur, Sicherheitsgrenzen und Live-Konfiguration sind in [docs/architecture.md](docs/architecture.md)
und [docs/security.md](docs/security.md) beschrieben. Die klare Trennung zwischen lokal
verifizierter Abnahme und credential-abhängigen Live-Smokes steht in
[docs/acceptance.md](docs/acceptance.md).

Provider-, Supabase-, Worker-, ERP- und Erweiterungs-Setup samt Fehlerdiagnose steht in
[docs/setup-and-integrations.md](docs/setup-and-integrations.md). Die Abdeckung des vollständigen
MVP ist in [docs/mvp-audit.md](docs/mvp-audit.md) den Implementierungs- und Testnachweisen zugeordnet.
Geplante Erweiterungen für Cloudflare und komponentenbezogene Marktpreis-Referenzen stehen in
[docs/roadmap.md](docs/roadmap.md).

Das fachliche Datenmodell und der HTTP-Vertrag sind in
[docs/data-model-and-api.md](docs/data-model-and-api.md) zusammengefasst. Wie weitere Kategorien,
Provider, Analysemodelle und Adapter ergänzt werden, beschreibt [docs/extending.md](docs/extending.md).

# Betrieb

Die API wendet zuerst die Supabase-Migrationen an und startet danach ohne automatische
Schemaerzeugung. `docker compose up --build` startet API und Scheduler. Der lokale
Ollama-Worker wird mit `docker compose --profile analysis up --build` ergänzt; TLS mit
`--profile tls`.

Produktiv müssen `DEAL_SCANNER_ENVIRONMENT=production`, `DEAL_SCANNER_AUTH_MODE=supabase`,
Supabase-JWKS/DB-Zugang und ein Scheduler-Service-Token gesetzt sein. eBay-Zugangsdaten,
IMAP-Passwort und Ollama-Modell sind optionale, getrennte Secrets. Service-Schlüssel werden
nie an Web-, Desktop- oder Extension-Bundles übergeben.

Der Container-Workflow baut API, Scheduler und Worker für `linux/amd64` und `linux/arm64`.
Desktop-Artefakte werden auf den jeweiligen nativen GitHub-Runnern erzeugt. Signierung wird
nur aktiviert, wenn die zugehörigen Repository-Secrets vorhanden sind.

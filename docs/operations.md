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

## Sicherung und Wiederherstellung

Die PostgreSQL-Datenbank wird mit einem Custom-Format-Dump gesichert. Das Skript übergibt die
Verbindungsdaten nur über die Prozessumgebung, validiert das Archiv anschließend mit `pg_restore`
und hält das lokale Sicherungsverzeichnis über `.gitignore` aus der Versionskontrolle heraus:

```powershell
$env:DEAL_SCANNER_SUPABASE_DB_URL='postgresql://...'
.\infrastructure\scripts\backup-postgres.ps1
```

Eine Wiederherstellung wird zunächst in eine leere Prüf-Datenbank eingespielt und dort mit den
RLS- und Smoke-Tests validiert:

```powershell
$env:PGDATABASE='postgresql://.../deal_scanner_restore_test'
pg_restore --clean --if-exists --no-owner --no-privileges .\.backups\deal-scanner-<Zeitstempel>.dump
```

Backups müssen außerhalb des Mini-Servers verschlüsselt und nach einer festgelegten Aufbewahrung
gespeichert werden. PostgreSQL-Dumps enthalten die Storage-Metadaten, nicht jedoch die Binärdaten
privater Supabase-Buckets; `listing-images` und `mail-archive` benötigen deshalb zusätzlich eine
versionierte Storage-Sicherung beim eingesetzten Supabase-Anbieter. Wiederherstellungstests sind
regelmäßig gegen ein separates Projekt auszuführen, niemals direkt gegen Produktion.

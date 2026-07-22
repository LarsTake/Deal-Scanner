# Abnahme und externe Voraussetzungen

## Lokal reproduzierbar

- API-Flow für Workspace, Suchprofil, unveränderliche Snapshots, Feedback, Jobs, Marktwert,
  getrennte Deal-/Risikoauswertung, Benachrichtigung und Extension-Pairing.
- Regel-Normalisierung für RTX 4070 Super/4070S, QR1/QR2, DJI O3/Vista und ELRS sowie
  evidenzbasierte Risikosignale.
- Gewichtete Marktdaten, MAD-Filter, Mindestdatenmenge und Qualitätsgrenze für ausschließlich
  aktive Angebote.
- Job-Claim mit `SKIP LOCKED`, Lease/Renew, drei Versuchen, Backoff, Dead-Letter und
  Schema-Validierung der Ollama-Ausgabe.
- Angular-Webbuild, Tauri-Rust- und Loopback-Proxytests, Manifest-V3-Extension, OpenAPI-Vertrag
  und generierte TypeScript-Typen.
- SQLite-Desktopcache, idempotente Outbox, sichtbare Konflikte, Stronghold-Sitzungsspeicher
  und native Desktop-Benachrichtigung.
- Private Bildablage mit Domain-Allowlist, MIME-/Größenprüfung, SHA-256/pHash-Dubletten,
  kurzlebigem Zugriff und einem real ausführbaren Tesseract-OCR-Worker.
- PostgreSQL-17-Testsuite, die in CI die Supabase-Migration anwendet und Workspace- sowie private
  Storage-RLS mit zwei getrennten Benutzeridentitäten prüft; die Ausführung benötigt einen
  PostgreSQL-Dienst.
- Schema-validierte Compose-Definitionen und konfigurierte CI-Builds für
  `linux/amd64`/`linux/arm64` sowie native Windows-, Apple-Silicon- und Linux-Artefakte.
- Lokal erzeugte Windows-Artefakte: MSI und NSIS-Installer unter
  `apps/desktop/src-tauri/target/release/bundle`.

## Nur mit bereitgestellten externen Zugängen prüfbar

- Tatsächlicher Compose-/Containerlauf; auf dem aktuellen Windows-Rechner fehlen Docker, WSL und
  die Administratorrechte zum Aktivieren von `VirtualMachinePlatform`.
- GitHub-CI-Läufe für Linux, Apple Silicon und Multi-Arch-Container; das lokale Repository besitzt
  noch kein Git-Remote.
- Supabase-Migration/RLS/Storage gegen ein echtes Supabase-Projekt; die zugrunde liegenden
  PostgreSQL-RLS-Regeln werden bereits in CI gegen PostgreSQL 17 geprüft.
- eBay Sandbox und Produktion read-only mit freigeschalteten Client-Credentials.
- IMAP-Retry, Roharchivierung und Quarantäne gegen das Testpostfach; bei konfiguriertem
  Supabase werden EML-Dateien zusätzlich in den privaten Bucket hochgeladen.
- Ollama-Modelllauf und optionale ntfy-Zustellung.
- Signierte Installer und Apple-Notarisierung; ohne Zertifikate erzeugt CI unsignierte Artefakte.

Die Live-Smoke-Tests bleiben absichtlich credential-gesteuert und führen weder Käufe noch
Verkäuferkontakte oder nicht autorisiertes Scraping aus.

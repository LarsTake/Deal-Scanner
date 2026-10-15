# ThinkCentre: schlanker Dauerbetrieb

Vorbereitet für Windows 11 Pro/Docker Desktop mit 8 GB RAM. Noch nicht auf deinem
ThinkCentre installiert oder unter Jellyfin-Last gemessen. Anleitung für den
HTTP-Sammler, nicht für Browserautomatisierung oder lokale KI auf dem Server.

## Vor dem Start

1. Produktionsdatenbank/Supabase einrichten und die SQL-Migrationen aus
   `infrastructure/supabase/migrations` anwenden. Die API migriert nicht automatisch.
   Datenbankrolle/RLS, Benutzer und Workspace-Mitgliedschaft nach
   [Setup](setup-and-integrations.md) konfigurieren.
2. `.env.example` nach `.env` kopieren. Produktionswerte setzen:
   `DEAL_SCANNER_ENVIRONMENT=production`, `DEAL_SCANNER_AUTH_MODE=supabase`,
   `DEAL_SCANNER_AUTO_CREATE_DB=false`, `DEAL_SCANNER_DATABASE_URL` mit
   `postgresql+asyncpg://…` und `DEAL_SCANNER_SUPABASE_URL`.
   `DEAL_SCANNER_API_TOKEN` muss ein gültiger Benutzer-Zugangstoken für den
   Workspace sein; Scheduler/Worker brauchen eine Erneuerungsstrategie vor Ablauf.
   Ein Service-Role-Key ist kein Ersatz für einen Benutzer-Token.
3. Gewünschte HTTP-Quellen aktivieren. Browser-/Stealth-Modi ausgeschaltet lassen.
   In der Weboberfläche Supabase-URL/Publishable-Key hinterlegen und anmelden.
   Keine Datenbankpasswörter oder Service-Role-Keys in die Oberfläche eingeben.
4. Freien Speicher und Backupziel prüfen. Die externe Datenbank ist in diesem Stack
   nicht enthalten; bei lokaler Supabase-Installation kommt deren RAM hinzu.

## Lokaler Start auf dem Windows-Host

In PowerShell im Projektverzeichnis:

```powershell
docker compose -f compose.yaml -f compose.thinkcentre.yaml config --quiet
docker compose -f compose.yaml -f compose.thinkcentre.yaml build
docker compose -f compose.yaml -f compose.thinkcentre.yaml up -d
docker compose -f compose.yaml -f compose.thinkcentre.yaml ps
docker stats --no-stream
```

Weboberfläche zunächst nur am Server unter `http://127.0.0.1:8088`, API unter
`http://127.0.0.1:8000`. Beide Hostports bleiben absichtlich an Loopback gebunden.
Das optionale Profil `tls` nicht starten: dein Caddy belegt bereits 80/443.
Das Profil `analysis` nicht auf dem ThinkCentre aktivieren.

Grenzen: API 512 MiB, Scheduler 320 MiB, Regel-Worker 320 MiB, Web 64 MiB.
Zusammen maximal 1216 MiB für diese vier Container; das ist eine konfigurierte
Obergrenze, kein gemessener Normalverbrauch und keine Reservierung. Docker/WSL,
Jellyfin-Transcoding, Datenbank und Build-Prozesse brauchen zusätzlichen Speicher.
Bei OOM/Neustarts erst Quelle/Last untersuchen, nicht ungeprüft Intervalle verkürzen.

## Vorhandenen Caddy verbinden

Den echten Netzwerknamen am Windows-Host ermitteln:

```powershell
docker inspect caddy --format '{{json .NetworkSettings.Networks}}'
```

`DEAL_SCANNER_PROXY_NETWORK` in `.env` auf das passende gemeinsame Docker-Netz setzen.
Es muss bereits existieren und dein Caddy muss daran angeschlossen sein.

```powershell
docker compose -f compose.yaml -f compose.thinkcentre.yaml -f compose.caddy-network.yaml up -d
```

Im **bestehenden** Caddy einen eigenen Host hinzufügen, etwa:

```caddyfile
scanner.example.test {
    reverse_proxy deal-scanner-web:8080
}
```

Den Beispielhost durch deinen tatsächlichen DNS-Namen ersetzen und TLS/DNS passend
zu deinem LAN konfigurieren. Vor Reload die bestehende Caddy-Datei sichern/validieren.
Keine Ports pauschal im Router öffnen. Für Internetzugriff zuerst Authentifizierung,
TLS und Zugriffsschutz prüfen. Die Weboberfläche verwendet ihre eigene Serveradresse
für API-Anfragen; vorhandene manuelle API-Einstellungen bei Bedarf zurücksetzen.

## Mac-/Windows-KI-Worker

Auf dem leistungsfähigeren Gerät den Worker mit eigener Konfiguration starten:
`DEAL_SCANNER_WORKER_MODE=ai`, `DEAL_SCANNER_API_URL=https://<dein-scanner-host>`,
`DEAL_SCANNER_API_TOKEN=<gültiger Benutzer-Token>` und passende lokale Ollama-Modelle.
Ollama bleibt lokal auf `127.0.0.1:11434`; keine Portfreigabe dafür erforderlich.
Server-Regeljobs laufen unabhängig weiter. „KI-Tiefenanalyse anfordern“ erzeugt
einen separaten Auftrag, der bei ausgeschaltetem KI-Gerät wartet.

## Abnahme vor echtem Dauerbetrieb

- Mit einem normalen Benutzer anmelden; fremde Workspaces dürfen nicht lesbar sein.
- Einen Suchauftrag mit moderatem Intervall und mehreren Quellen ausführen.
- KI-Gerät ausschalten: Sammlung und Regelbewertung müssen weiterarbeiten.
- Filter interessant/auffällig/unklar prüfen; unbekannte Werte bleiben sichtbar.
- 24 Stunden einschließlich Jellyfin-Nutzung und Containerneustart beobachten.
- Datenbank und Volumes `api-data`, `mail-archive`, `parser-data` sichern;
  Wiederherstellung in separater Umgebung testen. Keine Live-Dateikopie einer
  schreibenden Datenbank als verifiziertes Backup behandeln.

Produktionsfreigabe erst nach dieser Abnahme. Derselbe Stack kann später in eine
Linux-VM unter Proxmox umziehen; Datenbank, Volumes, Secrets und DNS werden dabei
gezielt migriert, nicht nur die Images.

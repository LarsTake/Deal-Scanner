# Dauerhafte Anmeldung für Scheduler und Regel-Worker

Die Dienste melden sich mit einem normalen Supabase-Auth-Benutzer an und erneuern
ihre Sitzung automatisch. Kein Service-Role-Key erforderlich. Jeder Prozess führt
eine eigene Sitzung; Refresh-Tokens werden nicht zwischen Diensten und Browser
geteilt und bleiben ausschließlich im Arbeitsspeicher.

## ThinkCentre einrichten

Voraussetzung: API/Web funktionieren bereits mit PostgreSQL und Supabase-Anmeldung.
Das neue Compose-Override erst nach der folgenden Einrichtung verwenden.

1. Aktuellen Code holen: git pull --ff-only.
2. In der lokalen .env ergänzen:

~~~dotenv
DEAL_SCANNER_SERVICE_EMAIL=DEINE_SCANNER_LOGIN_EMAIL
DEAL_SCANNER_SUPABASE_PUBLISHABLE_KEY=DEIN_PUBLISHABLE_KEY
DEAL_SCANNER_API_TOKEN=
DEAL_SCANNER_DEVELOPMENT_USER_ID=
~~~

Der Auth-Benutzer muss Mitglied im gewünschten Workspace sein. Für den ersten
Start kann der vorhandene Scanner-Benutzer verwendet werden. Ein späterer
dedizierter Dienstbenutzer muss gezielt demselben Workspace zugeordnet werden:
Ein neuer Benutzer bekommt zunächst einen eigenen Workspace. Die Dienste haben
die Workspace-Rechte dieses Benutzers; dies sind keine separat eingeschränkten
Maschinenidentitäten. Bei aktivierter Supabase-Einzelsitzungsbegrenzung dürfen sich
Browser-Anmeldung und mehrere Dienstsitzungen nicht gegenseitig verdrängen.

3. Passwort des Scanner-Auth-Benutzers, NICHT des Datenbankbenutzers, verdeckt eingeben:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\scripts\set-service-password.ps1
~~~

Die ExecutionPolicy-Ausnahme gilt nur für diesen PowerShell-Prozess, nicht global.
Das Skript erzeugt .secrets/service-password.txt als UTF-8-Datei. Der Ordner verliert
geerbte Berechtigungen und bekommt Zugriff für den ausführenden Windows-Benutzer.
Bereits bestehende explizite ACLs separat prüfen. Eine vorhandene Datei wird nicht
überschrieben.

Wichtig: Die Passwortdatei ist nicht verschlüsselt. Docker-Administratoren und
entsprechend privilegierte Prozesse können sie lesen. Git und Docker-Build-Kontext
schließen .secrets/ aus. Compose bindet das Secret nur in Scheduler/Regel-Worker ein.
Keine Passwörter in Befehle, Chat oder Git schreiben.

4. Konfiguration ohne Zugangsdaten-Ausgabe prüfen und Images bauen:

~~~powershell
docker compose -f compose.yaml -f compose.thinkcentre.yaml -f compose.service-auth.yaml config --quiet
docker compose -f compose.yaml -f compose.thinkcentre.yaml -f compose.service-auth.yaml build api scheduler rule-worker
~~~

5. API mit dem neuen Image aktualisieren, dann nur den API-Anmeldetest ausführen:

~~~powershell
docker compose -f compose.yaml -f compose.thinkcentre.yaml -f compose.service-auth.yaml up -d api
docker compose -f compose.yaml -f compose.thinkcentre.yaml -f compose.service-auth.yaml run --rm -T --no-deps rule-worker python -c "import asyncio; from deal_scanner_service_auth.check import run; asyncio.run(run())"
~~~

Erwartet: OK: Dienstanmeldung und Workspace-Zugriff funktionieren.
Keine Tokens/Passwörter ausgeben. Diese Testsitzung wird anschließend lokal
verworfen; sie kann bis zum Ablauf in Supabase als Sitzung vorhanden bleiben.
Der Anmeldetest selbst erzeugt eine Sitzung und aktualisiert ggf. Auth-Metadaten,
liest aber nur den API-Endpunkt auth/me und führt keinen Scan/Import aus.

6. Erst nach erfolgreichem Test die Dienste starten:

~~~powershell
docker compose -f compose.yaml -f compose.thinkcentre.yaml -f compose.service-auth.yaml up -d scheduler rule-worker
docker compose -f compose.yaml -f compose.thinkcentre.yaml -f compose.service-auth.yaml ps
~~~

Suchquellen und Suchaufträge danach bewusst aktivieren. Ein vorhandenes
Caddy-Netzwerk-Override ebenfalls ergänzen, falls bereits verwendet.

## Störungen, Neustart und Widerruf

- Erneuerung vor Ablauf; konkurrierende Anfragen teilen eine serialisierte
  Erneuerung innerhalb desselben Prozesses.
- Bei API-401 genau eine Erneuerung und ein weiterer Versuch. Keine automatische
  Wiederholung bei 403, 5xx oder unklar fehlgeschlagenen Schreibanfragen.
- Netzwerk-/Supabase-Ausfälle unterbrechen die Arbeit; die Dienstschleifen
  versuchen es später erneut. Kein anonymer Entwicklungs-Fallback.
- Abgelehnte Zugangsdaten oder widerrufene Refresh-Tokens sperren die Anmeldung
  des laufenden Prozesses. Kein stiller Passwort-Neulogin. Nach Ursachenprüfung
  Zugangsdaten korrigieren und den betroffenen Dienst bewusst neu starten.
- Neustart meldet mit dem Passwort neu an. Dauerhafter Entzug erfordert Entzug
  von Benutzer-/Workspace-Zugang bzw. Passwortwechsel; nur eine Sitzung abzumelden
  genügt nicht, solange der Dienst das gültige Passwort besitzt.
- Bereits ausgestellte JWTs können bis zum Ablauf gültig bleiben. Das ist keine
  Echtzeit-Widerrufsprüfung bei jeder API-Anfrage.
- API-Zugangsdaten gehen nur an die konfigurierte API-Origin unter /api/v1/,
  nicht an Ollama oder Bild-/Storage-URLs.

Grundlagen: [Supabase-Sitzungen](https://supabase.com/docs/guides/auth/sessions).
Diese Funktion ist kein Free-Tarif-Keep-alive und verhindert Projektpausen nicht garantiert.

## Prüfstand

Mock-Tests prüfen Login, Erneuerung/Parallelität, API-401, Widerruf, Netz-/Serverfehler,
Fehlkonfiguration und Schutz gegen Weitergabe an fremde Origins. Keine echten
Benutzerzugangsdaten werden für Tests verwendet. Windows-Secret-ACLs und die echte
Supabase-Anmeldung müssen auf dem ThinkCentre noch abgenommen werden.

Der asyncpg-Treiber ist nun explizit in API und Scheduler enthalten, damit eine
postgresql+asyncpg-Verbindungsadresse auch im isolierten Container unterstützt wird.

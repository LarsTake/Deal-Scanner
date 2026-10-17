# Windows-App mit Ollama einrichten

Die App zeigt Dashboard und Angebote und steuert einen lokalen KI-Worker. API,
Datenbank und Sammlung können auf einem eigenen zentralen Server laufen. Es
sind keine persönlichen IP-Adressen oder Konten im Programm vorbelegt.

## 1. Server einmal vorbereiten

Den Server gemäß [Einrichtung und Integrationen](setup-and-integrations.md) mit
Docker und eigenem Supabase-Projekt einrichten. Migrationen liegen unter
`infrastructure/supabase/migrations`. Die **Server-`.env`** benötigt unter anderem:

```dotenv
DEAL_SCANNER_ENVIRONMENT=production
DEAL_SCANNER_AUTH_MODE=supabase
DEAL_SCANNER_SUPABASE_URL=https://PROJECT.supabase.co
DEAL_SCANNER_SUPABASE_PUBLISHABLE_KEY=PUBLIC_PUBLISHABLE_OR_ANON_KEY
DEAL_SCANNER_CORS_ORIGINS=http://tauri.localhost,tauri://localhost
```

Dies ist ein Auth-Ausschnitt, keine vollständige Server-Konfiguration.
Datenbankverbindung, Rollen und Workspace-Zugriff ebenfalls einrichten;
bestehende Web-Ursprünge in CORS beibehalten. Datenbankpasswort und Service-Role-Key
gehören ausschließlich auf den Server. `GET /api/v1/client-config` muss erreichbar
sein und `authMode: "supabase"` sowie die öffentliche URL und den öffentlichen
Schlüssel liefern. Das Scanner-Konto muss im eigenen Supabase-Projekt bestehen.

Ein bestehendes Windows-Compose-Deployment kann mit folgendem Skript auf dem
**Server** aktualisiert werden (eigene Adresse einsetzen):

```powershell
.\infrastructure\scripts\update-thinkcentre-auth.ps1 -ServerUrl 'https://scanner.example.com'
```

Es erwartet genau einen laufenden Compose-Service `api`, verwendet dessen
bestehende Compose-Dateien, baut die API neu und prüft Client-Konfiguration und
Desktop-CORS. Änderungen an `.env` werden unter `.backups` gesichert. Docker
und Supabase werden dadurch nicht neu installiert.

Eine erreichbare Serveradresse genügt, vorzugsweise HTTPS mit eigenem DNS-Namen.
Lokale IPv4-Adressen werden auch über HTTP unterstützt. Ein Wechsel zwischen
WLAN und LAN erzeugt keine automatische IP-Weiterleitung. Docker-Portbindung und
Firewall müssen den Zugriff auf die gewählte Adresse zulassen.

## 2. Worker-Laufzeit installieren

Auf jedem Windows-PC werden Git, `uv` und Ollama benötigt. In PowerShell:

```powershell
winget install --id Git.Git --exact
winget install --id astral-sh.uv --exact
winget install --id Ollama.Ollama --exact
```

Ein neues Terminal öffnen, Ollama starten und den Checkout einrichten:

```powershell
git clone https://github.com/LarsTake/Deal-Scanner.git
Set-Location Deal-Scanner
uv python install 3.12
uv sync --all-packages --frozen --python 3.12
```

Der Installer enthält **keine Python-Laufzeit**. Checkout und `.venv` behalten,
da die App daraus den Worker startet. Für einen entfernten Server benötigt dieser
PC keine `.env` mit Server-Datenbankdaten.

## 3. Modelle laden

Dieses Profil wurde mit 12 GB Grafikspeicher und 32 GB RAM erprobt. Modellnamen
sind in der App frei einstellbar; andere Modelle müssen für strukturierte
Ausgaben beziehungsweise Bildanalyse geeignet sein.

```powershell
ollama pull gemma4:12b
ollama pull gpt-oss:20b
ollama pull qwen3-embedding:0.6b
ollama list
```

| App-Feld | Modell | Aufgabe |
| --- | --- | --- |
| Textmodell | `gemma4:12b` | Produkte und Attribute extrahieren |
| Risikoanalyse, optional | `gpt-oss:20b` | Risiken und Widersprüche prüfen |
| Embedding, optional | `qwen3-embedding:0.6b` | Vektoren für Ähnlichkeitssuchen |
| Vision | `gemma4:12b` | Angebotsbilder auswerten |

Das ist Bildanalyse, keine Bildgenerierung. GPT-OSS kann teilweise im RAM laufen
und langsamer sein. Optionale Felder können leer bleiben. `ollama ps` zeigt die
tatsächliche CPU-/GPU-Nutzung. Downloads können mehrere GB groß sein.

Bei begrenztem Grafikspeicher können folgende Benutzer-Einstellungen helfen:

```powershell
[Environment]::SetEnvironmentVariable('OLLAMA_CONTEXT_LENGTH', '8192', 'User')
[Environment]::SetEnvironmentVariable('OLLAMA_MAX_LOADED_MODELS', '1', 'User')
[Environment]::SetEnvironmentVariable('OLLAMA_NUM_PARALLEL', '1', 'User')
[Environment]::SetEnvironmentVariable('OLLAMA_FLASH_ATTENTION', '1', 'User')
[Environment]::SetEnvironmentVariable('OLLAMA_KV_CACHE_TYPE', 'q8_0', 'User')
```

Danach Ollama vollständig beenden und neu starten.

## 4. App installieren oder bauen

Ein Windows-Paket kann ein Repository-Berechtigter unter **GitHub → Actions →
Desktop artifacts → Run workflow** bauen lassen. Nach erfolgreichem Lauf das
Artefakt `deal-scanner-windows` herunterladen und den Installer darin ausführen.
Ein normaler Push auf `main` startet diesen Paket-Workflow nicht. Ohne
Signierzertifikat sind die Installer unsigniert.

Alternativ selbst bauen: Node.js 24, pnpm **10.28.0**, Rust, Visual Studio Build
Tools mit **Desktopentwicklung mit C++** und Windows SDK installieren. Die App
benötigt WebView2. Im Checkout:

```powershell
npm install --global pnpm@10.28.0
pnpm install --frozen-lockfile
pnpm --filter @deal-scanner/desktop tauri build --bundles nsis
```

Installer: `apps/desktop/src-tauri/target/release/bundle/nsis`.
Nach der Installation die App im Startmenü öffnen. Optional startet
`infrastructure/scripts/start-desktop.ps1` eine normal installierte App. Nur mit
`-LocalServer` startet es zusätzlich die lokale Entwicklungsumgebung; diese
benötigt Node/pnpm, `.env` und vorheriges `start-local.ps1 -Install`.

## 5. Server verbinden und Analyse starten

1. Unter **Anmelden** die eigene Serveradresse eingeben und **Server verbinden**
   wählen. Supabase-URL und öffentlicher Schlüssel werden automatisch übernommen
   und dauerhaft gespeichert. Neue Geräte benötigen Serveradresse und persönliche
   Anmeldung, keine erneute manuelle Supabase-Einrichtung.
2. Mit Scanner-E-Mail und Passwort anmelden. In Tauri die Tresorpassphrase für
   die Dashboard-Sitzung angeben.
3. Unter **Dieses Gerät · KI** den Haken **Lokaler Betrieb auf diesem PC** bei
   einem zentralen Server **ausgeschaltet lassen**. Dieser Haken ist nur für eine
   Entwicklungs-API auf `127.0.0.1`/`localhost`, nicht für den Standort von Ollama.
4. Den vollständigen Pfad zu `.venv\Scripts\deal-scanner-worker.exe` im Checkout
   als Worker-Programmdatei eintragen. Die API-Adresse und die öffentlichen
   Supabase-Daten werden aus der Serververbindung übernommen.
5. Modelle eintragen und **Zusätzlich Bilder analysieren** nach Bedarf aktivieren.
   Ohne Bildanalyse arbeitet dieser Worker ohne Vision und Tesseract.
6. Unter **Dienstanmeldung** Scanner-E-Mail und Passwort hinterlegen. Diese
   Worker-Anmeldung ist unabhängig von der Dashboard-Sitzung. Keine Datenbank-
   oder Service-Role-Schlüssel eingeben.
7. Einstellungen speichern und **Analyse starten** wählen. Vor Änderungen den
   Worker stoppen. Ein leeres Passwortfeld behält das gespeicherte Passwort.

Der Worker läuft bei minimiertem Fenster weiter und endet beim Beenden der App.
Die App richtet keinen neuen System-Autostart ein. Nicht zusätzlich einen
separaten Worker mit denselben Aufgaben starten. **Prozess läuft** bestätigt nur
den Start; unter **Worker** im Dashboard Heartbeat und abgeschlossene Jobs prüfen.
Ohne wartende Jobs ist der Worker untätig.

Konfiguration, Passwortdatei und `worker.log` liegen unter
`%LOCALAPPDATA%\de.dealscanner.desktop\local-worker`. Das Worker-Passwort ist durch
Benutzerzugriffsrechte geschützt, aber **nicht verschlüsselt**. Diese Dateien nicht
weitergeben oder einchecken. Dashboard-Token liegen getrennt im Stronghold-Tresor.
App-Updates aktualisieren nicht automatisch Server, Python-Checkout oder Modelle.

Unter **Suchaufträge → Treffer ansehen** öffnet sich die Angebotsliste mit dem
entsprechenden Suchauftragsfilter. **Zurücksetzen** entfernt den Filter.

## 6. Textanalyse mit Internet

Mit `ollama signin` den PC mit einem eigenen Ollama-Konto verbinden. Unter
**Dieses Gerät · KI → Textanalyse und Webrecherche** eine Frage eingeben.
Die Internetoption ist standardmäßig aktiv und kann ausgeschaltet werden.

Mit Internet wird die Suchfrage an Ollamas externen Suchdienst übermittelt.
Das lokale Textmodell erstellt eine Antwort aus begrenzten Quellenausschnitten;
Quellenlinks werden angezeigt. Verwendet wird der experimentelle lokale
Websuche-Proxy, der sich mit zukünftigen Ollama-Versionen ändern kann. Ein
API-Schlüssel in `.env` ist dafür nicht erforderlich. Alternativ im Checkout:

```powershell
.\.venv\Scripts\python.exe infrastructure/scripts/research-local.py "Welche technischen Daten hat eine NVIDIA RTX 4070 SUPER?"
```

Diese separate Recherche ergänzt Inseratdaten nicht automatisch. Die automatische
Angebotsanalyse verarbeitet weiterhin die vorliegenden Inseratinhalte.

## Fehlerdiagnose

| Symptom | Prüfen |
| --- | --- |
| Supabase nicht konfiguriert | Server verbinden; `/api/v1/client-config` und Server-`.env` prüfen |
| HTTP 404 beim Konfigurationsendpunkt | Server-Code und API-Container aktualisieren |
| API erreichbar, App-Verbindung scheitert | Desktop-CORS, Adresse und HTTPS-Zertifikat prüfen |
| Prozess läuft, kein Heartbeat | Dienstanmeldung, Workspace-Zugriff und `worker.log` prüfen |
| Analysefehler / Modell fehlt | `ollama list`, Modellnamen und laufendes Ollama prüfen |
| Websuche meldet 401 | `ollama signin` auf diesem PC abschließen |
| WLAN-/LAN-Adresse antwortet nicht | Docker-Portbindung, Netzwerk und Firewall prüfen |

Das optionale Administratorskript `enable-thinkcentre-lan-wifi.ps1` erlaubt alle
Programme und Ports innerhalb des ausdrücklich angegebenen Netzes. Es ist kein
Teil des normalen Setups und richtet weder IP-Weiterleitung noch Docker ein.
Beispiel mit eigenen Adressen ersetzen:

```powershell
.\infrastructure\scripts\enable-thinkcentre-lan-wifi.ps1 -ServerAddresses '192.168.1.10','192.168.1.11' -HomeNetwork '192.168.1.0/24'
```

Weitere Anleitung: [Angebotsimport mit cURL](import-with-curl.md).
Offizielle Dokumentation: [Ollama Windows](https://docs.ollama.com/windows),
[Ollama Websuche](https://docs.ollama.com/capabilities/web-search).

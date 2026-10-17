# Desktop-App: ThinkCentre-Dashboard und lokale KI

Die Tauri-App öffnet beim Start das konfigurierte Server-Dashboard im Standardbrowser.
Das lokale App-Fenster bietet die Worker-Steuerung unter **Dieses Gerät · KI**.
Die Server-Seite erhält damit keine Tauri-Laufzeit und keine lokalen Berechtigungen;
jeder native Steuerbefehl prüft zusätzlich Fenstername und lokale Herkunft.
Die ältere Server-Oberfläche würde sonst die eingebettete Webview als Desktop-App
erkennen und beim Zugriff auf nicht freigegebene SQL-Funktionen nicht starten.
Das Mac-Paket enthält keine App-Transport-Security-Ausnahmen. Die Dashboard-Adresse
wird vor dem Öffnen auf HTTPS oder lokale HTTP-Adressen begrenzt. Für Zugangsdaten
bleibt HTTPS auch im Heimnetz vorzuziehen.

## Voraussetzungen

- Windows oder macOS, erreichbarer Scanner-Server und laufendes lokales Ollama.
- Installierte Python-Worker-Laufzeit: im Repository
  `uv sync --all-packages --frozen` ausführen. Python/Worker werden derzeit **nicht**
  in das App-Paket eingebettet. Ollama-Modelle werden nicht automatisch geladen.
- Worker-Programmdatei wählen: `.venv/bin/deal-scanner-worker` unter macOS oder
  `.venv/Scripts/deal-scanner-worker.exe` unter Windows.
- Supabase-URL, Publishable-Key, Scanner-E-Mail und Scanner-Passwort hinterlegen.
  Keine Datenbank-Zugangsdaten und keine Service-Role-Keys verwenden.

Auf dem bereits eingerichteten Mac werden die Werte des bekannten LaunchAgents
`de.deal-scanner.text-worker` gelesen. Sein Passwort wird nicht in die UI geladen.
Solange dieser Dienst geladen ist, startet die App keinen zweiten Worker. **Stopp**
deaktiviert dessen Autostart und entlädt den Dienst. Danach kann die App übernehmen.

## Bedienung

1. Bei Bedarf die ThinkCentre-Adresse ändern, z. B. `http://192.168.178.169:8088`.
2. Worker stoppen, bevor die Einstellungen geändert werden.
3. Textmodell eintragen; optional Bildanalyse einschalten und ein installiertes,
   bildfähiges Vision-Modell zuweisen.
4. Einstellungen speichern und **Worker aktivieren** wählen.
5. **Worker deaktivieren** stoppt den lokalen Prozess. Laufende Jobs können dabei
   abgebrochen und nach Ablauf ihrer Lease erneut verarbeitet werden.

Der App-Worker läuft bei minimierter App weiter, nicht nach dem Beenden der App.
Die App richtet keinen neuen OS-Autostart ein. Bei Ruhemodus oder ausgeschaltetem
Computer pausiert die lokale KI; die serverseitige Sammlung läuft weiter.
Das Statusfeld zeigt den lokalen Prozesszustand, nicht den Erfolg der Anmeldung
oder einer Modellanalyse. Heartbeat/Jobs im Server-Dashboard und `worker.log`
prüfen. Textmodus deaktiviert Vision und Tesseract; separate Reasoning- und
Embedding-Stufen sind in diesem schlanken Profil ausgeschaltet.

Passwortdateien sind auf Unix mit `0600` geschützt; unter Windows wird die
ACL-Vererbung entfernt und dem aktuellen Benutzer Zugriff gewährt. Sie sind nicht
verschlüsselt. Speicherort: App-Local-Data-Verzeichnis, Unterordner `local-worker`.
Worker-Logs können Angebotsinformationen enthalten.

## App-Pakete bauen

Auf dem jeweiligen Zielsystem mit Node/pnpm, Rust und den Tauri-Buildvoraussetzungen:

```sh
corepack pnpm install --frozen-lockfile
corepack pnpm --filter @deal-scanner/desktop tauri build
```

macOS erzeugt `.app`/DMG; Windows erzeugt die konfigurierten Windows-Installer.
Ergebnisse liegen unter `apps/desktop/src-tauri/target/release/bundle`.
Der vorhandene GitHub-Workflow **Desktop artifacts** baut Windows und Apple-Silicon
auf ihren jeweiligen Runnern. Er wurde durch diese lokale Implementierung nicht
automatisch gestartet. Ohne Entwicklerzertifikate sind Artefakte nicht für eine
ungeprüfte öffentliche Verteilung signiert/notarisiert.

Das Dashboard lädt die Version, die tatsächlich auf dem ThinkCentre installiert
ist. Ein Desktop-App-Update aktualisiert nicht automatisch den Server.

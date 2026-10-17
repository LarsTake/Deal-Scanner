# Desktop-App und lokaler KI-Worker

Die Tauri-App zeigt Dashboard, Suchaufträge und Angebote im eigenen Fenster.
Unter **Dieses Gerät · KI** steuert sie einen lokalen Worker und bietet
Textanalyse mit optionaler Webrecherche. Der Dashboard-Button öffnet auf Wunsch
den Standardbrowser; beim Start wird kein Browser automatisch geöffnet.

Die vollständige [Windows-Anleitung](ollama-windows.md) beschreibt Installation,
Server, Modelle und Fehlerdiagnose. Unter **Anmelden → Server verbinden** die
eigene API-Adresse hinterlegen. `/api/v1/client-config` liefert automatisch die
öffentliche Supabase-Konfiguration. Persönliche Dashboard-Sitzung und
Worker-Dienstanmeldung bleiben getrennt. Keine Datenbankpasswörter oder
Service-Role-Keys auf Endgeräten hinterlegen.

Die CSP erlaubt Netzwerkverbindungen zu eigenen HTTP(S)-Servern und Supabase-
Domains, ohne private IPs einzubauen. Native Steuerbefehle prüfen Fenstername
und lokale Herkunft; externe Serverseiten dürfen keinen Worker steuern.

## Analyse

Die App benötigt laufendes Ollama und eine separat installierte Worker-Laufzeit:
`uv sync --all-packages --frozen`. Programmdatei: `.venv/bin/deal-scanner-worker`
unter macOS oder `.venv/Scripts/deal-scanner-worker.exe` unter Windows. Python
und Modelle sind nicht im Installer enthalten.

Bei einem zentralen Server bleibt **Lokaler Betrieb auf diesem PC** ausgeschaltet.
Die Option gilt ausschließlich für lokale Entwicklungs-APIs mit Entwicklungsauth.
Textmodell ist Pflicht; Risiko- und Embedding-Modell sind optional. Bildanalyse
benötigt ein installiertes Vision-Modell. Ohne Bildanalyse sind Vision und
Tesseract deaktiviert.

Vor Änderungen den Worker stoppen, speichern und **Analyse starten** wählen.
**Analyse stoppen** beendet den eigenen Prozess, unter Windows auch dessen
Kindprozesse. Laufende Jobs können nach Ablauf ihrer Lease neu verarbeitet werden.
Der Worker läuft minimiert weiter, endet aber beim Schließen der App. Es wird
kein neuer System-Autostart eingerichtet.

Auf macOS können Einstellungen des bisherigen LaunchAgents
`de.deal-scanner.text-worker` übernommen werden. Solange dieser geladen ist,
startet die App keinen zweiten Worker. Stoppen entlädt den Dienst und deaktiviert
seinen Autostart, bevor die App übernimmt.

Der Prozesszustand beweist keine erfolgreiche Analyse. Heartbeat und Jobs unter
**Worker** und das lokale `worker.log` prüfen. Die separate Recherche mit Internet
reichert Inserate nicht automatisch mit Webdaten an.

## Speicherung und Pakete

Konfiguration, Passwortdatei und Logs liegen im App-Local-Data-Verzeichnis unter
`local-worker`. Das Worker-Passwort ist auf Unix mit `0600` und auf Windows durch
eine Benutzer-ACL geschützt, aber nicht verschlüsselt. Dashboard-Token liegen
getrennt im Stronghold-Tresor. Logs können Angebotsdaten enthalten.

Die Windows-Anleitung erklärt den lokalen Build und den GitHub-Workflow
**Desktop artifacts**. Pakete liegen unter
`apps/desktop/src-tauri/target/release/bundle`. Ohne Entwicklerzertifikate sind
sie nicht signiert beziehungsweise notarisiert. Desktop-Updates aktualisieren
Server, Python-Checkout und Modelle nicht automatisch.

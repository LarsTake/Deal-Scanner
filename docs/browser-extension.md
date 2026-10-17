# Chrome-Erweiterung installieren und verbinden

## Installation über App oder Dashboard

Unter **Einstellungen → Chrome-Erweiterung installieren** die ZIP herunterladen.
Der öffentliche Download liegt auch unter
`GET /api/v1/downloads/browser-extension` auf dem eigenen Scanner-Server.
Die ZIP enthält Programmdateien und eine Kurzanleitung, keine Kontozugangsdaten.
Alternativ stellt ein erfolgreicher GitHub-Actions-Lauf **CI → Quality and
PostgreSQL isolation** das Artefakt `deal-scanner-chrome` bereit.

1. ZIP in einen dauerhaften Ordner entpacken.
2. `chrome://extensions` in Chrome öffnen und **Entwicklermodus** einschalten.
3. **Entpackte Erweiterung laden** wählen und den Ordner mit `manifest.json` öffnen.
4. Die Erweiterung über das Puzzle-Symbol bei Bedarf anheften.

Die Erweiterung ist nicht im Chrome Web Store veröffentlicht. Eine direkte
Ein-Klick-Installation von unserer Website ist deshalb nicht vorgesehen. Die
Installationswege beschreibt [Google](https://developer.chrome.com/docs/extensions/how-to/distribute).

## Eigenes Konto automatisch übernehmen

1. Das Scanner-Dashboard **in Chrome** öffnen und mit dem Scanner-Konto anmelden.
   Bei Verwendung der Windows-App gegebenenfalls **Dashboard im Browser öffnen**
   verwenden; eine native App ist kein Chrome-Tab.
2. Diesen Tab geöffnet lassen, Erweiterungs-Popup öffnen und **Mit geöffnetem
   Scanner verbinden** wählen.
3. Die angefragte Berechtigung für den eigenen API-Host bestätigen.

Die Erweiterung übernimmt API-Adresse und ein neu erstelltes, widerrufbares
Geräte-Token automatisch. Kein Kopieren von URL oder Token, keine separate
Passworteingabe in der Erweiterung. Passwort und Supabase-Access-/Refresh-Token
werden nicht übertragen. Das Geräte-Token berechtigt nur Browser- und Bildimporte
im zugehörigen Workspace. Es bleibt lokal in Chrome gespeichert und wird nicht
über Chrome Sync synchronisiert; der API-Host darf synchronisiert werden.

Die einmalige Kopplung bleibt nach Browser- und App-Neustarts bestehen. Unter
**Einstellungen → Dauerhafte Kontoverbindung** kann sie widerrufen werden.
Bei einem Kontowechsel erneut mit dem gewünschten Konto koppeln und die bisherige
Verbindung im alten Konto widerrufen. Alternativ ist weiterhin die manuelle
Verbindung mit API-Adresse und Geräte-Token im Popup möglich.

Voraussetzung ist eine aktuelle Weboberfläche mit Kopplungsfunktion. Ein
API-Update allein aktualisiert keine separat laufende Weboberfläche.

## Einzelne Seiten oder ganzer Durchlauf

Der Button auf einer Kleinanzeigen-Seite importiert weiterhin die aktuelle
Detailseite oder alle geladenen Karten der aktuellen Ergebnisseite. Karten
enthalten häufig nur einen Kurztext.

Für vollständige Artikelbeschreibungen:

1. Eine Kleinanzeigen-Ergebnisseite öffnen und das Erweiterungs-Popup öffnen.
2. Seitenlimit (1–20), Angebotslimit (1–200) und Pause (3–60 Sekunden) einstellen.
   Standard: 3 Seiten, 50 Angebote, 5 Sekunden je aufgerufener Seite.
3. **Durchlauf starten** wählen. Der aktuelle Tab öffnet nacheinander die
   gefundenen Angebotsdetailseiten, importiert Beschreibung und Bilder und
   wechselt anschließend zur nächsten Ergebnisseite.
4. **Durchlauf stoppen** im Popup hält den Lauf an. Ein bereits gestarteter
   Import kann noch abschließen. Das Popup darf währenddessen geschlossen werden.

Der Lauf verarbeitet nur die im DOM erkannten Angebote, keine noch nicht
geladenen/infinite-scroll-versteckten Treffer. Er erkennt vorhandene Weiter-Links,
verhindert Schleifen und doppelte Detailaufrufe innerhalb desselben Durchlaufs.
Er startet nicht automatisch beim Browserstart und endet beim Browser-Neustart.
Der Tab muss geöffnet bleiben. Ein Wechsel auf eine andere Kleinanzeigen-Seite
außerhalb des Durchlaufs hält ihn beim nächsten Seitenstart an.

Bei fehlenden Beschreibungen, entfernten Angeboten, Sicherheitsabfragen oder
API-Fehlern stoppt er mit einer Meldung. Die Seite manuell prüfen und gegebenenfalls
neu starten. Es werden keine CAPTCHAs oder Zugriffsbeschränkungen umgangen.
Bei zukünftigen Änderungen an Kleinanzeigen können die Selektoren anzupassen sein.

## Server-Betreiber: Paket bereitstellen und aktualisieren

Beim Build des API-Docker-Images wird die Erweiterung automatisch gebaut und als
ZIP unter `/app/artifacts/deal-scanner-chrome.zip` abgelegt. Das ist unabhängig
vom Datenvolume. Für eine manuell betriebene API im Checkout:

```powershell
pnpm install --frozen-lockfile
pnpm browser-extension:package
```

Der Befehl benötigt Node.js 24, pnpm 10.28.0, `uv` und die Python-Workspace-
Abhängigkeiten. Er erzeugt `artifacts/deal-scanner-chrome.zip`. Die API erwartet
diesen Pfad relativ zu ihrem Arbeitsverzeichnis. Optional kann
`DEAL_SCANNER_BROWSER_EXTENSION_ARCHIVE` einen anderen absoluten Pfad vorgeben.
Fehlt das Paket, liefert der Download eine erklärende 404-Antwort.

Bestehende Docker-Deployments nach `git pull --ff-only` mit ihren bisherigen
Compose-Dateien neu bauen: **API und Weboberfläche** aktualisieren. Das
ThinkCentre-Update-Skript kann beides im selben Compose-Projekt aktualisieren:

```powershell
.\infrastructure\scripts\update-thinkcentre-auth.ps1 -ServerUrl 'https://scanner.example.com' -IncludeWeb
```

Einen außerhalb dieses Projekts betriebenen Web-Service zusätzlich neu bauen.
Datenvolumes und `.env` beibehalten.

Für lokale Updates: ZIP erneut herunterladen, im bisherigen Erweiterungsordner
entpacken und unter `chrome://extensions` **Neu laden** wählen. Bereits offene
Kleinanzeigen-Tabs ebenfalls neu laden. Bei unverändertem Installationspfad
bleiben die gespeicherte Verbindung und die Berechtigungen erhalten; laufende
Durchläufe werden durch das Neuladen beendet.

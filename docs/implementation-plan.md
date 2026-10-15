# Deal Scanner: Umsetzungsplan

Stand: 15.10.2026. Zielgerät: Lenovo ThinkCentre, Windows 11 Pro, Docker Desktop,
8 GB RAM; Pi-hole, Jellyfin und Caddy laufen bereits. Späterer Umzug: derselbe
Container-Stack in eine Linux-VM unter Proxmox.

## Produktziel und Leitplanken

Ein Suchauftrag sammelt plattformübergreifend Angebote. Der Server speichert
unveränderte Evidenz und erledigt die Grundbewertung ohne KI. Nutzer sehen
interessante, auffällige und nicht ausreichend belegbare Treffer getrennt.
Mac-/Windows-Worker ergänzen auf explizite Anforderung eine versionierte KI-Analyse.
Offline-Geräte blockieren die Sammlung und Grundbewertung nicht.

„Bester“ wird anhand von Treffergenauigkeit, nachvollziehbaren Gründen, Aktualität,
Zuverlässigkeit und Ressourcenverbrauch geprüft; eine Marktführerschaft wird nicht behauptet.
Ein unbekannter Marktwert wird niemals als schlechter Deal oder als bestätigter Verkauf ausgegeben.
Daten werden zum Filtern nicht gelöscht. Preis, Risiko und Datenqualität bleiben getrennt.

## Priorisierte Pakete

| Paket | Ergebnis | Abnahme |
| --- | --- | --- |
| P0.1 Grundanalyse/KI trennen | Eigene Regel- und Tiefenanalyse-Jobs; Regeln erzwingen keinen Modellaufruf | Regel-Worker verarbeitet Grundjobs, kann KI-Aufträge nicht übernehmen; KI-Aufträge warten bei Offline-Geräten |
| P0.2 Treffer gezielt sichten | Serverseitige Filter für Plattform, Suchauftrag, Text, Deal, Risiko und Qualität; Ansichten interessant/auffällig/unklar | Filter greifen vor Pagination; unklare Treffer sind separat abrufbar; Grundbewertung genügt |
| P0.3 Schlanker Server | Dauerhafter Regel-Worker, ausgelieferte Weboberfläche, begrenzte Container, bestehender Caddy bleibt vorgeschaltet | Compose-Konfiguration geprüft, keine Secrets im Build-Kontext; Grundbetrieb ohne Ollama/GPU |
| P0.4 ThinkCentre in Betrieb nehmen | Authentifizierter Zugriff von anderen Geräten, echte Suchen, Backup und Wiederanlauf | Live-Abnahme auf Windows, einschließlich Jellyfin-Last; keine Portkollision mit Pi-hole/Caddy |
| P1.1 Vergleichbare Preise | Ganze Angebote, Einzelteile, Zustand, Variante und Bundles sauber unterscheiden; Vergleichsquellen anzeigen | Kein PC-Gesamtpreis als GPU-Preis; Zielangebot nicht als eigene unabhängige Vergleichsevidenz zählen |
| P1.2 Fundierte Auffälligkeiten | Änderungen, Kopien, ungewöhnliche Preisabweichungen, fehlende Angaben und Verkäufermerkmale erklären | Jede Warnung nennt Quelle, Regelversion und Evidenz; keine unbegründete Betrugsbehauptung |
| P1.3 Komfortable Suchaufträge | Intervall, Quellen, Pflicht-/Ausschlussbegriffe, Quellenstatus und Ergebnisse direkt pro Suche | Bearbeiten/Pausieren verändert keine Historie; Fehler einer Quelle stoppen andere nicht |
| P1.4 Geräte-Worker | Separate Konfiguration für Mac/Windows; gezielte KI-Aufträge, Fortschritt und Wiederholungen | Worker kontaktiert Server ausgehend; Ollama bleibt lokal; falsche/stale Ergebnisse überschreiben keine aktuellen Daten |
| P2.1 Messbare Qualität | Manuell geprüfter Referenzsatz, Präzision je Kategorie und Quelle, False-Positive-Feedback | Verbesserungen werden gegen denselben Referenzsatz bewertet; keine Erfolgsquoten ohne Messdaten |
| P2.2 Betrieb und Skalierung | Sammlungslatenz, Speicherwachstum, Ausfallalarm, Backups, Lasttests und Index-/Abfrageoptimierung | Restore in separater Umgebung funktioniert; 24-Stunden-Test ohne KI und mit Neustarts |
| P2.3 Restock und Browser | Gewählte Produktlinks abnehmen; optional Browser-Laufzeit unter Last prüfen | Keine Verfügbarkeitsmeldung bei unbekannten Daten; HTTP bleibt Standard; Ressourcen-/Sperrgrenzen eingehalten |
| P3 Proxmox-Umzug | Images, Konfiguration und verifizierte Daten-Backups in Linux-VM übernehmen | Gleiche Suchen/History nach Wiederherstellung; Rückweg zum ThinkCentre vorhanden |

## Erste Umsetzung

Implementiert: getrennte Regel-/KI-Jobs, deduplizierte laufende Tiefenanalysen,
serverseitige Trefferfilter, Datenqualitätsgrenze für Meldungen, konfigurierbare
Scanintervalle sowie Web-Container und ThinkCentre-/Caddy-Compose-Ergänzungen.
Die Anleitung steht in [ThinkCentre-Deployment](thinkcentre-deployment.md).
P0.4 und P1–P3 sind noch nicht abgeschlossen.

### Zweite Ausbaustufe: Vergleichssicherheit

Der erste Teil von P1.1 ist implementiert (`comparability-v1`):

- Eigene importierte Preisstände sind keine unabhängigen Vergleichsdaten.
- Pro anderem Angebot wird höchstens der jüngste Preisstand verwendet.
- PC-/System-, Bundle-, Mehrfach- und unklare Angebote liefern keine Einzelteilpreise.
  Auch alte, fälschlich zugeordnete Beobachtungen werden beim Vergleich überprüft.
- Erkannte Varianten bleiben erhalten; Aliase dürfen Kategorie, Hersteller, Modell
  und Variante nicht überbrücken.
- Neu, gebraucht/neuwertig, beschädigt/ungetestet und unbekannt werden getrennt.
- Nullpreise und Quellenqualität null werden ausgeschlossen.
- Oberfläche und Bewertung nutzen dieselbe Vergleichsauswahl; Version,
  Ausschlussgründe und Beobachtungs-IDs werden in der Bewertung gespeichert.
- Alte Marktwerte bleiben in der Historie, erscheinen aber ohne Neubewertung
  nicht als aktuelle Top-Deals und werden nicht als belastbare ERP-Marktwerte exportiert.
  In der Detailansicht kann „Neu bewerten“ ohne KI ausgeführt werden.

Grenzen: konservative Texterkennung, keine vollständige Komponenten-Summenbewertung
für PCs/Bundles. Bei unklarem Umfang wird kein Einzelteil-Marktwert erfunden.
Manuell einem Angebot zugeordnete Verkäufe bleiben ausdrücklich Nutzerevidenz;
ihre Unabhängigkeit wird nicht extern verifiziert. Unbekannt-gegen-unbekannt bestätigt
keinen tatsächlich gleichen Zustand. Automatische Variantenerkennung ist noch nicht
für alle Kategorien vorhanden. Das Prüffenster ist auf 2000 jüngste Kandidaten begrenzt;
bei Erreichen wird dies in der Erklärung genannt. Frühere Bewertungen werden nicht
im Hintergrund massenhaft überschrieben.

Prüfstand dieser Ausbaustufe: 101 Python- und 24 TypeScript-Tests bestanden,
11 externe/PostgreSQL-Tests weiterhin übersprungen. Typprüfungen, Lint und
Produktionsbuild erfolgreich. Keine Live-Abnahme auf dem ThinkCentre erfolgt.

### Dritte Ausbaustufe: nachvollziehbare Beobachtungen

Erster Teil von P1.2 implementiert (`listing-findings-v1`):

- Detailansicht zeigt bis zu 20 jüngste Preisänderungen/Preisabweichungen mit
  Zeitstempel, Regelversion und aufklappbaren Belegen.
- Preisänderungen vergleichen den Gesamtpreis einschließlich erfasster
  Versandkosten. Alter/neuer Preis, Versand, Differenz, Prozent und beide
  Snapshot-IDs sind nachvollziehbar. Bei Ausgangspreis null wird keine Prozentzahl erfunden.
- Währungswechsel werden nicht als prozentuale Preisänderung ausgegeben.
- Eine Abweichung von mindestens 40 % zum Vergleichsmedian wird erst ab
  Datenqualität 60 und mit einer aktuellen, vergleichsgeprüften Bewertung angezeigt.
  Historische Bewertungen zu älteren Snapshots lösen keinen aktuellen Hinweis aus.
- Preisabweichung ist ausdrücklich kein Betrugsnachweis und verändert den
  Risiko-Score nicht. Es werden keine zusätzlichen Push-Nachrichten verschickt.
- Preisrückkehr A → B → A erzeugt einen neuen Snapshot/Grundauftrag; ein
  unveränderter Wiederholungsimport bleibt ohne zusätzlichen Auftrag.

Grenzen: Die Grenzwerte dieser sachlichen Hinweise sind zunächst versionierte
Serverregeln, noch keine separat konfigurierbaren Benachrichtigungsregeln.
Erweiterte Auffälligkeiten, Quellenstatus und optionales Push-Routing bleiben offen.
Ein leerer Hinweisbereich ist keine Bestätigung für Sicherheit oder vollständige Daten.

Prüfstand: 110 Python- und 24 TypeScript-Tests bestanden; 11 externe/PostgreSQL-Tests
übersprungen. Python-/TypeScript-Typprüfungen, Lint und Produktionsbuild erfolgreich.
Produktiver Windows-Betrieb und Last-/Restore-Abnahme bleiben ausstehend.

### Vierte Ausbaustufe: Dienstanmeldung mit Token-Erneuerung

Scheduler und Worker nutzen eine gemeinsame Anmeldekomponente. Optionaler
Supabase-Passwortlogin aus einer lokal geschützten Secret-Datei, getrennte Sitzungen
pro Prozess, automatische und serialisierte Refresh-Token-Rotation vor Ablauf.
Bei API-401 höchstens ein erneuter Versuch; keine automatischen Replays anderer
Schreibfehler. Abgelehnte Erneuerungen sperren die Sitzung bis zum bewussten Neustart.
API-Credentials gehen nicht an Ollama oder fremde Bildadressen.

Docker-Override, Windows-Einrichtung und Anmeldetest:
[Dienstanmeldung](service-auth.md). Die Passwortdatei ist nicht verschlüsselt,
aber vom Git-/Build-Kontext ausgeschlossen und nur in die beiden Dienste eingebunden.
Bestehende Benutzerrechte gelten unverändert; keine neue eingeschränkte Maschinenrolle.
Eine Sitzungserneuerung ist keine Garantie gegen Free-Tarif-Projektpausen.

Zusätzlich sind die schon verwendeten Extraction-Pakete und der asyncpg-Treiber
explizite Image-Abhängigkeiten. Prüfstand: 128 Python-Tests bestanden, 11 externe/
PostgreSQL-Tests übersprungen; Lint/Typprüfung erfolgreich, Images gebaut.
Windows-Passwortdatei und echte Supabase-Anmeldung noch nicht live abgenommen.

P0.1–P0.3 werden zunächst lokal implementiert und mit Regressionstests geprüft.
Erst danach wird P0.4 auf dem tatsächlichen ThinkCentre abgenommen. Der bisher genannte
RAM-Rahmen von ungefähr 1,5 GiB ist ein Budgetziel, kein gemessener Verbrauch dieses Stacks.
Container-Builds werden vorab erzeugt; parallele Browser und KI-Modelle laufen dort nicht.
Externe Datenbank-/Auth-Dienste dürfen beim Budget nicht als lokale Container mitgezählt werden.

## Deployment-Voraussetzungen

- LAN-IP/Hostname und freier Zugangspfad am vorhandenen Caddy.
- Docker-Netzwerk des vorhandenen Caddy und gewünschter interner/externer Zugriff.
- Produktionsfähige Authentifizierung und Datenbank mit Migrationen/RLS; der bestehende
  Entwicklungsmodus mit frei wählbarer Testidentität wird nicht ins LAN/Internet veröffentlicht.
- Workspace-Mitgliedschaft und gültige Worker-/Scheduler-Zugangsdaten.
- Backupziel und Festplattenspeicher; konkrete Restock-Produktlinks, falls gewünscht.

Ein lokaler Test oder erfolgreicher Build ersetzt weder Deployment noch Last-/Restore-Abnahme.
Native Tauri-Zugriffe auf eine neue Serverdomain benötigen außerdem eine passende CSP-Konfiguration.

## Prüfstand der ersten Ausbaustufe

- Python: 91 Tests bestanden; 11 Live-/PostgreSQL-Tests mangels freigegebener
  Zugangsdaten/Testdatenbank übersprungen.
- TypeScript: 24 Tests bestanden; Typprüfung erfolgreich.
- Python-Lint und Typprüfung der 59 Projekt-Quelldateien erfolgreich.
- Produktionsbuild der Oberfläche und Erweiterung erfolgreich.
- ThinkCentre-/Caddy-Compose-Zusammenführung syntaktisch geprüft.
- Web-Dockerimage lokal gebaut; Caddy-Konfiguration validiert und SPA-Route
  im isolierten Read-only-Container erfolgreich abgerufen.
- Kein Windows-Dauerlauf, kein produktiver Login-/RLS-Test und kein vollständiger
  Containerverbund auf dem ThinkCentre abgenommen.

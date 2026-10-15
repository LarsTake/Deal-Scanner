# Tracker und Scrapling: Analyse und Integration

Analysiert am 14.10.2026, jeweils als flacher lokaler Git-Checkout unter
`/private/tmp/deal-scanner-references/`:

- [Tracker](https://github.com/Restythecake/Tracker/tree/8ad8fbdf3671b55cd5f7aaed7d3dd934ba5e8727)
- [Scrapling](https://github.com/d4vinci/Scrapling/tree/7a684934907a8c7feaafe9ff1ccfd9d45cc26faf)

## Was die Referenzen machen

Tracker trennt Marktplatzquellen, Suchfilter, SQLite-Historie, Bewertungsregeln und
Benachrichtigungsadapter. Neue Suchen werden zuerst still eingelesen; danach werden neue
Angebote gemeldet. Neben eBay-API und HTML-Suchen unterstützt das Projekt u. a.
Kleinanzeigen, mydealz und Shop-Restock. Die Nest-Integration ergänzt eine Weboberfläche,
Widgets, manuelle Suchen, Archivierung und PC-Komponentenbewertungen. Die Marktwerte
kommen aus Preisbeobachtungen oder festen Hardwaretabellen.

Der HTTP-/Browser-Abruf in `ebay_tracker/sources/fetch.py` arbeitet mit einer geteilten
Browser-Session, Wartezeiten und zeitweisem Browser-Vorrang nach Sperren. Der Parser in
`sources/parsing.py` speichert Element-Fingerabdrücke und versucht bei geänderten CSS-Selektoren
ähnliche Karten wiederzufinden. `filters.py` gleicht Begriffe ohne störende Leer- und
Sonderzeichen ab. `tracker.py` und `storage.py` verhindern wiederholte Meldungen.

Scrapling ist eine allgemeine Bibliothek: `Selector` bietet CSS/XPath und adaptive
Elementerkennung; `SQLiteStorageSystem` speichert Fingerabdrücke pro Domain. HTTP-,
Browser- und Stealth-Fetcher sind zusätzliche Komponenten. Das Spider-System ergänzt
Warteschlangen, Checkpoints, Deduplizierung, robots.txt und Auto-Throttling. Deal Scanner
verwendet den Parser aus der Registry-Version **0.4.15**, nicht den Git-Checkout als Laufzeit.

## Übernahme in Deal Scanner

| Ansatz | Integration |
| --- | --- |
| Wiederkehrende Kleinanzeigen-Suche | Neuer `deal-scanner-kleinanzeigen-web`-Provider, optional im vorhandenen Scheduler |
| Robuste HTML-Erkennung | Scrapling-Selektoren für aktuelle und ältere Karten, persistente adaptive Fingerabdrücke |
| Validierung nach Selbstheilung | HTTPS, feste Kleinanzeigen-Domain, gültiger Anzeigenpfad, passende Anzeigen-ID, Titel und bekannter Preis |
| Schonender Abruf | Ein serieller Abruf je Provider, mindestens fünf Sekunden Abstand; 30 Minuten Pause nach 403/429/503 oder kleiner Challenge-Seite; längeres `Retry-After` wird berücksichtigt |
| Suchfilter unabhängig von Schreibweise | Pflicht-/Ausschlussbegriffe erkennen `RTX4070`, `RTX-4070` und `RTX 4070` |
| Dauerhafte Historie und Dubletten | Bestehende append-only Snapshots, Inhalts-Hashes, idempotente Imports und Analysejobs wiederverwendet |
| Preisänderungen | Neue Preise verändern den Inhalts-Hash und erzeugen eine neue analysierbare Momentaufnahme |
| Bedienung | Quellenwahl im Suchauftrag; bestehende Suchintervalle, Pausierung, Deal-/Risikoschwellen bleiben erhalten |
| Betrieb | Parser-Daten in `.data/scrapling`; persistentes Volume `parser-data` im Scheduler-Container |
| Stille Erstaufnahme | Geprüfter Suchlauf wird als Kontrollreferenz übergeben; erste Snapshots bleiben stumm, auch nach Neustarts. Spätere Preisänderungen können melden. |
| Sammelbenachrichtigungen | Mehr als fünf wartende Meldungen werden im Desktop-Polling bzw. ntfy-Dispatcher gebündelt. Fehlende native Zustellung wird nicht als Erfolg quittiert. |
| Archivierung | Konfigurierbare Altersgrenze (Standard 14 Tage) plus mindestens 48 Stunden nicht gesehen; Favoriten ausgenommen. Erneutes Auftauchen stellt automatisch Archiviertes wieder her, manuell Verborgenes bleibt verborgen. |
| Detailseiten | Höchstens fünf neue Detailabrufe pro Scan, eine Stunde Cache; Beschreibung, verifizierter Titel/Preis, Bilder und verfügbare Veröffentlichungsdaten. |
| Umkreissuche | PLZ-Auflösung über Kleinanzeigen, Cache im Providerprozess, unterstützte Radien zwischen 5 und 200 km; bei Zwischenwerten wird konservativ der kleinere Radius gewählt. |
| mydealz | Eigener Provider liest die strukturierten Deal-Daten der Suchseite, verwirft abgelaufene Deals, erfasst bekannte Versandkosten und prüft Suchwörter im Titel. |
| Vinted | Eigener Provider liest öffentliche Katalogkarten, erfasst Artikelpreis und sichtbare Käuferschutzgebühr getrennt und nutzt beide für den bekannten Preis. |
| Restock | Konfigurierbare Shop-Produktlinks, Schema.org-Produktdaten und persistente Verfügbarkeitszustände; Meldungen nur bei bestätigtem Wechsel auf verfügbar. |
| Browser-Modi | Optionaler Dynamic-/Stealth-Fetcher von Scrapling mit isoliertem Headless-Browser, beschränkter Navigation und deaktivierter automatischer Challenge-Lösung. |

Nest-spezifische Widgets werden nicht übernommen: Deal Scanner hat eine eigene Angular-/Tauri-
Oberfläche. Die vorhandene komponentenbezogene Bewertung, Marktpreis-Historie und Desktop-/ntfy-
Meldungen werden weiterverwendet. Neue Provider verwenden dieselbe Import- und Analysepipeline.

## Aktivierung

```bash
uv sync --all-packages --frozen
```

In `.env` `DEAL_SCANNER_KLEINANZEIGEN_WEB_ENABLED=true` setzen und den Scheduler neu starten.
In **Suchaufträge → Quellen** Kleinanzeigen wählen und den Auftrag speichern. Der Provider
ist in `.env.example` standardmäßig deaktiviert; eBay-API, E-Mail- und Browserimporte funktionieren weiter.
Für die zusätzlich gewünschten Marktplätze gelten `DEAL_SCANNER_MYDEALZ_WEB_ENABLED=true` und
`DEAL_SCANNER_VINTED_WEB_ENABLED=true`. Die lokale `.env` wurde für alle drei Webquellen aktiviert;
bestehende Suchaufträge wurden dabei nicht automatisch auf andere Marktplätze ausgeweitet.
In der Quellenwahl lassen sich mydealz und Vinted auswählen. Diese Quellen haben keinen
verifizierten Orts-/Radiusfilter und melden einen entsprechenden Konfigurationsfehler statt
eine ungefilterte geografische Suche vorzutäuschen. Noch unbekannte Versandkosten sind mit
`shippingKnown=false` markiert; bekannte Vinted-Käuferschutzkosten werden in den Preis einbezogen.
Nicht sichtbare Käuferschutzkosten werden nicht erfunden (`buyerProtectionKnown=false`).

Die Websuche liest nur die erste Suchergebnisseite. Sie liefert Titel, Kurzbeschreibung,
bekannten EUR-Preis, gegebenenfalls Standort und Bild-URL. Detailseiten werden standardmäßig
begrenzt nachgeladen (`DEAL_SCANNER_KLEINANZEIGEN_WEB_DETAILS_ENABLED=true`); der Browserimport
ergänzt weiterhin weitere Evidenz. Unbekannte VB-Preise werden nicht als Null-Euro-Angebote importiert;
explizit „Zu verschenken“ wird als 0 EUR erkannt. Suchprofile mit Ortsfilter werden lokal
gefiltert. Bei gesetztem Radius ist eine fünfstellige PLZ erforderlich; die Orts-ID und
der Radius werden direkt in die Marktplatzsuche eingebaut. Eine individuell berechnete
Entfernung oder Fahrtkostenschätzung wird nicht behauptet. Ein Veröffentlichungsdatum
wird nur aus expliziten Datumsfeldern gelesen: Bei aktivem Alterslimit qualifizieren undatierte Angebote nicht für
Benachrichtigungen. Marktwerte bleiben getrennt von den Angebotspreisen.

Der Scheduler führt nach jedem Zyklus die Archivpflege und den ntfy-Dispatcher aus. ntfy
versucht fehlgeschlagene Zustellungen höchstens dreimal; die Desktop-App fordert nur noch
ausstehende Desktop-Meldungen an. Unter **Suchaufträge** lassen sich Meldungen beim ersten
Lauf einschalten und die Archiv-Altersgrenze einstellen oder mit leerem Feld deaktivieren.
Archivierung ist wiederherstellbares Ausblenden, kein Löschen und keine Behauptung eines Verkaufs.
Bei Datumsangaben ohne Uhrzeit wird der Tagesbeginn in Europe/Berlin verwendet und als
`publishedAtPrecision=day` gekennzeichnet; die Altersprüfung bleibt dadurch konservativ.

## Shop-Restock

Unter **Einstellungen → Shop-Restock** lassen sich bis zu 20 Produktlinks von Otto,
MediaMarkt, Saturn, Amazon oder Müller speichern. Der Scheduler prüft höchstens fünf
fällige Produktseiten pro Zyklus; Erstaufnahme bleibt standardmäßig still. Unklare Daten,
Challenges, Weiterleitungen und Fehler gelten als **unbekannt**, nicht als bestätigte
Nichtverfügbarkeit. Ein unbekannter Zustand löscht den letzten bestätigten Zustand nicht.
Die Zustände überstehen API-/Scheduler-Neustarts in der vorhandenen Provider-Konfiguration.
Es werden keine Daten gelöscht und keine Bestellungen ausgelöst.

Ohne konkrete Produktlinks bleibt Restock deaktiviert. Es wurden keine Zelda-Produktlinks
aus Tracker stillschweigend übernommen. Die Shops müssen eindeutige Schema.org-Produkt-/
Angebotsdaten liefern; ein Live-Test der gewünschten Produkte ist nach deren Auswahl nötig.

## Optionale Browser-Laufzeit

Der aktuelle HTTP-Modus hat auf allen drei Marktplätzen erfolgreich funktioniert. Falls ein
Marktplatz später gerenderte Seiten benötigt, sind `browser` und `stealth` wählbar:

```bash
uv sync --all-packages --extra browser
uv run scrapling install
```

Danach in `.env` `DEAL_SCANNER_WEB_FETCH_MODE=browser` oder `stealth` setzen und Scheduler
neu starten. Browser-Anfragen dürfen nur GET/HEAD auf den festgelegten Marktplatz-Hosts
ausführen; fremde Navigation und Ressourcen werden blockiert. Automatische Cloudflare-/
CAPTCHA-Lösung bleibt ausgeschaltet. Sperren führen weiterhin zur Pause. Die optionale
Browser-Binärlaufzeit wurde nicht installiert oder live geprüft; die Adapter-Verträge und
die Navigationsgrenze wurden mit Test-Fetchern geprüft. Docker braucht für diese Modi einen
entsprechend erweiterten Build mit Browser-Laufzeit; der Standardcontainer bleibt HTTP-basiert.

## Lizenzen

Im untersuchten Tracker-Checkout existiert keine erkennbare Lizenzdatei. Es wurde kein
Tracker-Quellcode übernommen; die Integration implementiert die beschriebenen Ansätze
eigenständig. Scrapling ist BSD-3-Clause-lizenziert und wird als normale gesperrte
Python-Abhängigkeit installiert. Bei Weitergabe einer gebündelten Bibliothek gelten die
Hinweis- und Lizenzpflichten ihrer Distribution.

## Prüfungen

Tests decken aktuelle Karten, Preisreduktion, Duplikate, Gratisangebote, unbekannte Preise,
Layoutfehler, adaptive Wiedererkennung, externe/manipulierte Links, Inhalts-Hashes,
Preisfilter, Sperrpausen, Größenlimits und den vollständigen Scheduler-Importablauf ab.
Ergänzende Tests prüfen stille Erstläufe, wiederholte Snapshots, spätere Preisänderungen,
Archivierung/Favoriten/manuelle Entscheidungen, ntfy-Bündelung, PLZ-Suchen und Detail-Caches.
Am 14.10.2026 wurden 26 Angebote aus einer echten Suchseite erfolgreich erkannt; drei davon
wurden in einer isolierten In-Memory-Datenbank importiert und regelbasiert analysiert.
Ein separater Durchlauf bestätigte die tatsächliche Detailanreicherung. Die Erstaufnahme
erzeugte keine Benachrichtigungen. Es wurden keine echten ntfy-/Desktop-Pushs verschickt.
Zusätzliche Live-Suchabrufe am selben Tag lieferten 30 mydealz- und 96 Vinted-Angebote.
Vinted verwendet dafür ein weiterhin begrenztes 8-MiB-Antwortlimit. Beide neuen Parser,
die Quellen-/Bildhost-Grenzen und die Gebührennormalisierung sind zusätzlich fixture-basiert geprüft.

Reproduzierbarer Live-Smoke (öffentlicher Abruf, lokaler Testzustand wird verworfen):

```bash
uv run python infrastructure/scripts/smoke-kleinanzeigen-live.py --limit 3 --details
```

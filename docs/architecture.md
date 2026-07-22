# Architektur

## Grenzen

- `deal_scanner_core` enthält Verträge und Domänentypen ohne Infrastrukturabhängigkeiten.
- `deal_scanner_extraction` normalisiert Produktnamen und extrahiert evidenzbasierte Signale.
- `deal_scanner_scoring` berechnet Marktwerte sowie getrennte Deal- und Risiko-Scores.
- Provider implementieren `ListingProvider`; API, Scheduler und Worker konsumieren nur das Port.
- FastAPI ist die einzige öffentliche Daten-API. Supabase Auth stellt Identitäten bereit,
  Supabase PostgreSQL und RLS sichern die Workspace-Grenze zusätzlich ab.

## Datenfluss

1. Ein Provider erzeugt einen unveränderten `RawListingSnapshot`.
2. Der Snapshot wird gehasht, append-only gespeichert und anschließend normalisiert.
3. Ein idempotenter Analysejob referenziert Snapshot und Berechnungsversion.
4. Regeln laufen vor einem optionalen Modell. Modellergebnisse müssen das versionierte Schema erfüllen.
5. Marktwert, Deal-Score und Risiko-Score werden getrennt persistiert.
6. Feedback erzeugt neue Ereignisse und niemals rückwirkende Änderungen an Analysehistorie.

## Entscheidungen

- SQL-Migrationen in `infrastructure/supabase/migrations` sind die einzige Schemaquelle.
- JSON-Wire-Modelle sind camelCase; Python bleibt intern snake_case.
- Geldbeträge werden als Decimal/NUMERIC übertragen und gespeichert.
- SQLite dient ausschließlich dem lokalen Entwicklungs- und Offlinepfad.

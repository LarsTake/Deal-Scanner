# Deal Scanner erweitern

## Neue Kategorie

1. Ein versioniertes YAML-Profil in `packages/python/extraction/src/deal_scanner_extraction/profiles`
   ergänzen. Produkttypen, Attribute, Aliase, Vollständigkeit, Risiko- und Scoringgewichte gehören
   in das Profil, nicht in die UI.
2. Kanonische Aliase und eindeutige Normalisierungs-Fixtures ergänzen.
3. Profilvalidierung, Extraktion und Scoring mit Tests absichern.
4. Nur wenn sich der Wire-Vertrag ändert: OpenAPI exportieren und TypeScript-Verträge erzeugen.

## Neuer Listing-Provider

1. Den `ListingProvider`-Port aus `packages/python/core` implementieren: `discover`,
   `fetch_details`, `normalize`, `health_check`.
2. Rohantworten unverändert als Snapshot-Payload erhalten. Die Normalisierung darf weder Marktwert
   noch KI-Ergebnisse erfinden.
3. Cursor, Rate-Limits, Retry/Backoff, Fehlerklassen und Idempotenz festlegen.
4. Scheduler-Konfiguration und Provider-Health ergänzen, ohne Secrets in API-Antworten oder Logs
   auszugeben.
5. Provider-Contract-Tests mit gespeicherten Fixtures hinzufügen; Live-Smokes separat über ein
   explizites Environment-Flag schalten.

## Neues Analysemodell

1. Den `AIProvider`-Port implementieren und Capabilities sowie Modellversion melden.
2. Ausgabe ausschließlich gegen das aktuelle versionierte Schema in `schemas/` akzeptieren.
3. Prompt und Promptversion gemeinsam ändern; unbekannte Werte bleiben `null`, Evidenz und Quelle
   bleiben Pflicht.
4. Worker-Auswahl, Health-Anzeige und falsche/abgebrochene Antworten testen. Cloud-Adapter bleiben
   standardmäßig deaktiviert und benötigen eine ausdrückliche Konfiguration.

## Neuer Benachrichtigungs- oder ERP-Adapter

Benachrichtigungen implementieren den gemeinsamen Adapter und speichern jeden Zustellversuch. Ein
Adapter entscheidet nicht selbst über Deal-/Risikoschwellen. ERP-Adapter implementieren
`exportListingAsPurchase`; Mappingfehler müssen als fachliche Problem-Response sichtbar bleiben.
Der bestehende ntfy- beziehungsweise Mock-Adapter dient als Referenz.

## Änderungs-Checkliste

- Migration ausschließlich als neue Supabase-SQL-Datei, niemals durch paralleles Alembic-Schema.
- RLS, Grants, Audit und Secret-Redaction für neue Datenwege prüfen.
- Python-Lint/Typen/Tests sowie TypeScript-Test/Typecheck/Build ausführen.
- OpenAPI/Contracts bei Vertragsänderungen neu erzeugen und Drift prüfen.
- Betriebs-, Sicherheits- und Abnahmedokumentation aktualisieren.

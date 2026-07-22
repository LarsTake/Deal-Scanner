# Datenmodell und API

## Datenmodell

`workspace_id` ist die Mandantengrenze. PostgreSQL-RLS prüft für alle fachlichen Tabellen die
transaktionslokal gesetzten Benutzerclaims. `workspaces` und `workspace_members` bilden die
Zuordnung; eine spätere ERP-Mandanten-ID liegt am Workspace.

| Bereich | Tabellen | Lebenszyklus |
|---|---|---|
| Suche/Import | `search_profiles`, `provider_configurations`, `provider_sync_runs`, `mail_imports` | Konfiguration veränderbar, Läufe und Mailnachweise historisch |
| Angebot | `listings`, `listing_snapshots`, `sellers`, `listing_images` | Listing zeigt auf aktuellen Stand; Snapshots sind append-only |
| Produkt | `canonical_products`, `product_aliases`, `listing_products`, `product_attributes` | Katalog erweiterbar; Erkennungen je Analyse nachvollziehbar |
| Markt/Score | `price_observations`, `market_value_estimates`, `risk_signals`, `deal_evaluations` | jede Berechnung erzeugt eine versionierte neue Zeile |
| Analyse | `analysis_jobs`, `workers`, `analysis_results` | Lease-Zustandsautomat; Ergebnisse per Job/Input-Hash dedupliziert |
| Interaktion | `user_feedback`, `notifications`, `notification_deliveries`, `extension_pairings` | Feedback/Auslieferungen historisch; Tokens nur gehasht |
| Nachweis | `audit_events`, `idempotency_keys` | Audit append-only; Idempotenzschlüssel zeitlich begrenzt |

Geld wird als `numeric(14,2)` mit ISO-4217-Währung gespeichert. Externe IDs sind pro
`(workspace_id, platform, external_id)` eindeutig. Historische Snapshots, Analyseergebnisse und
Audit-Ereignisse dürfen nicht aktualisiert oder gelöscht werden; Datenbank-Trigger erzwingen dies.
Das vollständige physische Schema ist in den Supabase-Migrationen definiert.

## HTTP-Vertrag

Die API liegt unter `/api/v1`. Wire-Daten verwenden camelCase, UUIDs, RFC-3339/UTC und
Dezimalbeträge als Strings. Listen verwenden Cursor-Pagination. Import-Endpunkte akzeptieren
`Idempotency-Key`; Fehler folgen RFC 9457 (`application/problem+json`).

Die wichtigsten Bereiche sind:

- Identität und Workspaces: `/auth/me`, `/workspaces`
- Suchprofile und Provider: `/search-profiles`, `/provider-configurations`, `/provider-sync-runs`
- Listings und Analyse: `/listings`, `/listings/{id}/reanalyze`, `/listings/{id}/feedback`
- Imports und Markt: `/imports/*`, `/products`, `/price-observations`, `/market-data/imports/csv`
- Worker: `/workers/*`, `/jobs/claim`, `/jobs/{id}/*`
- Integrationen: `/extension/pairings`, `/erp/exports`, `/notifications`
- Betrieb: `/health/live`, `/health/ready`, `/system/status`

Im laufenden Entwicklungsserver sind Swagger UI unter `/docs`, ReDoc unter `/redoc` und der
OpenAPI-Vertrag unter `/openapi.json` erreichbar. Die versionierte Kopie liegt in
`schemas/openapi.json`. `pnpm openapi:export` und `pnpm contracts:generate` erzeugen daraus Client
und Wire-Typen; `pnpm contracts:check` schlägt bei Drift fehl.

## Authentifizierung und Rollen

Web und Desktop senden ein Supabase-JWT. Die API validiert es lokal über JWKS und setzt Subject,
Rolle und Workspace für die Datenbanktransaktion. Service-Schlüssel werden ausschließlich in
Serverumgebungen gehalten. Der lokale Entwicklungsnutzer ist nur erlaubt, wenn der
Produktionsmodus deaktiviert ist. Private Storage-Objekte werden über kurzlebige signierte URLs
ausgeliefert.

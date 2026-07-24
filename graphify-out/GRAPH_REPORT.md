# Graph Report - Graper  (2026-07-24)

## Corpus Check
- 175 files · ~98,477 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1218 nodes · 2422 edges · 105 communities (91 shown, 14 thin omitted)
- Extraction: 80% EXTRACTED · 20% INFERRED · 0% AMBIGUOUS · INFERRED: 485 edges (avg confidence: 0.64)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 82|Community 82]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 85|Community 85]]
- [[_COMMUNITY_Community 86|Community 86]]
- [[_COMMUNITY_Community 87|Community 87]]
- [[_COMMUNITY_Community 88|Community 88]]
- [[_COMMUNITY_Community 89|Community 89]]
- [[_COMMUNITY_Community 90|Community 90]]
- [[_COMMUNITY_Community 91|Community 91]]
- [[_COMMUNITY_Community 96|Community 96]]
- [[_COMMUNITY_Community 97|Community 97]]

## God Nodes (most connected - your core abstractions)
1. `CamelModel` - 82 edges
2. `select()` - 53 edges
3. `str` - 49 edges
4. `DealScannerClient` - 35 edges
5. `Base` - 30 edges
6. `import_listing()` - 22 edges
7. `OllamaProvider` - 20 edges
8. `EbayProvider` - 20 edges
9. `Scheduler` - 19 edges
10. `Settings` - 19 edges

## Surprising Connections (you probably didn't know these)
- `test_scheduler_selects_ebay_credentials_for_the_effective_environment()` --calls--> `SchedulerSettings`  [INFERRED]
  tests/test_security.py → apps/scheduler/src/deal_scanner_scheduler/main.py
- `test_worker_reconnects_after_transient_api_failure()` --calls--> `WorkerSettings`  [INFERRED]
  tests/test_worker_agent.py → apps/analysis-worker/src/deal_scanner_worker/main.py
- `RiskReview` --uses--> `CamelModel`  [INFERRED]
  apps/analysis-worker/src/deal_scanner_worker/ollama.py → packages/python/core/src/deal_scanner_core/models.py
- `VisionText` --uses--> `CamelModel`  [INFERRED]
  apps/analysis-worker/src/deal_scanner_worker/ollama.py → packages/python/core/src/deal_scanner_core/models.py
- `OllamaProvider` --uses--> `CamelModel`  [INFERRED]
  apps/analysis-worker/src/deal_scanner_worker/ollama.py → packages/python/core/src/deal_scanner_core/models.py

## Communities (105 total, 14 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.08
Nodes (64): CamelModel, AnalysisResultResponse, AuthMeResponse, ComponentHealth, CorrectedAttributeInput, CorrectedProductInput, CsvImportResponse, DealEvaluationHistoryResponse (+56 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (41): DevelopmentIdentityProvider, get_identity(), get_identity_provider(), Identity, IdentityProvider, SupabaseIdentityProvider, get_browser_request_context(), get_request_context() (+33 more)

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (29): AiRiskSignal, AnalysisStatus, Contradiction, DetectedAttribute, ImageOcrResult, ListingStatus, ModelProviderStatus, NormalizedListing (+21 more)

### Community 3 - "Community 3"
Cohesion: 0.11
Nodes (41): BaseModel, AuditEventRow, EbayAccountDeletionEventRow, ListingImageRow, ListingRow, ListingSnapshotRow, PriceObservationRow, SellerRow (+33 more)

### Community 4 - "Community 4"
Cohesion: 0.1
Nodes (9): ApiProblemError, ApiResult, ClientOptions, createGeneratedDealScannerClient(), DealScannerClient, GeneratedDealScannerClient, client, fetchMock (+1 more)

### Community 5 - "Community 5"
Cohesion: 0.08
Nodes (18): BaseSettings, _body(), _first_image(), KleinanzeigenMailParser, ParsedMail, extract_ebay_legacy_id(), _api_datetime(), _ebay_image_urls() (+10 more)

### Community 6 - "Community 6"
Cohesion: 0.09
Nodes (25): require_identifier(), validate_prices(), validate_security_mode(), DealScannerError, LeaseConflict, ProviderError, ProviderRateLimited, Base error safe to map to a structured API problem. (+17 more)

### Community 7 - "Community 7"
Cohesion: 0.12
Nodes (30): apiUnavailable(), config, Configuration, failure(), handleImport(), importVisibleListings(), responseProblem(), results (+22 more)

### Community 8 - "Community 8"
Cohesion: 0.09
Nodes (8): AuthService, runsInTauri(), ExtensionLoopbackService, LoopbackPairing, resolveDevelopmentUserId(), runsInTauri(), LoginPage, SettingsPage

### Community 9 - "Community 9"
Cohesion: 0.12
Nodes (31): record_audit_event(), ExtensionPairingRow, MailImportRow, ProviderSyncRunRow, select(), create_observation(), mark_desktop_notification_delivered(), notifications() (+23 more)

### Community 10 - "Community 10"
Cohesion: 0.06
Nodes (10): cachedError(), connection(), constructor(), readable(), simple(), timer(), user, v (+2 more)

### Community 11 - "Community 11"
Cohesion: 0.06
Nodes (33): components, $defs, operations, paths, webhooks, AnalysisJob, CsvImport, ExtensionConnection (+25 more)

### Community 12 - "Community 12"
Cohesion: 0.1
Nodes (28): challengeResponse(), config, database(), decodeBase64Strict(), deletePrivateImages(), errorName(), fetchAccessToken(), fetchPublicKey() (+20 more)

### Community 13 - "Community 13"
Cohesion: 0.1
Nodes (21): ProductDetection, listing_text_fingerprint(), listing_text_similarity(), normalize_listing_text(), Create a locale-independent representation for duplicate comparison., normalize_text(), ProductRule, RiskRule (+13 more)

### Community 14 - "Community 14"
Cohesion: 0.19
Nodes (21): estimate_listing_market(), DealScoreEngine, MarketValueEngine, _median(), RiskScoreEngine, _weighted_quantile(), DealScoreInput, DealScoreResult (+13 more)

### Community 15 - "Community 15"
Cohesion: 0.17
Nodes (6): ApiService, CatalogPage, DashboardPage, PlaceholderPage, SystemPage, WorkersPage

### Community 16 - "Community 16"
Cohesion: 0.19
Nodes (21): AnalysisResultRow, Base, CanonicalProductRow, ListingProductRow, ProductAliasRow, ProductAttributeRow, ProviderConfigurationRow, SearchProfileRow (+13 more)

### Community 17 - "Community 17"
Cohesion: 0.15
Nodes (18): add_erp_image(), payload(), set_job_times(), test_authenticated_permanent_extension_connection_can_be_used_and_revoked(), test_end_to_end_import_feedback_and_worker_lease(), test_erp_mock_uses_stable_purchase_contract(), test_evaluation_keeps_risk_separate_and_creates_notification(), test_idempotency_and_extension_pairing() (+10 more)

### Community 18 - "Community 18"
Cohesion: 0.15
Nodes (19): AnalysisJobRow, IdempotencyKeyRow, import_listing(), latest_evaluation(), listing_summary(), request_content_hash(), upsert_seller(), validate_import_url() (+11 more)

### Community 19 - "Community 19"
Cohesion: 0.15
Nodes (14): ActiveLoopback, forward(), forward_preserves_auth_idempotency_status_and_body(), is_uuid_like(), LoopbackController, LoopbackPairing, problem(), proxy_browser_import() (+6 more)

### Community 20 - "Community 20"
Cohesion: 0.16
Nodes (8): AppComponent, appConfig, routes, DesktopNotificationService, ICON_PATHS, NavIconComponent, NavIconName, NotificationPollingService

### Community 21 - "Community 21"
Cohesion: 0.21
Nodes (8): isConflictError(), OutboxItem, OutboxKind, processOutboxItems(), conflicted, delivered, sender, OutboxSyncService

### Community 22 - "Community 22"
Cohesion: 0.26
Nodes (11): DealEvaluationRow, MarketValueEstimateRow, NotificationDeliveryRow, NotificationRow, _deal_component_scores(), evaluate_listing_record(), EvaluationOutcome, _send_ntfy() (+3 more)

### Community 23 - "Community 23"
Cohesion: 0.14
Nodes (15): code:powershell ($env:DEAL_SCANNER_POSTGRES_BIN='C:\Pfad\zu\pgsql\bin'), code:text (https://<öffentliche-domain>/api/v1/webhooks/ebay/account-de), code:dotenv (DEAL_SCANNER_EBAY_ENVIRONMENT=production), code:dotenv (DEAL_SCANNER_IMAP_HOST=imap.example.de), code:powershell ($env:DEAL_SCANNER_RUN_LIVE_TESTS='1'), Credential-gesteuerte Live-Abnahme, Desktop-Signierung und Notarisierung, E-Mail und Browser-Erweiterung (+7 more)

### Community 24 - "Community 24"
Cohesion: 0.17
Nodes (15): database(), decodeBase64Strict(), deletePrivateImages(), errorName(), handleChallenge(), handleNotification(), handler(), isVerificationToken() (+7 more)

### Community 26 - "Community 26"
Cohesion: 0.29
Nodes (13): RiskSignalRow, claim_job(), complete_job(), fail_job(), heartbeat(), _job_response(), _leased_job(), list_jobs() (+5 more)

### Community 27 - "Community 27"
Cohesion: 0.32
Nodes (9): str, import_csv(), test_ebay_deletion_audit_is_private_and_append_only_exception_is_owner_only(), test_extension_pairing_resolver_accepts_persistent_tokens_until_revoked(), test_postgres_skip_locked_allows_only_one_concurrent_job_claim(), test_private_storage_policy_uses_workspace_path(), test_rls_isolates_two_personal_workspaces(), _visible_workspaces() (+1 more)

### Community 30 - "Community 30"
Cohesion: 0.22
Nodes (8): 1. Öffentlicher Betrieb hinter Cloudflare, 2. Komponentenbezogene Marktpreis-Referenzen, Ausbau-Roadmap, Bewertungslogik und Oberfläche, Daten und Herkunft, Offene Produktentscheidung, Quellenstrategie, Umsetzungspakete

### Community 32 - "Community 32"
Cohesion: 0.25
Nodes (8): challengeResponse(), closeDatabaseConnection(), end(), hmac(), md5(), sha256(), update(), verifyEbaySignature()

### Community 33 - "Community 33"
Cohesion: 0.25
Nodes (8): forEach(), osUsername(), parseOptions(), parseTransform(), parseUrl(), postgres(), Subscribe(), tsa()

### Community 34 - "Community 34"
Cohesion: 0.29
Nodes (7): code:bash (cp .env.example .env), code:bash (brew install uv rustup), code:powershell (Copy-Item .env.example .env), code:powershell (uv run pytest), Deal Scanner, Qualitätsprüfungen, Schnellstart

### Community 35 - "Community 35"
Cohesion: 0.38
Nodes (4): ApiTarget, validateApiTarget(), apiUrl, value

### Community 36 - "Community 36"
Cohesion: 0.29
Nodes (4): MockErpIntegrationAdapter, Stable ERP boundary; replace this adapter without changing the REST contract., Stable ERP boundary; replace this adapter without changing the REST contract., mock_erp_export()

### Community 37 - "Community 37"
Cohesion: 0.29
Nodes (6): build(), escapeIdentifiers(), insert(), values(), valuesBuilder(), main()

### Community 38 - "Community 38"
Cohesion: 0.29
Nodes (6): Deal Scanner erweitern, Neue Kategorie, Neuer Benachrichtigungs- oder ERP-Adapter, Neuer Listing-Provider, Neues Analysemodell, Änderungs-Checkliste

### Community 39 - "Community 39"
Cohesion: 0.47
Nodes (3): FileAccessService, runsInTauri(), SelectedTextFile

### Community 40 - "Community 40"
Cohesion: 0.47
Nodes (6): catch(), execute(), finally(), handle(), notTagged(), then()

### Community 41 - "Community 41"
Cohesion: 0.4
Nodes (6): firstIsString(), fragment(), generic(), handleValue(), stringify(), stringifyValue()

### Community 42 - "Community 42"
Cohesion: 0.4
Nodes (5): Betrieb, code:powershell ($env:DEAL_SCANNER_DOMAIN='api.example.de'), code:powershell ($env:DEAL_SCANNER_SUPABASE_DB_URL='postgresql://...'), code:powershell ($env:PGDATABASE='postgresql://.../deal_scanner_restore_test'), Sicherung und Wiederherstellung

### Community 46 - "Community 46"
Cohesion: 0.4
Nodes (4): Architektur, Datenfluss, Entscheidungen, Grenzen

### Community 47 - "Community 47"
Cohesion: 0.4
Nodes (4): Authentifizierung und Rollen, Datenmodell, Datenmodell und API, HTTP-Vertrag

### Community 50 - "Community 50"
Cohesion: 0.5
Nodes (4): fit(), i16(), i32(), z()

### Community 51 - "Community 51"
Cohesion: 0.5
Nodes (3): Abnahme und externe Voraussetzungen, Lokal reproduzierbar, Nur mit bereitgestellten externen Zugängen prüfbar

### Community 52 - "Community 52"
Cohesion: 0.5
Nodes (3): Answer, Q: Trace the existing end-to-end flow from listing import through analysis result, canonical product matching, market value evaluation, and notification. Identify the exact missing connections., Source Nodes

### Community 53 - "Community 53"
Cohesion: 0.5
Nodes (3): Answer, Q: Which explicit Deal Scanner requirements in the specification are missing, only stubbed, or lack direct verification in the current repository?, Source Nodes

### Community 54 - "Community 54"
Cohesion: 0.5
Nodes (3): Answer, Q: Which improved Deal Scanner plan requirements still lack direct implementation or executable verification evidence? Focus on CI, Docker Compose, Supabase RLS/storage, cross-platform release, OpenAPI drift, and live-smoke gates., Source Nodes

### Community 55 - "Community 55"
Cohesion: 0.5
Nodes (3): Answer, Q: Which explicit requirements in the improved Deal Scanner plan remain unimplemented rather than merely unverified externally? Focus on Tauri loopback, token storage, SQLite offline cache, platform build workflows, storage signed URLs, SSRF, CSP, notification channels, and image OCR., Source Nodes

### Community 56 - "Community 56"
Cohesion: 0.5
Nodes (3): Answer, Q: Which original Deal Scanner requirements beyond the 20-point MVP are directly evidenced, and which lack nodes or paths: browser inline deal-score overlay and known-listing detection, normalized text fingerprint duplicate detection, health status for email/eBay/Ollama/storage, database backup, image prioritization, similar complete-PC market comparison, distance/fahrtkosten/platform fees, and seller/image ERP export fields?, Source Nodes

### Community 57 - "Community 57"
Cohesion: 0.5
Nodes (3): Answer, Q: Which requirements from the Deal Scanner implementation plan still have no direct implementation or test evidence, focusing on health statuses, backups, duplicate fingerprints, market comparison costs, image processing, ERP fields, offline conflict handling, and provider integration?, Source Nodes

### Community 58 - "Community 58"
Cohesion: 0.5
Nodes (3): Answer, Q: How are normalized listing text fingerprints and duplicate-description risk signals connected to the listing import pipeline and its tests?, Source Nodes

### Community 59 - "Community 59"
Cohesion: 0.5
Nodes (3): Answer, Q: Welche externen Zugangsdaten oder API-Schluessel werden fuer die noch offene Live-Abnahme benoetigt?, Source Nodes

### Community 60 - "Community 60"
Cohesion: 0.5
Nodes (3): Answer, Q: Was ist nach installierter Supabase CLI und beantragtem eBay API Zugang der naechste offene Einrichtungsschritt?, Source Nodes

### Community 61 - "Community 61"
Cohesion: 0.5
Nodes (3): Answer, Q: Wie wird das Deal-Scanner-Repository mit dem gehosteten Supabase-Projekt verknuepft?, Source Nodes

### Community 62 - "Community 62"
Cohesion: 0.5
Nodes (3): Answer, Q: Wie ist der Stand der gehosteten Supabase-Einrichtung fuer Deal Scanner?, Source Nodes

### Community 63 - "Community 63"
Cohesion: 0.5
Nodes (3): Answer, Q: Wurde die gehostete Supabase-RLS- und Storage-Konfiguration erfolgreich geprueft?, Source Nodes

### Community 64 - "Community 64"
Cohesion: 0.5
Nodes (3): Answer, Q: Soll Deal Scanner sensible APIs hinter einem Cloudflare Worker verstecken?, Source Nodes

### Community 65 - "Community 65"
Cohesion: 0.5
Nodes (3): Answer, Q: Wie sollen aktuelle Komponentenpreise und Cloudflare in den Ausbauplan aufgenommen werden?, Source Nodes

### Community 66 - "Community 66"
Cohesion: 0.5
Nodes (3): Answer, Q: Ist eine lokal funktionsfähige Deal-Scanner-Version erreicht und welche Laufzeitblocker mussten behoben werden?, Source Nodes

### Community 67 - "Community 67"
Cohesion: 0.5
Nodes (3): Answer, Q: Wie werden Kleinanzeigen-Angebote automatisch erfasst und wie wird Ollama fuer die Analyse aktiviert?, Source Nodes

### Community 68 - "Community 68"
Cohesion: 0.5
Nodes (3): Answer, Q: Warum war die installierte Tauri-App unformatiert und wie wurde sie korrigiert?, Source Nodes

### Community 69 - "Community 69"
Cohesion: 0.5
Nodes (3): Answer, Q: Wie wird der automatische Gmail-Import fuer Kleinanzeigen sicher aktiviert?, Source Nodes

### Community 70 - "Community 70"
Cohesion: 0.5
Nodes (3): Answer, Q: Was ist nach der aktuellen Einrichtung als Naechstes zu tun?, Source Nodes

### Community 71 - "Community 71"
Cohesion: 0.5
Nodes (3): Answer, Q: Gibt es schon eine Chrome Extension?, Source Nodes

### Community 72 - "Community 72"
Cohesion: 0.5
Nodes (3): Answer, Q: Warum konnte die Loopback-Kopplung in der installierten Desktop-App nicht gestartet werden?, Source Nodes

### Community 73 - "Community 73"
Cohesion: 0.5
Nodes (3): Answer, Q: Was bedeutet der Screenshotfehler invalid or expired pairing token beim Browser-Import?, Source Nodes

### Community 74 - "Community 74"
Cohesion: 0.5
Nodes (3): Answer, Q: Warum wurde ein Kleinanzeigen-Angebot importiert, der Bildimport aber mit 502 beendet, und kann die Erweiterung alle Angebote einer Ergebnisseite importieren?, Source Nodes

### Community 75 - "Community 75"
Cohesion: 0.5
Nodes (3): Answer, Q: Warum zeigt die Erweiterung auf der gespeicherten Kleinanzeigen-Suche Keine sichtbaren Angebote?, Source Nodes

### Community 76 - "Community 76"
Cohesion: 0.5
Nodes (3): Answer, Q: Welche lokalen Ollama-Modelle sollten fuer Deal Scanner auf RTX 4070 SUPER 12 GB und 32 GB RAM nach Aufgabentyp eingesetzt werden?, Source Nodes

### Community 77 - "Community 77"
Cohesion: 0.5
Nodes (3): Answer, Q: Werden bereits Duplikate erkannt und gibt es permanente Connections?, Source Nodes

### Community 78 - "Community 78"
Cohesion: 0.5
Nodes (3): Answer, Q: Ist das Projekt bereits in einem Git-Repository mit GitHub-Remote, und welche macOS-Build-, Signierungs- und Installationswege sind vorhanden?, Source Nodes

### Community 79 - "Community 79"
Cohesion: 0.5
Nodes (3): Answer, Q: Wie wird eine dauerhafte, durch Anmeldedaten gesicherte Browser-Verbindung umgesetzt?, Source Nodes

### Community 80 - "Community 80"
Cohesion: 0.5
Nodes (3): Answer, Q: Sind jetzt schon User-Accounts angelegt, mit denen man auf unterschiedlichen Geräten arbeiten kann?, Source Nodes

### Community 81 - "Community 81"
Cohesion: 0.5
Nodes (3): Answer, Q: How is the eBay provider configured, and where should sandbox credentials be placed?, Source Nodes

### Community 82 - "Community 82"
Cohesion: 0.5
Nodes (3): Answer, Q: Which eBay APIs, OAuth credentials, and permissions does Graper currently need, and what would require additional access?, Source Nodes

### Community 83 - "Community 83"
Cohesion: 0.5
Nodes (3): Answer, Q: Does Graper implement eBay marketplace account deletion notifications, endpoint verification, and deletion of stored eBay user data?, Source Nodes

### Community 84 - "Community 84"
Cohesion: 0.5
Nodes (3): Answer, Q: How is Graper intended to be deployed publicly with HTTPS, and where should an eBay webhook endpoint be added?, Source Nodes

### Community 85 - "Community 85"
Cohesion: 0.5
Nodes (3): Answer, Q: Wo muss ein öffentlicher eBay Marketplace Account Deletion Webhook in Graper integriert werden, damit signierte Benachrichtigungen Verkäuferdaten sicher löschen?, Source Nodes

### Community 86 - "Community 86"
Cohesion: 0.5
Nodes (3): Answer, Q: Kann Grapers eBay Marketplace Account Deletion Endpoint sinnvoll auf Netlify betrieben werden, oder benötigt er die bestehende FastAPI- und Datenbank-Laufzeit?, Source Nodes

### Community 88 - "Community 88"
Cohesion: 0.67
Nodes (3): fetchAccessToken(), fetchPublicKey(), normalizePublicKey()

## Knowledge Gaps
- **181 isolated node(s):** `ApiTarget`, `listing`, `config`, `fetchMock`, `[listing]` (+176 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `str` connect `Community 27` to `Community 1`, `Community 2`, `Community 3`, `Community 36`, `Community 5`, `Community 6`, `Community 9`, `Community 10`, `Community 14`, `Community 16`, `Community 17`, `Community 50`, `Community 18`, `Community 22`, `Community 26`?**
  _High betweenness centrality (0.105) - this node is a cross-community bridge._
- **Why does `select()` connect `Community 9` to `Community 0`, `Community 1`, `Community 3`, `Community 36`, `Community 37`, `Community 10`, `Community 14`, `Community 16`, `Community 18`, `Community 22`, `Community 26`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Why does `CamelModel` connect `Community 0` to `Community 2`, `Community 3`, `Community 6`, `Community 13`, `Community 14`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Are the 68 inferred relationships involving `CamelModel` (e.g. with `RiskReview` and `VisionText`) actually correct?**
  _`CamelModel` has 68 INFERRED edges - model-reasoned connections that need verification._
- **Are the 51 inferred relationships involving `select()` (e.g. with `get_request_context()` and `get_browser_request_context()`) actually correct?**
  _`select()` has 51 INFERRED edges - model-reasoned connections that need verification._
- **Are the 47 inferred relationships involving `str` (e.g. with `.process_one()` and `._renew_while_running()`) actually correct?**
  _`str` has 47 INFERRED edges - model-reasoned connections that need verification._
- **What connects `ApiTarget`, `listing`, `config` to the rest of the system?**
  _181 weakly-connected nodes found - possible documentation gaps or missing edges._
# Graph Report - Graper  (2026-07-22)

## Corpus Check
- 105 files · ~63,097 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 676 nodes · 1370 edges · 48 communities (34 shown, 14 thin omitted)
- Extraction: 83% EXTRACTED · 17% INFERRED · 0% AMBIGUOUS · INFERRED: 232 edges (avg confidence: 0.6)
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
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]

## God Nodes (most connected - your core abstractions)
1. `CamelModel` - 73 edges
2. `Base` - 29 edges
3. `DealScannerClient` - 24 edges
4. `import_listing()` - 17 edges
5. `EbayProvider` - 17 edges
6. `ApiService` - 16 edges
7. `MarketValueEngine` - 16 edges
8. `OfflineCacheService` - 15 edges
9. `WorkerAgent` - 14 edges
10. `evaluate_listing_record()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `SchedulerSettings` --uses--> `SearchProfile`  [INFERRED]
  apps/scheduler/src/deal_scanner_scheduler/main.py → packages/python/core/src/deal_scanner_core/models.py
- `Scheduler` --uses--> `SearchProfile`  [INFERRED]
  apps/scheduler/src/deal_scanner_scheduler/main.py → packages/python/core/src/deal_scanner_core/models.py
- `EvaluationOutcome` --uses--> `NotificationAdapter`  [INFERRED]
  apps/server-api/src/deal_scanner_api/market_service.py → packages/python/core/src/deal_scanner_core/ports.py
- `evaluate_listing_record()` --calls--> `DealScoreEngine`  [INFERRED]
  apps/server-api/src/deal_scanner_api/market_service.py → packages/python/scoring/src/deal_scanner_scoring/engine.py
- `evaluate_listing_record()` --calls--> `DealScoreInput`  [INFERRED]
  apps/server-api/src/deal_scanner_api/market_service.py → packages/python/scoring/src/deal_scanner_scoring/models.py

## Communities (48 total, 14 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (32): DealScannerError, LeaseConflict, ProviderError, ProviderRateLimited, Base error safe to map to a structured API problem., AiRiskSignal, AnalysisStatus, Contradiction (+24 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (57): AnalysisJobRow, AnalysisResultRow, AuditEventRow, Base, CanonicalProductRow, DealEvaluationRow, ExtensionPairingRow, IdempotencyKeyRow (+49 more)

### Community 2 - "Community 2"
Cohesion: 0.09
Nodes (57): CamelModel, AnalysisResultResponse, AuthMeResponse, CorrectedAttributeInput, CorrectedProductInput, CsvImportResponse, DealEvaluationHistoryResponse, ErpExportResponse (+49 more)

### Community 3 - "Community 3"
Cohesion: 0.07
Nodes (23): DevelopmentIdentityProvider, get_identity(), get_identity_provider(), Identity, IdentityProvider, SupabaseIdentityProvider, get_browser_request_context(), get_request_context() (+15 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (9): FixedWindowRateLimiter, _identity(), Small in-process guard for the single-process MVP API deployment., _sensitive(), ApiProblemError, ClientOptions, DealScannerClient, _request() (+1 more)

### Community 5 - "Community 5"
Cohesion: 0.1
Nodes (18): BaseSettings, ProductDetection, normalize_text(), ProductRule, RiskRule, RuleAnalysis, RuleExtractor, _ebay_image_urls() (+10 more)

### Community 6 - "Community 6"
Cohesion: 0.07
Nodes (18): BaseModel, validate_prices(), validate_security_mode(), _body(), _first_image(), KleinanzeigenMailParser, ParsedMail, CategoryProfile (+10 more)

### Community 7 - "Community 7"
Cohesion: 0.07
Nodes (28): components, $defs, operations, paths, webhooks, AnalysisJob, FeedbackCreate, ImageAccess (+20 more)

### Community 8 - "Community 8"
Cohesion: 0.19
Nodes (21): estimate_listing_market(), DealScoreEngine, MarketValueEngine, _median(), RiskScoreEngine, _weighted_quantile(), DealScoreInput, DealScoreResult (+13 more)

### Community 9 - "Community 9"
Cohesion: 0.17
Nodes (6): ApiService, CatalogPage, DashboardPage, PlaceholderPage, SystemPage, WorkersPage

### Community 10 - "Community 10"
Cohesion: 0.16
Nodes (19): create_image_access(), download_provider_image(), resolve_local_image(), store_private_image(), validate_image_url(), fingerprint_image(), ImageFingerprint, InvalidImage (+11 more)

### Community 11 - "Community 11"
Cohesion: 0.13
Nodes (15): MockErpIntegrationAdapter, Stable ERP boundary; replace this adapter without changing the REST contract., complete_provider_sync_run(), create_pairing(), create_provider_sync_run(), mail_imports(), _mail_response(), mock_erp_export() (+7 more)

### Community 12 - "Community 12"
Cohesion: 0.24
Nodes (13): config, Configuration, button, collectCards(), collectDetail(), externalId(), imageUrls(), importVisible() (+5 more)

### Community 13 - "Community 13"
Cohesion: 0.23
Nodes (11): payload(), test_end_to_end_import_feedback_and_worker_lease(), test_erp_mock_uses_stable_purchase_contract(), test_evaluation_keeps_risk_separate_and_creates_notification(), test_idempotency_and_extension_pairing(), test_listing_views_follow_versioned_favorite_and_hidden_feedback(), test_manual_product_correction_updates_canonical_detail_and_preserves_history(), test_search_profile_filters_and_notification_age_threshold_roundtrip() (+3 more)

### Community 14 - "Community 14"
Cohesion: 0.2
Nodes (5): AppComponent, appConfig, routes, DesktopNotificationService, NotificationPollingService

### Community 15 - "Community 15"
Cohesion: 0.24
Nodes (3): AuthService, runsInTauri(), LoginPage

### Community 16 - "Community 16"
Cohesion: 0.32
Nodes (12): claim_job(), complete_job(), fail_job(), heartbeat(), _job_response(), _leased_job(), list_jobs(), list_workers() (+4 more)

### Community 18 - "Community 18"
Cohesion: 0.31
Nodes (3): OutboxItem, OutboxKind, OutboxSyncService

### Community 20 - "Community 20"
Cohesion: 0.22
Nodes (8): E-Mail und Browser-Erweiterung, eBay, Einrichtung und Integrationen, ERP und Migration, Fehlerdiagnose, Lokal und Docker, Ollama, OCR und Benachrichtigungen, Supabase

### Community 21 - "Community 21"
Cohesion: 0.53
Nodes (4): test_private_storage_policy_uses_workspace_path(), test_rls_isolates_two_personal_workspaces(), _visible_workspaces(), _workspace_for()

### Community 22 - "Community 22"
Cohesion: 0.33
Nodes (5): code:powershell (Copy-Item .env.example .env), code:powershell (uv run pytest), Deal Scanner, Qualitätsprüfungen, Schnellstart

### Community 24 - "Community 24"
Cohesion: 0.4
Nodes (4): Architektur, Datenfluss, Entscheidungen, Grenzen

### Community 29 - "Community 29"
Cohesion: 0.5
Nodes (3): Abnahme und externe Voraussetzungen, Lokal reproduzierbar, Nur mit bereitgestellten externen Zugängen prüfbar

### Community 30 - "Community 30"
Cohesion: 0.5
Nodes (3): Answer, Q: Trace the existing end-to-end flow from listing import through analysis result, canonical product matching, market value evaluation, and notification. Identify the exact missing connections., Source Nodes

## Knowledge Gaps
- **57 isolated node(s):** `Configuration`, `config`, `button`, `value`, `apiUrl` (+52 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CamelModel` connect `Community 2` to `Community 0`, `Community 8`, `Community 5`, `Community 6`?**
  _High betweenness centrality (0.126) - this node is a cross-community bridge._
- **Are the 59 inferred relationships involving `CamelModel` (e.g. with `WorkspaceResponse` and `ProblemDetails`) actually correct?**
  _`CamelModel` has 59 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `import_listing()` (e.g. with `RuleExtractor` and `RiskScoreEngine`) actually correct?**
  _`import_listing()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Configuration`, `config`, `button` to the rest of the system?**
  _57 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.05 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.07 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.09 - nodes in this community are weakly interconnected._
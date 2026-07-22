# Graph Report - Graper  (2026-07-22)

## Corpus Check
- 122 files · ~71,581 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 811 nodes · 1614 edges · 56 communities (43 shown, 13 thin omitted)
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 249 edges (avg confidence: 0.61)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ec19f180`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

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
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]

## God Nodes (most connected - your core abstractions)
1. `CamelModel` - 75 edges
2. `DealScannerClient` - 31 edges
3. `Base` - 29 edges
4. `EbayProvider` - 20 edges
5. `import_listing()` - 17 edges
6. `ApiService` - 16 edges
7. `MarketValueEngine` - 16 edges
8. `WorkerAgent` - 15 edges
9. `OfflineCacheService` - 15 edges
10. `evaluate_listing_record()` - 15 edges

## Surprising Connections (you probably didn't know these)
- `SchedulerSettings` --uses--> `SearchProfile`  [INFERRED]
  apps/scheduler/src/deal_scanner_scheduler/main.py → packages/python/core/src/deal_scanner_core/models.py
- `Scheduler` --uses--> `SearchProfile`  [INFERRED]
  apps/scheduler/src/deal_scanner_scheduler/main.py → packages/python/core/src/deal_scanner_core/models.py
- `_matches_profile()` --calls--> `RuleExtractor`  [INFERRED]
  apps/scheduler/src/deal_scanner_scheduler/main.py → packages/python/extraction/src/deal_scanner_extraction/engine.py
- `EvaluationOutcome` --uses--> `NotificationAdapter`  [INFERRED]
  apps/server-api/src/deal_scanner_api/market_service.py → packages/python/core/src/deal_scanner_core/ports.py
- `evaluate_listing_record()` --calls--> `DealScoreEngine`  [INFERRED]
  apps/server-api/src/deal_scanner_api/market_service.py → packages/python/scoring/src/deal_scanner_scoring/engine.py

## Communities (56 total, 13 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (75): DevelopmentIdentityProvider, get_identity(), get_identity_provider(), Identity, IdentityProvider, SupabaseIdentityProvider, get_browser_request_context(), get_request_context() (+67 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (62): CamelModel, AnalysisResultResponse, AuthMeResponse, ComponentHealth, CorrectedAttributeInput, CorrectedProductInput, CsvImportResponse, DealEvaluationHistoryResponse (+54 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (35): BaseModel, validate_prices(), validate_security_mode(), DealScannerError, LeaseConflict, ProviderError, ProviderRateLimited, Base error safe to map to a structured API problem. (+27 more)

### Community 3 - "Community 3"
Cohesion: 0.07
Nodes (24): BaseSettings, AiRiskSignal, AnalysisStatus, Contradiction, DetectedAttribute, ImageOcrResult, ListingStatus, ModelProviderStatus (+16 more)

### Community 4 - "Community 4"
Cohesion: 0.11
Nodes (9): ApiProblemError, ApiResult, ClientOptions, createGeneratedDealScannerClient(), DealScannerClient, GeneratedDealScannerClient, client, fetchMock (+1 more)

### Community 5 - "Community 5"
Cohesion: 0.07
Nodes (29): components, $defs, operations, paths, webhooks, AnalysisJob, CsvImport, FeedbackCreate (+21 more)

### Community 6 - "Community 6"
Cohesion: 0.13
Nodes (21): get_session(), ready(), config, Configuration, results, button, collectCards(), collectDetail() (+13 more)

### Community 7 - "Community 7"
Cohesion: 0.11
Nodes (7): AuthService, runsInTauri(), ExtensionLoopbackService, LoopbackPairing, runsInTauri(), LoginPage, SettingsPage

### Community 8 - "Community 8"
Cohesion: 0.19
Nodes (21): estimate_listing_market(), DealScoreEngine, MarketValueEngine, _median(), RiskScoreEngine, _weighted_quantile(), DealScoreInput, DealScoreResult (+13 more)

### Community 9 - "Community 9"
Cohesion: 0.12
Nodes (22): record_audit_event(), MockErpIntegrationAdapter, Stable ERP boundary; replace this adapter without changing the REST contract., create_profile(), delete_profile(), list_profiles(), _response(), update_profile() (+14 more)

### Community 10 - "Community 10"
Cohesion: 0.17
Nodes (6): ApiService, CatalogPage, DashboardPage, PlaceholderPage, SystemPage, WorkersPage

### Community 11 - "Community 11"
Cohesion: 0.15
Nodes (11): AppComponent, appConfig, routes, isConflictError(), OutboxItem, OutboxKind, processOutboxItems(), conflicted (+3 more)

### Community 12 - "Community 12"
Cohesion: 0.16
Nodes (17): create_image_access(), download_provider_image(), resolve_local_image(), validate_image_url(), fingerprint_image(), ImageFingerprint, InvalidImage, perceptually_similar() (+9 more)

### Community 13 - "Community 13"
Cohesion: 0.15
Nodes (14): ActiveLoopback, forward(), forward_preserves_auth_idempotency_status_and_body(), is_uuid_like(), LoopbackController, LoopbackPairing, problem(), proxy_browser_import() (+6 more)

### Community 14 - "Community 14"
Cohesion: 0.13
Nodes (6): FixedWindowRateLimiter, _identity(), Small in-process guard for the single-process MVP API deployment., _sensitive(), _request(), test_sensitive_rate_limit_is_independent_and_returns_retry_delay()

### Community 15 - "Community 15"
Cohesion: 0.19
Nodes (13): payload(), set_job_times(), test_end_to_end_import_feedback_and_worker_lease(), test_erp_mock_uses_stable_purchase_contract(), test_evaluation_keeps_risk_separate_and_creates_notification(), test_idempotency_and_extension_pairing(), test_listing_views_follow_versioned_favorite_and_hidden_feedback(), test_manual_product_correction_updates_canonical_detail_and_preserves_history() (+5 more)

### Community 16 - "Community 16"
Cohesion: 0.21
Nodes (5): _ebay_image_urls(), _matches_profile(), run(), Scheduler, SchedulerSettings

### Community 17 - "Community 17"
Cohesion: 0.22
Nodes (12): ProductDetection, normalize_text(), ProductRule, RiskRule, RuleAnalysis, RuleExtractor, models(), test_o3_vista_and_elrs_remain_distinct() (+4 more)

### Community 18 - "Community 18"
Cohesion: 0.32
Nodes (12): claim_job(), complete_job(), fail_job(), heartbeat(), _job_response(), _leased_job(), list_jobs(), list_workers() (+4 more)

### Community 19 - "Community 19"
Cohesion: 0.17
Nodes (11): code:powershell ($env:DEAL_SCANNER_RUN_LIVE_TESTS='1'), Credential-gesteuerte Live-Abnahme, Desktop-Signierung und Notarisierung, E-Mail und Browser-Erweiterung, eBay, Einrichtung und Integrationen, ERP und Migration, Fehlerdiagnose (+3 more)

### Community 21 - "Community 21"
Cohesion: 0.24
Nodes (4): FileAccessService, runsInTauri(), SelectedTextFile, PricesPage

### Community 26 - "Community 26"
Cohesion: 0.38
Nodes (4): ApiTarget, validateApiTarget(), apiUrl, value

### Community 27 - "Community 27"
Cohesion: 0.48
Nodes (5): test_postgres_skip_locked_allows_only_one_concurrent_job_claim(), test_private_storage_policy_uses_workspace_path(), test_rls_isolates_two_personal_workspaces(), _visible_workspaces(), _workspace_for()

### Community 28 - "Community 28"
Cohesion: 0.29
Nodes (6): Deal Scanner erweitern, Neue Kategorie, Neuer Benachrichtigungs- oder ERP-Adapter, Neuer Listing-Provider, Neues Analysemodell, Änderungs-Checkliste

### Community 29 - "Community 29"
Cohesion: 0.33
Nodes (5): code:powershell (Copy-Item .env.example .env), code:powershell (uv run pytest), Deal Scanner, Qualitätsprüfungen, Schnellstart

### Community 32 - "Community 32"
Cohesion: 0.4
Nodes (4): Architektur, Datenfluss, Entscheidungen, Grenzen

### Community 33 - "Community 33"
Cohesion: 0.4
Nodes (4): Authentifizierung und Rollen, Datenmodell, Datenmodell und API, HTTP-Vertrag

### Community 35 - "Community 35"
Cohesion: 0.5
Nodes (3): Abnahme und externe Voraussetzungen, Lokal reproduzierbar, Nur mit bereitgestellten externen Zugängen prüfbar

### Community 36 - "Community 36"
Cohesion: 0.5
Nodes (3): Answer, Q: Trace the existing end-to-end flow from listing import through analysis result, canonical product matching, market value evaluation, and notification. Identify the exact missing connections., Source Nodes

### Community 37 - "Community 37"
Cohesion: 0.5
Nodes (3): Answer, Q: Which explicit Deal Scanner requirements in the specification are missing, only stubbed, or lack direct verification in the current repository?, Source Nodes

### Community 38 - "Community 38"
Cohesion: 0.5
Nodes (3): Answer, Q: Which improved Deal Scanner plan requirements still lack direct implementation or executable verification evidence? Focus on CI, Docker Compose, Supabase RLS/storage, cross-platform release, OpenAPI drift, and live-smoke gates., Source Nodes

### Community 39 - "Community 39"
Cohesion: 0.5
Nodes (3): Answer, Q: Which explicit requirements in the improved Deal Scanner plan remain unimplemented rather than merely unverified externally? Focus on Tauri loopback, token storage, SQLite offline cache, platform build workflows, storage signed URLs, SSRF, CSP, notification channels, and image OCR., Source Nodes

### Community 40 - "Community 40"
Cohesion: 0.5
Nodes (3): Answer, Q: Which original Deal Scanner requirements beyond the 20-point MVP are directly evidenced, and which lack nodes or paths: browser inline deal-score overlay and known-listing detection, normalized text fingerprint duplicate detection, health status for email/eBay/Ollama/storage, database backup, image prioritization, similar complete-PC market comparison, distance/fahrtkosten/platform fees, and seller/image ERP export fields?, Source Nodes

## Knowledge Gaps
- **91 isolated node(s):** `ApiTarget`, `Configuration`, `config`, `results`, `[listing]` (+86 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CamelModel` connect `Community 1` to `Community 8`, `Community 17`, `Community 2`, `Community 3`?**
  _High betweenness centrality (0.105) - this node is a cross-community bridge._
- **Are the 61 inferred relationships involving `CamelModel` (e.g. with `WorkspaceResponse` and `ProblemDetails`) actually correct?**
  _`CamelModel` has 61 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `EbayProvider` (e.g. with `ProviderError` and `ProviderRateLimited`) actually correct?**
  _`EbayProvider` has 11 INFERRED edges - model-reasoned connections that need verification._
- **What connects `ApiTarget`, `Configuration`, `config` to the rest of the system?**
  _91 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.05 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.08 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.05 - nodes in this community are weakly interconnected._
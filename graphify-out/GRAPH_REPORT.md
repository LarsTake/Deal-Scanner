# Graph Report - Graper  (2026-07-22)

## Corpus Check
- 97 files · ~56,353 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 597 nodes · 1207 edges · 36 communities (31 shown, 5 thin omitted)
- Extraction: 83% EXTRACTED · 17% INFERRED · 0% AMBIGUOUS · INFERRED: 202 edges (avg confidence: 0.6)
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
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]

## God Nodes (most connected - your core abstractions)
1. `CamelModel` - 57 edges
2. `Base` - 27 edges
3. `DealScannerClient` - 21 edges
4. `EbayProvider` - 17 edges
5. `import_listing()` - 16 edges
6. `MarketValueEngine` - 16 edges
7. `ApiService` - 15 edges
8. `OfflineCacheService` - 15 edges
9. `WorkerAgent` - 14 edges
10. `Scheduler` - 13 edges

## Surprising Connections (you probably didn't know these)
- `SchedulerSettings` --uses--> `SearchProfile`  [INFERRED]
  apps/scheduler/src/deal_scanner_scheduler/main.py → packages/python/core/src/deal_scanner_core/models.py
- `Scheduler` --uses--> `SearchProfile`  [INFERRED]
  apps/scheduler/src/deal_scanner_scheduler/main.py → packages/python/core/src/deal_scanner_core/models.py
- `evaluate_listing_record()` --calls--> `DealScoreEngine`  [INFERRED]
  apps/server-api/src/deal_scanner_api/market_service.py → packages/python/scoring/src/deal_scanner_scoring/engine.py
- `evaluate_listing_record()` --calls--> `DealScoreInput`  [INFERRED]
  apps/server-api/src/deal_scanner_api/market_service.py → packages/python/scoring/src/deal_scanner_scoring/models.py
- `canonicalize_detection()` --calls--> `RuleExtractor`  [INFERRED]
  apps/server-api/src/deal_scanner_api/product_service.py → packages/python/extraction/src/deal_scanner_extraction/engine.py

## Communities (36 total, 5 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (21): ApiService, AppComponent, appConfig, routes, CatalogPage, ConflictsPage, DashboardPage, DesktopNotificationService (+13 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (28): DealScannerError, LeaseConflict, ProviderError, ProviderRateLimited, Base error safe to map to a structured API problem., AnalysisStatus, ImageOcrResult, ListingStatus (+20 more)

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (57): AnalysisJobRow, AnalysisResultRow, AuditEventRow, Base, CanonicalProductRow, DealEvaluationRow, ExtensionPairingRow, IdempotencyKeyRow (+49 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (54): CamelModel, AuthMeResponse, CsvImportResponse, ErpExportResponse, FeedbackCreate, ImageAccessResponse, ImportResponse, JobClaimRequest (+46 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (14): DevelopmentIdentityProvider, get_identity(), get_identity_provider(), Identity, IdentityProvider, SupabaseIdentityProvider, get_browser_request_context(), get_request_context() (+6 more)

### Community 5 - "Community 5"
Cohesion: 0.08
Nodes (17): BaseModel, validate_prices(), validate_security_mode(), _body(), _first_image(), KleinanzeigenMailParser, ParsedMail, CategoryProfile (+9 more)

### Community 6 - "Community 6"
Cohesion: 0.07
Nodes (26): components, $defs, operations, paths, webhooks, AnalysisJob, FeedbackCreate, ImageAccess (+18 more)

### Community 7 - "Community 7"
Cohesion: 0.19
Nodes (21): estimate_listing_market(), DealScoreEngine, MarketValueEngine, _median(), RiskScoreEngine, _weighted_quantile(), DealScoreInput, DealScoreResult (+13 more)

### Community 8 - "Community 8"
Cohesion: 0.14
Nodes (3): ApiProblemError, ClientOptions, DealScannerClient

### Community 9 - "Community 9"
Cohesion: 0.16
Nodes (19): create_image_access(), download_provider_image(), resolve_local_image(), store_private_image(), validate_image_url(), fingerprint_image(), ImageFingerprint, InvalidImage (+11 more)

### Community 10 - "Community 10"
Cohesion: 0.24
Nodes (13): config, Configuration, button, collectCards(), collectDetail(), externalId(), imageUrls(), importVisible() (+5 more)

### Community 11 - "Community 11"
Cohesion: 0.19
Nodes (4): AuthService, runsInTauri(), LoginPage, SettingsPage

### Community 12 - "Community 12"
Cohesion: 0.21
Nodes (5): BaseSettings, _ebay_image_urls(), run(), Scheduler, SchedulerSettings

### Community 13 - "Community 13"
Cohesion: 0.22
Nodes (12): ProductDetection, normalize_text(), ProductRule, RiskRule, RuleAnalysis, RuleExtractor, models(), test_o3_vista_and_elrs_remain_distinct() (+4 more)

### Community 14 - "Community 14"
Cohesion: 0.32
Nodes (12): claim_job(), complete_job(), fail_job(), heartbeat(), _job_response(), _leased_job(), list_jobs(), list_workers() (+4 more)

### Community 16 - "Community 16"
Cohesion: 0.33
Nodes (7): payload(), test_end_to_end_import_feedback_and_worker_lease(), test_evaluation_keeps_risk_separate_and_creates_notification(), test_idempotency_and_extension_pairing(), test_listing_views_follow_versioned_favorite_and_hidden_feedback(), test_worker_completion_canonicalizes_product_and_evaluates_automatically(), test_workspace_isolation_at_api_boundary()

### Community 17 - "Community 17"
Cohesion: 0.53
Nodes (4): create_profile(), list_profiles(), _response(), update_profile()

### Community 18 - "Community 18"
Cohesion: 0.53
Nodes (4): test_private_storage_policy_uses_workspace_path(), test_rls_isolates_two_personal_workspaces(), _visible_workspaces(), _workspace_for()

### Community 19 - "Community 19"
Cohesion: 0.33
Nodes (5): code:powershell (Copy-Item .env.example .env), code:powershell (uv run pytest), Deal Scanner, Qualitätsprüfungen, Schnellstart

### Community 20 - "Community 20"
Cohesion: 0.4
Nodes (4): Architektur, Datenfluss, Entscheidungen, Grenzen

### Community 21 - "Community 21"
Cohesion: 0.5
Nodes (3): Abnahme und externe Voraussetzungen, Lokal reproduzierbar, Nur mit bereitgestellten externen Zugängen prüfbar

### Community 22 - "Community 22"
Cohesion: 0.5
Nodes (3): Answer, Q: Trace the existing end-to-end flow from listing import through analysis result, canonical product matching, market value evaluation, and notification. Identify the exact missing connections., Source Nodes

## Knowledge Gaps
- **45 isolated node(s):** `Configuration`, `config`, `button`, `value`, `apiUrl` (+40 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CamelModel` connect `Community 3` to `Community 1`, `Community 13`, `Community 5`, `Community 7`?**
  _High betweenness centrality (0.125) - this node is a cross-community bridge._
- **Why does `SearchProfile` connect `Community 1` to `Community 3`, `Community 12`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Why does `text()` connect `Community 10` to `Community 12`, `Community 4`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Are the 46 inferred relationships involving `CamelModel` (e.g. with `WorkspaceResponse` and `ProblemDetails`) actually correct?**
  _`CamelModel` has 46 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `EbayProvider` (e.g. with `ProviderError` and `ProviderRateLimited`) actually correct?**
  _`EbayProvider` has 8 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Configuration`, `config`, `button` to the rest of the system?**
  _45 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.05 - nodes in this community are weakly interconnected._
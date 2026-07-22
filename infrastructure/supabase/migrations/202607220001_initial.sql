create extension if not exists pgcrypto;
create schema if not exists deal_scanner;

create or replace function deal_scanner.current_user_id()
returns uuid
language sql
stable
as $$
  select coalesce(
    auth.uid(),
    nullif(current_setting('request.jwt.claim.sub', true), '')::uuid
  )
$$;

create table deal_scanner.workspaces (
  id uuid primary key default gen_random_uuid(),
  name text not null check (length(name) between 1 and 120),
  erp_tenant_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table deal_scanner.workspace_members (
  workspace_id uuid not null references deal_scanner.workspaces(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null default 'owner' check (role in ('owner', 'admin', 'member', 'viewer')),
  created_at timestamptz not null default now(),
  primary key (workspace_id, user_id)
);

create or replace function deal_scanner.is_workspace_member(target_workspace_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from deal_scanner.workspace_members membership
    where membership.workspace_id = target_workspace_id
      and membership.user_id = deal_scanner.current_user_id()
  )
$$;

create table deal_scanner.search_profiles (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references deal_scanner.workspaces(id) on delete cascade,
  name text not null,
  query text not null check (length(query) between 1 and 100),
  category_profile text not null default 'general',
  enabled_platforms jsonb not null default '["ebay"]',
  minimum_price numeric(14,2),
  maximum_price numeric(14,2),
  location text,
  radius_km integer,
  required_terms jsonb not null default '[]',
  excluded_terms jsonb not null default '[]',
  minimum_deal_score smallint not null default 75 check (minimum_deal_score between 0 and 100),
  maximum_risk_score smallint not null default 45 check (maximum_risk_score between 0 and 100),
  notification_settings jsonb not null default '{}',
  scan_interval_minutes integer not null default 15 check (scan_interval_minutes >= 5),
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (minimum_price is null or maximum_price is null or minimum_price <= maximum_price)
);

create table deal_scanner.sellers (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references deal_scanner.workspaces(id) on delete cascade,
  platform text not null,
  external_id text not null,
  display_name text,
  account_age_text text,
  account_created_at timestamptz,
  rating_text text,
  rating_score numeric(5,2),
  review_count integer,
  location text,
  raw_data jsonb not null default '{}',
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  unique (workspace_id, platform, external_id)
);

create table deal_scanner.listings (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references deal_scanner.workspaces(id) on delete cascade,
  search_profile_id uuid references deal_scanner.search_profiles(id) on delete set null,
  seller_id uuid references deal_scanner.sellers(id) on delete set null,
  platform text not null,
  external_id text not null,
  url text not null,
  title text not null,
  description text not null default '',
  price numeric(14,2) not null check (price >= 0),
  shipping_cost numeric(14,2) not null default 0 check (shipping_cost >= 0),
  currency char(3) not null default 'EUR',
  location text,
  category_profile text not null default 'general',
  published_at timestamptz,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  removed_at timestamptz,
  status text not null default 'DISCOVERED',
  analysis_status text not null default 'PENDING',
  is_favorite boolean not null default false,
  is_hidden boolean not null default false,
  current_snapshot_id uuid,
  version integer not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, platform, external_id)
);

create table deal_scanner.listing_snapshots (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references deal_scanner.workspaces(id) on delete cascade,
  listing_id uuid not null references deal_scanner.listings(id) on delete cascade,
  content_hash char(64) not null,
  raw_data jsonb not null,
  provider_version text not null,
  storage_path text,
  fetched_at timestamptz not null,
  created_at timestamptz not null default now(),
  unique (listing_id, content_hash)
);

alter table deal_scanner.listings
  add constraint listings_current_snapshot_fk
  foreign key (current_snapshot_id) references deal_scanner.listing_snapshots(id) on delete set null;

create table deal_scanner.listing_images (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references deal_scanner.workspaces(id) on delete cascade,
  listing_id uuid not null references deal_scanner.listings(id) on delete cascade,
  source_url text not null,
  storage_path text,
  sha256_hash char(64),
  perceptual_hash text,
  width integer,
  height integer,
  mime_type text,
  analysis_status text not null default 'PENDING',
  created_at timestamptz not null default now()
);

create table deal_scanner.canonical_products (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references deal_scanner.workspaces(id) on delete cascade,
  category_profile text not null,
  product_type text not null,
  manufacturer text,
  model text not null,
  variant text,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique nulls not distinct (workspace_id, category_profile, product_type, manufacturer, model, variant)
);

create table deal_scanner.product_aliases (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references deal_scanner.workspaces(id) on delete cascade,
  canonical_product_id uuid not null references deal_scanner.canonical_products(id) on delete cascade,
  alias text not null,
  normalized_alias text not null,
  created_at timestamptz not null default now(),
  unique (workspace_id, normalized_alias)
);

create table deal_scanner.listing_products (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references deal_scanner.workspaces(id) on delete cascade,
  listing_id uuid not null references deal_scanner.listings(id) on delete cascade,
  canonical_product_id uuid references deal_scanner.canonical_products(id) on delete set null,
  product_type text not null,
  manufacturer text,
  model text not null,
  variant text,
  quantity integer not null default 1 check (quantity > 0),
  confidence numeric(4,3) not null check (confidence between 0 and 1),
  detection_source text not null,
  raw_match text not null,
  created_at timestamptz not null default now()
);

create table deal_scanner.product_attributes (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references deal_scanner.workspaces(id) on delete cascade,
  listing_product_id uuid not null references deal_scanner.listing_products(id) on delete cascade,
  attribute_key text not null,
  value_text text,
  value_number numeric,
  value_boolean boolean,
  unit text,
  confidence numeric(4,3) not null check (confidence between 0 and 1),
  source text not null,
  created_at timestamptz not null default now(),
  check (num_nonnulls(value_text, value_number, value_boolean) = 1)
);

create table deal_scanner.price_observations (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references deal_scanner.workspaces(id) on delete cascade,
  canonical_product_id uuid references deal_scanner.canonical_products(id) on delete cascade,
  listing_id uuid references deal_scanner.listings(id) on delete set null,
  platform text not null,
  observed_price numeric(14,2) not null check (observed_price > 0),
  shipping_cost numeric(14,2) not null default 0,
  currency char(3) not null default 'EUR',
  condition text,
  observation_kind text not null check (observation_kind in ('soldConfirmed', 'manualSold', 'active')),
  region text,
  observed_at timestamptz not null,
  source_quality numeric(4,3) not null check (source_quality between 0 and 1),
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table deal_scanner.market_value_estimates (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references deal_scanner.workspaces(id) on delete cascade,
  listing_id uuid not null references deal_scanner.listings(id) on delete cascade,
  status text not null,
  minimum numeric(14,2),
  median numeric(14,2),
  maximum numeric(14,2),
  observation_count integer not null,
  data_quality_score smallint not null check (data_quality_score between 0 and 100),
  calculation_version text not null,
  explanation jsonb not null,
  created_at timestamptz not null default now()
);

create table deal_scanner.workers (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references deal_scanner.workspaces(id) on delete cascade,
  name text not null,
  operating_system text not null,
  hostname text not null,
  cpu text,
  ram_gb numeric(7,2),
  gpu text,
  vram_gb numeric(7,2),
  runtime jsonb not null default '{}',
  capabilities jsonb not null default '[]',
  installed_models jsonb not null default '[]',
  current_load numeric(4,3) not null default 0,
  last_heartbeat_at timestamptz not null default now(),
  enabled boolean not null default true,
  created_at timestamptz not null default now()
);

create table deal_scanner.analysis_jobs (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references deal_scanner.workspaces(id) on delete cascade,
  listing_id uuid not null references deal_scanner.listings(id) on delete cascade,
  snapshot_id uuid not null references deal_scanner.listing_snapshots(id) on delete cascade,
  job_type text not null,
  required_capability text not null,
  input_hash char(64) not null,
  priority integer not null default 0,
  status text not null default 'PENDING' check (status in ('PENDING', 'LEASED', 'COMPLETE', 'RETRY', 'DEAD')),
  assigned_worker_id uuid references deal_scanner.workers(id) on delete set null,
  lease_expires_at timestamptz,
  attempts integer not null default 0,
  available_at timestamptz not null default now(),
  last_error text,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz,
  unique (listing_id, snapshot_id, job_type, input_hash)
);

create table deal_scanner.analysis_results (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references deal_scanner.workspaces(id) on delete cascade,
  listing_id uuid not null references deal_scanner.listings(id) on delete cascade,
  job_id uuid references deal_scanner.analysis_jobs(id) on delete set null,
  analysis_type text not null,
  model_name text not null,
  model_version text not null,
  prompt_version text not null,
  result_schema_version text not null,
  input_hash char(64) not null,
  result_json jsonb not null,
  confidence numeric(4,3) not null check (confidence between 0 and 1),
  created_at timestamptz not null default now(),
  unique (listing_id, analysis_type, model_name, model_version, prompt_version, input_hash)
);

create unique index analysis_results_job_input_idx
on deal_scanner.analysis_results(job_id, input_hash)
where job_id is not null;

create table deal_scanner.risk_signals (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references deal_scanner.workspaces(id) on delete cascade,
  listing_id uuid not null references deal_scanner.listings(id) on delete cascade,
  type text not null,
  severity smallint not null check (severity between 0 and 100),
  confidence numeric(4,3) not null check (confidence between 0 and 1),
  positive boolean not null default false,
  source text not null,
  evidence text not null,
  created_at timestamptz not null default now()
);

create table deal_scanner.deal_evaluations (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references deal_scanner.workspaces(id) on delete cascade,
  listing_id uuid not null references deal_scanner.listings(id) on delete cascade,
  estimated_market_value_min numeric(14,2),
  estimated_market_value_median numeric(14,2),
  estimated_market_value_max numeric(14,2),
  expected_resale_value numeric(14,2),
  estimated_margin numeric(14,2),
  deal_score smallint check (deal_score between 0 and 100),
  risk_score smallint not null check (risk_score between 0 and 100),
  data_quality_score smallint not null check (data_quality_score between 0 and 100),
  relevance_score smallint not null check (relevance_score between 0 and 100),
  explanation jsonb not null,
  calculation_version text not null,
  created_at timestamptz not null default now()
);

create table deal_scanner.user_feedback (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references deal_scanner.workspaces(id) on delete cascade,
  listing_id uuid not null references deal_scanner.listings(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete restrict,
  feedback_type text not null,
  base_listing_version integer not null,
  corrected_products jsonb,
  corrected_attributes jsonb,
  corrected_value jsonb,
  note text,
  created_at timestamptz not null default now()
);

create table deal_scanner.provider_sync_runs (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references deal_scanner.workspaces(id) on delete cascade,
  search_profile_id uuid references deal_scanner.search_profiles(id) on delete set null,
  provider text not null,
  status text not null,
  cursor text,
  discovered_count integer not null default 0,
  imported_count integer not null default 0,
  error_summary text,
  started_at timestamptz not null default now(),
  completed_at timestamptz
);

create table deal_scanner.mail_imports (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references deal_scanner.workspaces(id) on delete cascade,
  message_id text not null,
  sender text not null,
  subject text not null,
  received_at timestamptz not null,
  raw_storage_path text not null,
  raw_sha256 char(64) not null,
  parser_version text not null,
  status text not null,
  parsed_data jsonb,
  error_summary text,
  created_at timestamptz not null default now(),
  unique (workspace_id, message_id)
);

create table deal_scanner.notifications (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references deal_scanner.workspaces(id) on delete cascade,
  listing_id uuid references deal_scanner.listings(id) on delete cascade,
  evaluation_id uuid unique references deal_scanner.deal_evaluations(id) on delete cascade,
  reason jsonb not null,
  created_at timestamptz not null default now()
);

create table deal_scanner.notification_deliveries (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references deal_scanner.workspaces(id) on delete cascade,
  notification_id uuid not null references deal_scanner.notifications(id) on delete cascade,
  channel text not null,
  status text not null,
  attempts integer not null default 0,
  last_error text,
  delivered_at timestamptz,
  created_at timestamptz not null default now()
);

create table deal_scanner.extension_pairings (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references deal_scanner.workspaces(id) on delete cascade,
  created_by_user_id uuid not null references auth.users(id) on delete cascade,
  token_hash char(64) not null unique,
  extension_id text,
  expires_at timestamptz not null,
  revoked_at timestamptz,
  created_at timestamptz not null default now()
);

-- Pairing tokens are opaque capabilities. This narrowly scoped resolver is the only
-- pre-authenticated path and never exposes the token or other pairing records.
create or replace function deal_scanner.resolve_extension_pairing(candidate_hash char(64))
returns table(workspace_id uuid, user_id uuid)
language sql
stable
security definer
set search_path = ''
as $$
  select pairing.workspace_id, pairing.created_by_user_id
  from deal_scanner.extension_pairings pairing
  where pairing.token_hash = candidate_hash
    and pairing.revoked_at is null
    and pairing.expires_at > now()
  limit 1
$$;

revoke all on function deal_scanner.resolve_extension_pairing(char(64)) from public;
grant execute on function deal_scanner.resolve_extension_pairing(char(64)) to authenticated;

create table deal_scanner.idempotency_keys (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references deal_scanner.workspaces(id) on delete cascade,
  key text not null,
  operation text not null,
  request_hash char(64) not null,
  resource_id uuid,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  unique (workspace_id, operation, key)
);

create table deal_scanner.audit_events (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references deal_scanner.workspaces(id) on delete cascade,
  actor_user_id uuid,
  event_type text not null,
  aggregate_type text not null,
  aggregate_id uuid,
  payload jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create index listings_workspace_status_idx on deal_scanner.listings(workspace_id, status, last_seen_at desc);
create index listings_workspace_score_queue_idx on deal_scanner.listings(workspace_id, analysis_status, created_at);
create index listing_snapshots_listing_idx on deal_scanner.listing_snapshots(listing_id, created_at desc);
create index price_observations_product_time_idx on deal_scanner.price_observations(canonical_product_id, observed_at desc);
create index analysis_jobs_claim_idx on deal_scanner.analysis_jobs(status, required_capability, available_at, priority desc);
create index workers_heartbeat_idx on deal_scanner.workers(workspace_id, enabled, last_heartbeat_at desc);
create index audit_events_aggregate_idx on deal_scanner.audit_events(workspace_id, aggregate_type, aggregate_id, created_at desc);

create or replace function deal_scanner.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end
$$;

create trigger workspaces_updated_at before update on deal_scanner.workspaces
for each row execute function deal_scanner.set_updated_at();
create trigger search_profiles_updated_at before update on deal_scanner.search_profiles
for each row execute function deal_scanner.set_updated_at();
create trigger listings_updated_at before update on deal_scanner.listings
for each row execute function deal_scanner.set_updated_at();
create trigger canonical_products_updated_at before update on deal_scanner.canonical_products
for each row execute function deal_scanner.set_updated_at();

create or replace function deal_scanner.prevent_mutation()
returns trigger language plpgsql as $$
begin
  raise exception '% is append-only', tg_table_name using errcode = '55000';
end
$$;

create trigger listing_snapshots_append_only before update or delete on deal_scanner.listing_snapshots
for each row execute function deal_scanner.prevent_mutation();
create trigger analysis_results_append_only before update or delete on deal_scanner.analysis_results
for each row execute function deal_scanner.prevent_mutation();
create trigger audit_events_append_only before update or delete on deal_scanner.audit_events
for each row execute function deal_scanner.prevent_mutation();

create or replace function deal_scanner.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  new_workspace_id uuid;
begin
  insert into deal_scanner.workspaces(name)
  values (coalesce(new.raw_user_meta_data ->> 'display_name', split_part(new.email, '@', 1), 'Workspace'))
  returning id into new_workspace_id;

  insert into deal_scanner.workspace_members(workspace_id, user_id, role)
  values (new_workspace_id, new.id, 'owner');
  return new;
end
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute function deal_scanner.handle_new_user();

alter table deal_scanner.workspaces enable row level security;
alter table deal_scanner.workspace_members enable row level security;

create policy workspace_member_access on deal_scanner.workspaces
for all to authenticated
using (deal_scanner.is_workspace_member(id))
with check (deal_scanner.is_workspace_member(id));

create policy membership_self_access on deal_scanner.workspace_members
for select to authenticated
using (user_id = deal_scanner.current_user_id());

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'search_profiles', 'sellers', 'listings', 'listing_snapshots', 'listing_images',
    'canonical_products', 'product_aliases', 'listing_products', 'product_attributes',
    'price_observations', 'market_value_estimates', 'workers', 'analysis_jobs',
    'analysis_results', 'risk_signals', 'deal_evaluations', 'user_feedback',
    'provider_sync_runs', 'mail_imports', 'notifications', 'notification_deliveries',
    'extension_pairings', 'idempotency_keys', 'audit_events'
  ] loop
    execute format('alter table deal_scanner.%I enable row level security', table_name);
    execute format(
      'create policy workspace_isolation on deal_scanner.%I for all to authenticated using (deal_scanner.is_workspace_member(workspace_id)) with check (deal_scanner.is_workspace_member(workspace_id))',
      table_name
    );
  end loop;
end
$$;

revoke all on schema deal_scanner from public, anon;
grant usage on schema deal_scanner to authenticated, service_role;
grant select, insert, update, delete on all tables in schema deal_scanner to authenticated;
grant all on all tables in schema deal_scanner to service_role;
alter default privileges in schema deal_scanner revoke all on tables from public, anon;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
  ('listing-images', 'listing-images', false, 15728640, array['image/jpeg', 'image/png', 'image/webp']),
  ('mail-archive', 'mail-archive', false, 20971520, array['message/rfc822', 'application/octet-stream'])
on conflict (id) do update
set public = false,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

create or replace function deal_scanner.storage_workspace_id(object_name text)
returns uuid
language sql
immutable
as $$
  select case
    when split_part(object_name, '/', 1) ~ '^[0-9a-fA-F-]{36}$'
      then split_part(object_name, '/', 1)::uuid
    else null
  end
$$;

create policy deal_scanner_private_objects_read on storage.objects
for select to authenticated
using (
  bucket_id in ('listing-images', 'mail-archive')
  and deal_scanner.is_workspace_member(deal_scanner.storage_workspace_id(name))
);

create policy deal_scanner_private_objects_insert on storage.objects
for insert to authenticated
with check (
  bucket_id in ('listing-images', 'mail-archive')
  and deal_scanner.is_workspace_member(deal_scanner.storage_workspace_id(name))
);

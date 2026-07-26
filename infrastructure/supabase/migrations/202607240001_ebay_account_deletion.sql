create table deal_scanner.ebay_account_deletion_events (
  notification_id text primary key,
  received_at timestamptz not null default now(),
  processed_at timestamptz not null default now(),
  deleted_seller_count integer not null default 0 check (deleted_seller_count >= 0),
  deleted_listing_count integer not null default 0 check (deleted_listing_count >= 0)
);

-- Compliance deletions are the sole exception to append-only domain records.
-- The API enables this transaction-local flag only after validating eBay's
-- signed Marketplace Account Deletion notification.
create or replace function deal_scanner.prevent_mutation()
returns trigger language plpgsql as $$
begin
  if tg_op = 'DELETE'
    and current_setting('deal_scanner.account_deletion', true) = 'on'
    and current_user not in ('anon', 'authenticated')
  then
    return old;
  end if;
  raise exception '% is append-only', tg_table_name using errcode = '55000';
end
$$;

revoke all on table deal_scanner.ebay_account_deletion_events from public, anon, authenticated;
grant all on table deal_scanner.ebay_account_deletion_events to service_role;
alter default privileges in schema deal_scanner revoke all on tables from public, anon;

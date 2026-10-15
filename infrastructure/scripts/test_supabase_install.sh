#!/usr/bin/env bash
# Run only in a disposable container with the repository mounted read-only at /workspace.
set -euo pipefail
test -f /workspace/infrastructure/supabase/install.sql
cluster_dir=$(mktemp -d /tmp/deal-scanner-install-test.XXXXXX)
initdb -D "$cluster_dir/data" -A trust --encoding=UTF8 --locale=C > "$cluster_dir/init.log"
pg_ctl -D "$cluster_dir/data" -l "$cluster_dir/postgres.log" -o '-k /tmp -h ""' start -w
trap 'pg_ctl -D "$cluster_dir/data" stop -m fast -w' EXIT
export PGHOST=/tmp PGDATABASE=postgres
bootstrap=/workspace/tests/postgres/bootstrap.sql
installer=/workspace/infrastructure/supabase/install.sql
psql -X -v ON_ERROR_STOP=1 -f "$bootstrap" > "$cluster_dir/bootstrap.log"
# Send the entire file as one query, as the dashboard SQL Editor does.
psql -X -v ON_ERROR_STOP=1 -c "$(< "$installer")" > "$cluster_dir/install.log"
test "$(psql -XAtc "select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='deal_scanner' and c.relkind='r' and c.relrowsecurity")" = 27
psql -X -v ON_ERROR_STOP=1 -c "insert into auth.users(id,email) values ('00000000-0000-4000-8000-000000000111','one@example.test'),('00000000-0000-4000-8000-000000000222','two@example.test')" > /dev/null
test "$(psql -XAtc 'select count(*) from deal_scanner.workspaces')" = 2
test "$(psql -XAtc "begin; set local role authenticated; select set_config('request.jwt.claim.sub','00000000-0000-4000-8000-000000000111',true); select count(*) from deal_scanner.workspaces; rollback;" | tail -2 | head -1)" = 1

expect_refusal() {
  if psql -X -v ON_ERROR_STOP=1 -f "$installer" > "$cluster_dir/refusal.log" 2>&1; then
    echo 'ERROR: expected installation to abort' >&2
    exit 1
  fi
  grep -q "$1" "$cluster_dir/refusal.log"
}

expect_refusal 'Schema deal_scanner already exists'
test "$(psql -XAtc 'select count(*) from deal_scanner.workspaces')" = 2

new_fixture_database() {
  createdb "$1"
  export PGDATABASE="$1"
  sed '/^create role /d' "$bootstrap" | psql -X -v ON_ERROR_STOP=1 > "$cluster_dir/bootstrap.log"
}

new_fixture_database schema_conflict
psql -X -v ON_ERROR_STOP=1 -c 'create schema deal_scanner; create table deal_scanner.sentinel(id integer); insert into deal_scanner.sentinel values (42);' > /dev/null
expect_refusal 'Schema deal_scanner already exists'
test "$(psql -XAtc 'select id from deal_scanner.sentinel')" = 42

new_fixture_database bucket_conflict
psql -X -v ON_ERROR_STOP=1 -c "insert into storage.buckets(id,name,public) values ('listing-images','listing-images',true)" > /dev/null
expect_refusal 'Existing listing-images/mail-archive buckets are protected'
test "$(psql -XAtc "select public from storage.buckets where id='listing-images'")" = t
test "$(psql -XAtc "select count(*) from pg_namespace where nspname='deal_scanner'")" = 0

new_fixture_database trigger_conflict
psql -X -v ON_ERROR_STOP=1 -c 'create function public.preserve_user() returns trigger language plpgsql as $$begin return new; end$$; create trigger on_auth_user_created after insert on auth.users for each row execute function public.preserve_user();' > /dev/null
expect_refusal 'Existing on_auth_user_created trigger is protected'
test "$(psql -XAtc "select count(*) from pg_namespace where nspname='deal_scanner'")" = 0
test "$(psql -XAtc "select count(*) from pg_trigger where tgname='on_auth_user_created' and not tgisinternal")" = 1
new_fixture_database policy_conflict
psql -X -v ON_ERROR_STOP=1 -c 'create policy existing_broad_access on storage.objects for select to authenticated using (true);' > /dev/null
expect_refusal 'Existing storage policies require review'
test "$(psql -XAtc "select count(*) from pg_namespace where nspname='deal_scanner'")" = 0
echo 'PASS: fresh installation, RLS isolation, repeat refusal, schema/bucket/trigger/policy conflict protection'

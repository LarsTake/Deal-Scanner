alter table deal_scanner.extension_pairings
  add column display_name text not null default 'Browser-Erweiterung';

alter table deal_scanner.extension_pairings
  alter column expires_at drop not null;

-- Permanent extension connections have no expiry. They remain narrowly scoped
-- opaque capabilities and can be revoked by an authenticated workspace member.
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
    and (pairing.expires_at is null or pairing.expires_at > now())
  limit 1
$$;

revoke all on function deal_scanner.resolve_extension_pairing(char(64)) from public;
grant execute on function deal_scanner.resolve_extension_pairing(char(64)) to authenticated;

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest

POSTGRES_URL = os.getenv("DEAL_SCANNER_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not POSTGRES_URL, reason="requires DEAL_SCANNER_TEST_POSTGRES_URL")

USER_ONE = UUID("00000000-0000-4000-8000-000000000111")
USER_TWO = UUID("00000000-0000-4000-8000-000000000222")


@pytest.fixture(scope="module")
def postgres() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    assert POSTGRES_URL
    connection = psycopg.connect(POSTGRES_URL, autocommit=True)
    root = Path(__file__).parents[1]
    connection.execute((root / "tests/postgres/bootstrap.sql").read_text(encoding="utf-8"))
    migrations = root / "infrastructure/supabase/migrations"
    for migration in sorted(migrations.glob("*.sql")):
        connection.execute(migration.read_text(encoding="utf-8"))
    connection.execute(
        "insert into auth.users(id, email) values (%s, %s), (%s, %s)",
        (USER_ONE, "one@example.test", USER_TWO, "two@example.test"),
    )
    yield connection
    connection.close()


def _workspace_for(connection: psycopg.Connection[tuple[object, ...]], user_id: UUID) -> UUID:
    row = connection.execute(
        "select workspace_id from deal_scanner.workspace_members where user_id = %s",
        (user_id,),
    ).fetchone()
    assert row is not None
    return UUID(str(row[0]))


def _visible_workspaces(connection: psycopg.Connection[tuple[object, ...]], user_id: UUID) -> list[UUID]:
    with connection.transaction():
        connection.execute("set local role authenticated")
        connection.execute("select set_config('request.jwt.claim.sub', %s, true)", (str(user_id),))
        rows = connection.execute("select id from deal_scanner.workspaces order by id").fetchall()
    return [UUID(str(row[0])) for row in rows]


def test_rls_isolates_two_personal_workspaces(postgres: psycopg.Connection[tuple[object, ...]]) -> None:
    workspace_one = _workspace_for(postgres, USER_ONE)
    workspace_two = _workspace_for(postgres, USER_TWO)
    assert workspace_one != workspace_two
    assert _visible_workspaces(postgres, USER_ONE) == [workspace_one]
    assert _visible_workspaces(postgres, USER_TWO) == [workspace_two]

    with pytest.raises(psycopg.errors.InsufficientPrivilege), postgres.transaction():
        postgres.execute("set local role authenticated")
        postgres.execute("select set_config('request.jwt.claim.sub', %s, true)", (str(USER_TWO),))
        postgres.execute(
            """
            insert into deal_scanner.search_profiles(workspace_id, name, query)
            values (%s, 'forbidden', 'RTX 4070 Super')
            """,
            (workspace_one,),
        )


def test_extension_pairing_resolver_accepts_persistent_tokens_until_revoked(
    postgres: psycopg.Connection[tuple[object, ...]],
) -> None:
    workspace_id = _workspace_for(postgres, USER_ONE)
    token_hash = hashlib.sha256(b"persistent-extension-token").hexdigest()
    pairing = postgres.execute(
        """
        insert into deal_scanner.extension_pairings(
          workspace_id, created_by_user_id, token_hash, display_name, expires_at
        ) values (%s, %s, %s, 'Test Browser', null)
        returning id
        """,
        (workspace_id, USER_ONE, token_hash),
    ).fetchone()
    assert pairing is not None

    resolved = postgres.execute(
        "select workspace_id, user_id from deal_scanner.resolve_extension_pairing(%s)",
        (token_hash,),
    ).fetchone()
    assert resolved == (workspace_id, USER_ONE)

    postgres.execute(
        "update deal_scanner.extension_pairings set revoked_at = now() where id = %s",
        (pairing[0],),
    )
    assert (
        postgres.execute(
            "select workspace_id, user_id from deal_scanner.resolve_extension_pairing(%s)",
            (token_hash,),
        ).fetchone()
        is None
    )


def test_private_storage_policy_uses_workspace_path(postgres: psycopg.Connection[tuple[object, ...]]) -> None:
    workspace_one = _workspace_for(postgres, USER_ONE)
    object_name = f"{workspace_one}/fixture.png"
    with postgres.transaction():
        postgres.execute("set local role authenticated")
        postgres.execute("select set_config('request.jwt.claim.sub', %s, true)", (str(USER_ONE),))
        postgres.execute(
            "insert into storage.objects(bucket_id, name) values ('listing-images', %s)",
            (object_name,),
        )
    with postgres.transaction():
        postgres.execute("set local role authenticated")
        postgres.execute("select set_config('request.jwt.claim.sub', %s, true)", (str(USER_TWO),))
        visible = postgres.execute("select name from storage.objects where name = %s", (object_name,)).fetchall()
    assert visible == []


def test_ebay_deletion_audit_is_private_and_append_only_exception_is_owner_only(
    postgres: psycopg.Connection[tuple[object, ...]],
) -> None:
    workspace_id = _workspace_for(postgres, USER_ONE)
    listing_id = postgres.execute(
        """
        insert into deal_scanner.listings(
          workspace_id, platform, external_id, url, title, price, currency
        ) values (%s, 'ebay', 'deletion-rls-fixture', 'https://www.ebay.de/itm/123456789012',
                  'Deletion fixture', 100, 'EUR')
        returning id
        """,
        (workspace_id,),
    ).fetchone()
    assert listing_id is not None
    postgres.execute(
        """
        insert into deal_scanner.listing_snapshots(
          workspace_id, listing_id, content_hash, raw_data, provider_version, fetched_at
        ) values (%s, %s, %s, '{}', 'test-v1', now())
        """,
        (workspace_id, listing_id[0], uuid4().hex * 2),
    )

    with pytest.raises(psycopg.errors.RaiseException), postgres.transaction():
        postgres.execute("set local role authenticated")
        postgres.execute("select set_config('request.jwt.claim.sub', %s, true)", (str(USER_ONE),))
        postgres.execute("set local deal_scanner.account_deletion = 'on'")
        postgres.execute("delete from deal_scanner.listings where id = %s", (listing_id[0],))

    with postgres.transaction():
        postgres.execute("set local deal_scanner.account_deletion = 'on'")
        postgres.execute("delete from deal_scanner.listings where id = %s", (listing_id[0],))
    assert (
        postgres.execute(
            "select id from deal_scanner.listings where id = %s",
            (listing_id[0],),
        ).fetchone()
        is None
    )

    with pytest.raises(psycopg.errors.InsufficientPrivilege), postgres.transaction():
        postgres.execute("set local role authenticated")
        postgres.execute("select * from deal_scanner.ebay_account_deletion_events")


def test_postgres_skip_locked_allows_only_one_concurrent_job_claim(
    postgres: psycopg.Connection[tuple[object, ...]],
) -> None:
    assert POSTGRES_URL
    workspace_id = _workspace_for(postgres, USER_ONE)
    external_id = f"concurrent-{uuid4()}"
    listing_id = postgres.execute(
        """
        insert into deal_scanner.listings(
          workspace_id, platform, external_id, url, title, price, currency
        ) values (%s, 'manual', %s, 'https://www.ebay.de/itm/123456789012', 'Concurrent', 100, 'EUR')
        returning id
        """,
        (workspace_id, external_id),
    ).fetchone()
    assert listing_id is not None
    snapshot_id = postgres.execute(
        """
        insert into deal_scanner.listing_snapshots(
          workspace_id, listing_id, content_hash, raw_data, provider_version, fetched_at
        ) values (%s, %s, %s, '{}', 'test-v1', now()) returning id
        """,
        (workspace_id, listing_id[0], uuid4().hex * 2),
    ).fetchone()
    assert snapshot_id is not None
    job_id = postgres.execute(
        """
        insert into deal_scanner.analysis_jobs(
          workspace_id, listing_id, snapshot_id, job_type, required_capability,
          input_hash, status, available_at
        ) values (%s, %s, %s, 'text_analysis', 'text-small', %s, 'PENDING', now()) returning id
        """,
        (workspace_id, listing_id[0], snapshot_id[0], uuid4().hex * 2),
    ).fetchone()
    assert job_id is not None

    first = psycopg.connect(POSTGRES_URL)
    second = psycopg.connect(POSTGRES_URL)
    claim_sql = """
      select id from deal_scanner.analysis_jobs
      where id = %s and status in ('PENDING', 'RETRY') and available_at <= now()
      for update skip locked limit 1
    """
    try:
        first_claim = first.execute(claim_sql, (job_id[0],)).fetchone()
        second_claim = second.execute(claim_sql, (job_id[0],)).fetchone()
        assert first_claim is not None
        assert second_claim is None
    finally:
        first.rollback()
        second.rollback()
        first.close()
        second.close()

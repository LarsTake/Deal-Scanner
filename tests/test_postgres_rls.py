from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from deal_scanner_api.database import set_request_subject
from deal_scanner_api.db_models import SearchProfileRow, WorkspaceRow
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

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
    connection.execute(
        (root / "infrastructure/supabase/migrations/202607220001_initial.sql").read_text(encoding="utf-8")
    )
    connection.execute(
        (root / "infrastructure/supabase/migrations/202607230001_permanent_extension_connections.sql").read_text(
            encoding="utf-8"
        )
    )
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


async def test_request_context_survives_commit_and_new_physical_connection(
    postgres: psycopg.Connection[tuple[object, ...]],
) -> None:
    assert POSTGRES_URL
    url = POSTGRES_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    # NullPool forces a fresh physical connection after every commit/rollback.
    engine = create_async_engine(url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    workspace_one = _workspace_for(postgres, USER_ONE)
    workspace_two = _workspace_for(postgres, USER_TWO)
    profile_id = uuid4()
    try:
        async with factory() as session:
            session.info["deal_scanner_role"] = "authenticated"
            await set_request_subject(session, USER_ONE)
            profile = SearchProfileRow(
                id=profile_id,
                workspace_id=workspace_one,
                name="Commit regression",
                query="GPU",
                category_profile="computer",
                enabled_platforms=["kleinanzeigen"],
                required_terms=[],
                excluded_terms=[],
                required_products=[],
                excluded_products=[],
                notification_settings={},
            )
            session.add(profile)
            await session.commit()
            # This is the exact create_profile() path that failed in production.
            await session.refresh(profile)
            assert profile.name == "Commit regression"
            assert await session.scalar(text("select current_user")) == "authenticated"
            assert await session.scalar(text("show search_path")) == "deal_scanner,public"
            assert set((await session.scalars(select(WorkspaceRow.id))).all()) == {workspace_one}
            await session.rollback()
            # A new transaction must still apply the subject, role and schema.
            assert await session.get(SearchProfileRow, profile_id) is not None
            assert await session.scalar(text("select current_user")) == "authenticated"
            await session.commit()
        async with factory() as session:
            session.info["deal_scanner_role"] = "authenticated"
            await set_request_subject(session, USER_TWO)
            assert set((await session.scalars(select(WorkspaceRow.id))).all()) == {workspace_two}
            assert await session.get(SearchProfileRow, profile_id) is None
            await session.commit()
            assert await session.get(SearchProfileRow, profile_id) is None
        # Transaction-local state must not leak to a subsequent unconfigured connection.
        async with engine.connect() as connection:
            assert await connection.scalar(text("select current_user")) == "postgres"
            assert await connection.scalar(text("show search_path")) != "deal_scanner,public"
    finally:
        await engine.dispose()

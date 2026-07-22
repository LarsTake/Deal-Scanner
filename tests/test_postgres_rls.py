from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

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
    connection.execute(
        (root / "infrastructure/supabase/migrations/202607220001_initial.sql").read_text(encoding="utf-8")
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

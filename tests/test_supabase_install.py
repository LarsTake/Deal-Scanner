import importlib.util
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_first_install_bundle_is_current_and_guarded() -> None:
    spec = importlib.util.spec_from_file_location(
        "build_supabase_install", ROOT / "infrastructure/scripts/build_supabase_install.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sql = module.build_sql()
    assert sql == (ROOT / "infrastructure/supabase/install.sql").read_text(encoding="utf-8")
    assert sql.index("Schema deal_scanner already exists") < sql.index("create schema")
    assert "drop trigger" not in sql.lower()
    assert "on conflict (id) do update" not in sql.lower()
    assert "drop table" not in sql.lower()
    assert "drop schema" not in sql.lower()
    assert "begin;" in sql and "commit;" in sql
    assert "Existing on_auth_user_created trigger is protected" in sql
    assert "Existing listing-images/mail-archive buckets are protected" in sql
    assert "relrowsecurity" in sql
    assert "end;\n$preflight$;" in sql
    assert "end;\n$postflight$;" in sql
    assert "\nend\n$$;" not in sql
    assert "vidcnfueatvritaffkqh" not in sql
    for migration in (ROOT / "infrastructure/supabase/migrations").glob("*.sql"):
        assert f"Migration: {migration.name}" in sql

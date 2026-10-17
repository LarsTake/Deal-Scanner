import base64
import json

import pytest
from deal_scanner_api.public_config import public_auth_config
from deal_scanner_api.settings import Settings


def legacy_key(role: str) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"role": role}).encode()).decode().rstrip("=")
    return f"header.{payload}.signature"


@pytest.mark.parametrize("key", ["sb_publishable_fixture", legacy_key("anon")])
def test_public_config_exposes_only_public_auth_settings(key: str) -> None:
    settings = Settings(
        _env_file=None,
        auth_mode="supabase",
        supabase_url="https://project.example.test",
        supabase_publishable_key=key,
        supabase_service_role_key="never-expose-this",
        database_url="postgresql://private-password@db/private",
    )
    assert public_auth_config(settings) == {
        "authMode": "supabase",
        "supabaseUrl": "https://project.example.test",
        "supabasePublishableKey": key,
    }


@pytest.mark.parametrize("key", ["", "sb_secret_private", legacy_key("service_role"), "invalid.jwt.value"])
def test_private_or_invalid_key_is_never_published(key: str) -> None:
    settings = Settings(
        _env_file=None,
        auth_mode="supabase",
        supabase_url="https://project.example.test",
        supabase_publishable_key=key,
    )
    assert public_auth_config(settings)["supabasePublishableKey"] is None
    assert public_auth_config(settings)["supabaseUrl"] is None

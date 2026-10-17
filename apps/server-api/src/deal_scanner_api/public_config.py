import base64
import json

from .settings import Settings


def is_public_key(key: str) -> bool:
    if key.startswith("sb_publishable_"):
        return True
    # Legacy anon JWTs are public too; never publish a service_role JWT.
    try:
        parts = key.split(".")
        if len(parts) != 3:
            return False
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
        return isinstance(payload, dict) and payload.get("role") == "anon"
    except (ValueError, UnicodeError):
        return False


def public_auth_config(settings: Settings) -> dict[str, str | None]:
    enabled = settings.auth_mode == "supabase" and is_public_key(settings.supabase_publishable_key)
    return {
        "authMode": settings.auth_mode,
        "supabaseUrl": settings.supabase_url if enabled else None,
        "supabasePublishableKey": settings.supabase_publishable_key if enabled else None,
    }

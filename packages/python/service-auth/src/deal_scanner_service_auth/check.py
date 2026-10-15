from __future__ import annotations

import httpx

from .auth import ServiceAuthError, ServiceSettings, create_api_auth


async def run() -> None:
    settings = ServiceSettings()
    try:
        async with httpx.AsyncClient(base_url=settings.api_url, auth=create_api_auth(settings), timeout=30) as client:
            response = await client.get("/api/v1/auth/me")
            response.raise_for_status()
        print("OK: Dienstanmeldung und Workspace-Zugriff funktionieren.")
    except ServiceAuthError as error:
        print(f"FEHLER: {error}")
        raise SystemExit(1) from None
    except httpx.HTTPStatusError as error:
        print(f"FEHLER: API-Status {error.response.status_code}; keine Zugangsdaten ausgeben.")
        raise SystemExit(1) from None
    except (httpx.HTTPError, ValueError) as error:
        print(f"FEHLER: {type(error).__name__}; Konfiguration oder Dienstprotokoll pruefen.")
        raise SystemExit(1) from None

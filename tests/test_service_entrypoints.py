from collections.abc import Callable
from typing import Any

import pytest
from deal_scanner_scheduler import main as scheduler
from deal_scanner_worker import main as worker


@pytest.mark.parametrize("kind", ["worker", "scheduler"])
@pytest.mark.parametrize("mode", ["supabase", "static", "missing"])
def test_production_entrypoint_uses_shared_auth_validation(
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    mode: str,
) -> None:
    """Invoke run(), not just constructors; neither legacy guard may bypass refresh auth."""
    for key, value in {
        "DEAL_SCANNER_ENVIRONMENT": "production",
        "DEAL_SCANNER_SERVICE_AUTH_MODE": "supabase" if mode == "supabase" else "static",
        "DEAL_SCANNER_API_TOKEN": "fixture-static" if mode == "static" else "",
        "DEAL_SCANNER_DEVELOPMENT_USER_ID": "",
        "DEAL_SCANNER_SUPABASE_URL": "https://auth.example.test",
        "DEAL_SCANNER_SUPABASE_PUBLISHABLE_KEY": "fixture-publishable",
        "DEAL_SCANNER_SERVICE_EMAIL": "worker@example.test",
        "DEAL_SCANNER_SERVICE_PASSWORD_FILE": "/not-read-by-this-test/password",
        "DEAL_SCANNER_WORKER_MODE": "rules",
        "DEAL_SCANNER_KLEINANZEIGEN_WEB_ENABLED": "false",
        "DEAL_SCANNER_MYDEALZ_WEB_ENABLED": "false",
        "DEAL_SCANNER_VINTED_WEB_ENABLED": "false",
    }.items():
        monkeypatch.setenv(key, value)
    entered: list[str] = []

    async def stop_after_start(self: Any) -> None:
        entered.append(kind)
        await self.client.aclose()

    entrypoint: Callable[[], None]
    if kind == "worker":
        monkeypatch.setattr(worker.WorkerAgent, "run_forever", stop_after_start)
        entrypoint = worker.run
    else:
        monkeypatch.setattr(scheduler.Scheduler, "run_forever", stop_after_start)
        entrypoint = scheduler.run
    if mode == "missing":
        with pytest.raises(ValueError, match="Production services require"):
            entrypoint()
        assert entered == []
    else:
        entrypoint()
        assert entered == [kind]

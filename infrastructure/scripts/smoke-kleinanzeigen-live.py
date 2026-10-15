"""Read public search results and exercise the real API/worker in an isolated in-memory database."""

import argparse
import asyncio
import json
import os

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--query", default="gaming pc")
parser.add_argument("--limit", type=int, choices=range(1, 6), default=3)
parser.add_argument("--details", action="store_true")
arguments = parser.parse_args()

# Never import application settings before choosing the isolated database.
os.environ["DEAL_SCANNER_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DEAL_SCANNER_AUTO_CREATE_DB"] = "true"
os.environ["DEAL_SCANNER_AUTH_MODE"] = "development"
os.environ["DEAL_SCANNER_ENVIRONMENT"] = "development"
os.environ["DEAL_SCANNER_NTFY_URL"] = ""

import httpx  # noqa: E402
from deal_scanner_api.main import app  # noqa: E402
from deal_scanner_core.models import SearchProfile  # noqa: E402
from deal_scanner_kleinanzeigen_web import KleinanzeigenWebProvider, WebProviderSettings  # noqa: E402
from deal_scanner_worker.main import WorkerAgent, WorkerSettings  # noqa: E402


async def main() -> None:
    provider = KleinanzeigenWebProvider(
        WebProviderSettings(
            storage_file=None,
            fetch_details=arguments.details,
            maximum_details_per_scan=arguments.limit,
        )
    )
    try:
        snapshots = []
        async for snapshot in provider.discover(SearchProfile(name="Live smoke", query=arguments.query)):
            snapshots.append(snapshot)
            if len(snapshots) >= arguments.limit:
                break
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://isolated") as client:
                response = await client.post(
                    "/api/v1/search-profiles",
                    json={
                        "name": "Isolated live smoke",
                        "query": arguments.query,
                        "categoryProfile": "computer",
                        "enabledPlatforms": ["kleinanzeigen"],
                        "notificationSettings": {
                            "desktopEnabled": True,
                            "ntfyEnabled": False,
                            "notifyOnFirstRun": False,
                        },
                    },
                )
                response.raise_for_status()
                profile_id = response.json()["id"]
                response = await client.post(
                    "/api/v1/provider-sync-runs",
                    json={
                        "searchProfileId": profile_id,
                        "provider": "kleinanzeigen",
                    },
                )
                response.raise_for_status()
                run_id = response.json()["id"]
                listing_ids = []
                for snapshot in snapshots:
                    normalized = await provider.normalize(snapshot)
                    imported = await client.post(
                        "/api/v1/imports/manual",
                        json={
                            "platform": "kleinanzeigen",
                            "externalId": normalized.external_id,
                            "url": str(normalized.url),
                            "title": normalized.title,
                            "description": normalized.description,
                            "price": str(normalized.price.amount),
                            "location": normalized.location,
                            "categoryProfile": "computer",
                            "publishedAt": normalized.published_at.isoformat() if normalized.published_at else None,
                            "providerVersion": snapshot.provider_version,
                            "rawData": snapshot.payload,
                            "searchProfileId": profile_id,
                            "providerSyncRunId": run_id,
                        },
                    )
                    imported.raise_for_status()
                    listing_ids.append(imported.json()["listing"]["id"])
                response = await client.patch(
                    f"/api/v1/provider-sync-runs/{run_id}",
                    json={
                        "status": "COMPLETED",
                        "discoveredCount": len(snapshots),
                        "importedCount": len(listing_ids),
                    },
                )
                response.raise_for_status()
                worker = WorkerAgent(
                    WorkerSettings(
                        _env_file=None,
                        ollama_text_model="",
                        ollama_extraction_model="",
                        ollama_reasoning_model="",
                        ollama_vision_model="",
                        ollama_embedding_model="",
                        tesseract_command="disabled-for-smoke",
                    )
                )
                await worker.client.aclose()
                worker.client = client
                await worker.register()
                analyzed = 0
                for _ in listing_ids:
                    analyzed += int(await worker.process_one())
                notifications = await client.get("/api/v1/notifications?pending_only=true")
                notifications.raise_for_status()
                assert analyzed == len(listing_ids), "Not every live import was analyzed"
                assert not notifications.json(), "First scan must remain silent"
                print(
                    json.dumps(
                        {
                            "liveImports": len(listing_ids),
                            "analyzed": analyzed,
                            "baselineNotifications": 0,
                            "detailsEnabled": arguments.details,
                            "detailsLoaded": sum(bool(snapshot.payload.get("detailsLoaded")) for snapshot in snapshots),
                            "database": "isolated-in-memory",
                        }
                    )
                )
    finally:
        await provider.close()


asyncio.run(main())

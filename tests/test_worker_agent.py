from __future__ import annotations

from uuid import UUID

import httpx
import pytest
from deal_scanner_core.models import TextAnalysisResult
from deal_scanner_worker.main import WorkerAgent, WorkerSettings


async def test_rule_only_worker_produces_schema_valid_text_result() -> None:
    settings = WorkerSettings(
        _env_file=None,
        ollama_text_model="",
        ollama_extraction_model="",
        ollama_reasoning_model="",
        ollama_vision_model="",
        ollama_embedding_model="",
    )
    agent = WorkerAgent(settings)
    try:
        result, analysis_type, model_name, prompt_version, confidence = await agent._analyze(
            {
                "jobType": "text_analysis",
                "listingId": "00000000-0000-4000-8000-000000000123",
                "payload": {
                    "title": "Gaming PC RTX 4070 Super",
                    "description": "Abholung und Funktionstest möglich.",
                    "categoryProfile": "computer",
                },
            }
        )
        validated = TextAnalysisResult.model_validate(result)
        assert analysis_type == "text"
        assert model_name == "rules-v1"
        assert prompt_version == "rules-v1"
        assert confidence == validated.overall_confidence
        assert validated.products[0].model == "RTX 4070 Super"
        assert validated.missing_information
    finally:
        await agent.client.aclose()


async def test_worker_reconnects_after_transient_api_failure() -> None:
    class StopLoop(RuntimeError):
        pass

    class FlakyWorker(WorkerAgent):
        register_calls = 0

        async def register(self) -> None:
            self.register_calls += 1
            if self.register_calls == 1:
                raise httpx.ConnectError("API temporarily unavailable")
            self.worker_id = UUID("00000000-0000-4000-8000-000000000456")

        async def process_one(self) -> bool:
            raise StopLoop

    agent = FlakyWorker(WorkerSettings(_env_file=None, worker_poll_seconds=0))
    with pytest.raises(StopLoop):
        await agent.run_forever()
    assert agent.register_calls == 2


async def test_rules_mode_disables_models_and_deep_fallback() -> None:
    agent = WorkerAgent(WorkerSettings(_env_file=None, worker_mode="rules"))
    try:
        assert agent.capabilities == ["rules"]
        assert not agent.ollama.configured_models
        assert agent.tesseract_path is None
        job = {
            "jobType": "rule_analysis",
            "listingId": "00000000-0000-4000-8000-000000000123",
            "payload": {"title": "RTX 4070 Super", "description": "", "categoryProfile": "computer"},
        }
        assert (await agent._analyze(job))[2] == "rules-v1"
        job["jobType"] = "deep_text_analysis"
        with pytest.raises(RuntimeError):
            await agent._analyze(job)
    finally:
        await agent.client.aclose()

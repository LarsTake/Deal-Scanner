from __future__ import annotations

import json
from uuid import UUID

import httpx
from deal_scanner_core.models import TextAnalysisRequest
from deal_scanner_worker.ollama import OllamaProvider


async def test_ollama_routes_text_vision_and_embeddings_to_assigned_models() -> None:
    requests: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        if request.url.path == "/api/embed":
            return httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3]]})
        if payload["model"] == "gemma4:12b" and payload["messages"][1].get("images"):
            return httpx.Response(
                200,
                json={
                    "message": {"content": json.dumps({"text": "RTX 4070 Super", "language": "de", "confidence": 0.93})}
                },
            )
        if payload["model"] == "gemma4:12b":
            return httpx.Response(
                200,
                json={
                    "message": {
                        "content": json.dumps(
                            {
                                "category": "computer",
                                "products": [
                                    {
                                        "productType": "gpu",
                                        "manufacturer": "NVIDIA",
                                        "model": "RTX 4070 Super",
                                        "quantity": 1,
                                        "confidence": 0.95,
                                        "sources": ["title"],
                                        "evidence": "RTX 4070 Super",
                                    }
                                ],
                                "attributes": [],
                                "riskSignals": [],
                                "contradictions": [],
                                "missingInformation": ["Kaufbeleg"],
                                "overallConfidence": 0.9,
                            }
                        )
                    }
                },
            )
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": json.dumps(
                        {
                            "riskSignals": [
                                {
                                    "signalType": "missing_proof",
                                    "severity": "low",
                                    "confidence": 0.7,
                                    "source": "description",
                                    "evidence": "Kein Kaufbeleg genannt",
                                }
                            ],
                            "contradictions": [],
                            "missingInformation": ["Seriennummer"],
                            "overallConfidence": 0.8,
                        }
                    )
                }
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OllamaProvider(
            "http://ollama.test",
            "gemma4:12b",
            client,
            reasoning_model="gpt-oss:latest",
            vision_model="gemma4:12b",
            embedding_model="qwen3-embedding:0.6b",
        )
        text_result = await provider.analyze_text(
            TextAnalysisRequest(
                listing_id=UUID("00000000-0000-4000-8000-000000000123"),
                title="Gaming PC RTX 4070 Super",
                description="Kein Kaufbeleg genannt",
                category_profile="computer",
            )
        )
        image_result = await provider.analyze_image(
            UUID("00000000-0000-4000-8000-000000000456"),
            b"fake-image",
        )
        embeddings = await provider.embed_texts(["RTX 4070 Super"])

    assert [request["model"] for request in requests] == [
        "gemma4:12b",
        "gpt-oss:latest",
        "gemma4:12b",
        "qwen3-embedding:0.6b",
    ]
    assert text_result.products[0].model == "RTX 4070 Super"
    assert text_result.risk_signals[0].signal_type == "missing_proof"
    assert text_result.missing_information == ["Kaufbeleg", "Seriennummer"]
    assert text_result.overall_confidence == 0.87
    assert image_result.engine == "ollama:gemma4:12b"
    assert image_result.text == "RTX 4070 Super"
    assert embeddings == [[0.1, 0.2, 0.3]]

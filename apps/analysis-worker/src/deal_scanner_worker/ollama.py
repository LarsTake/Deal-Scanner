from __future__ import annotations

import json
from typing import Any

import httpx
from deal_scanner_core.models import (
    ModelProviderStatus,
    TextAnalysisRequest,
    TextAnalysisResult,
)


class OllamaProvider:
    def __init__(self, base_url: str, model: str, client: httpx.AsyncClient) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.client = client

    async def analyze_text(self, request: TextAnalysisRequest) -> TextAnalysisResult:
        schema = TextAnalysisResult.model_json_schema(by_alias=True)
        response = await self.client.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "stream": False,
                "format": schema,
                "options": {"temperature": 0},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Extrahiere nur explizit erkennbare Fakten. Unbekannte Werte bleiben null. "
                            "Risikosignale sind Warnhinweise und niemals Betrugsbeweise. "
                            "Antworte ausschließlich im vorgegebenen JSON-Schema."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(request.model_dump(mode="json", by_alias=True), ensure_ascii=False),
                    },
                ],
            },
            timeout=180,
        )
        response.raise_for_status()
        content = response.json()["message"]["content"]
        return TextAnalysisResult.model_validate_json(content)

    async def analyze_images(self, request: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("Vision analysis is prepared but not enabled in MVP")

    async def health_check(self) -> ModelProviderStatus:
        try:
            response = await self.client.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            models = [item["name"] for item in response.json().get("models", [])]
            return ModelProviderStatus(
                available=self.model in models,
                provider="ollama",
                models=models,
                detail=None if self.model in models else f"configured model {self.model} is not installed",
            )
        except httpx.HTTPError as exc:
            return ModelProviderStatus(available=False, provider="ollama", detail=str(exc))

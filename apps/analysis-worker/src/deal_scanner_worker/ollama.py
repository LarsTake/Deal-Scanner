from __future__ import annotations

import base64
import json
from typing import Any
from uuid import UUID

import httpx
from deal_scanner_core.models import (
    AiRiskSignal,
    CamelModel,
    Contradiction,
    ImageOcrResult,
    ModelProviderStatus,
    TextAnalysisRequest,
    TextAnalysisResult,
)
from pydantic import Field


class RiskReview(CamelModel):
    risk_signals: list[AiRiskSignal] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    overall_confidence: float = Field(ge=0, le=1)


class VisionText(CamelModel):
    text: str = Field(max_length=100_000)
    language: str | None = Field(default=None, max_length=32)
    confidence: float = Field(ge=0, le=1)


class OllamaProvider:
    def __init__(
        self,
        base_url: str,
        model: str,
        client: httpx.AsyncClient,
        *,
        reasoning_model: str = "",
        vision_model: str = "",
        embedding_model: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.reasoning_model = reasoning_model
        self.vision_model = vision_model
        self.embedding_model = embedding_model
        self.client = client

    @property
    def configured_models(self) -> list[str]:
        return list(
            dict.fromkeys(
                model
                for model in (
                    self.model,
                    self.reasoning_model,
                    self.vision_model,
                    self.embedding_model,
                )
                if model
            )
        )

    async def _chat(
        self,
        *,
        model: str,
        schema: type[CamelModel],
        system: str,
        user: str,
        images: list[str] | None = None,
        think: bool | str = False,
        request_timeout: float = 180,
    ) -> CamelModel:
        json_schema = schema.model_json_schema(by_alias=True)
        user_message: dict[str, Any] = {"role": "user", "content": user}
        if images:
            user_message["images"] = images
        response = await self.client.post(
            f"{self.base_url}/api/chat",
            json={
                "model": model,
                "stream": False,
                "think": think,
                "format": json_schema,
                "options": {"temperature": 0},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            f"{system}\n"
                            "Antworte ausschließlich mit JSON, das exakt diesem Schema entspricht:\n"
                            f"{json.dumps(json_schema, ensure_ascii=False)}"
                        ),
                    },
                    user_message,
                ],
            },
            timeout=request_timeout,
        )
        response.raise_for_status()
        content = response.json()["message"]["content"]
        return schema.model_validate_json(content)

    async def analyze_text(self, request: TextAnalysisRequest) -> TextAnalysisResult:
        if not self.model:
            raise RuntimeError("Kein Ollama-Modell für die Faktenextraktion konfiguriert")
        serialized_request = json.dumps(
            request.model_dump(mode="json", by_alias=True),
            ensure_ascii=False,
        )
        facts = await self._chat(
            model=self.model,
            schema=TextAnalysisResult,
            think=False,
            system=(
                "Du extrahierst Produkt-, Komponenten- und Zustandsdaten aus deutschen "
                "Kleinanzeigen. Übernimm nur explizit erkennbare Fakten und erfinde keine "
                "Modellnummern. Unbekannte Werte bleiben leer. Gib riskSignals und "
                "contradictions leer zurück; diese prüft ein separates Reasoning-Modell."
            ),
            user=serialized_request,
        )
        assert isinstance(facts, TextAnalysisResult)
        if not self.reasoning_model:
            return facts

        review = await self._chat(
            model=self.reasoning_model,
            schema=RiskReview,
            think="low",
            system=(
                "Du bist die zweite, unabhängige Prüfstufe eines Deal-Scanners. Suche nur "
                "nach Widersprüchen, verdächtigen Formulierungen und fehlenden Angaben, die "
                "aus dem Inserat und den extrahierten Fakten belegbar sind. Risikosignale sind "
                "Warnhinweise und niemals Betrugsbeweise. Erfinde keine neuen Produktdaten."
            ),
            user=json.dumps(
                {
                    "listing": request.model_dump(mode="json", by_alias=True),
                    "extractedFacts": facts.model_dump(mode="json", by_alias=True),
                },
                ensure_ascii=False,
            ),
        )
        assert isinstance(review, RiskReview)
        missing_information = list(dict.fromkeys([*facts.missing_information, *review.missing_information]))
        return facts.model_copy(
            update={
                "risk_signals": review.risk_signals,
                "contradictions": review.contradictions,
                "missing_information": missing_information,
                "overall_confidence": round(
                    (facts.overall_confidence * 0.7) + (review.overall_confidence * 0.3),
                    4,
                ),
            }
        )

    async def analyze_image(self, image_id: UUID, content: bytes) -> ImageOcrResult:
        if not self.vision_model:
            raise RuntimeError("Kein Ollama-Vision-Modell konfiguriert")
        vision = await self._chat(
            model=self.vision_model,
            schema=VisionText,
            think=False,
            system=(
                "Lies ausschließlich sichtbaren Text aus dem Bild. Bewahre Modellnummern, "
                "Einheiten, Preise und Zeilenumbrüche möglichst genau. Beschreibe das Bild "
                "nicht und ergänze keine nicht sichtbaren Informationen."
            ),
            user="Extrahiere den sichtbaren Text aus diesem Angebotsbild.",
            images=[base64.b64encode(content).decode("ascii")],
        )
        assert isinstance(vision, VisionText)
        return ImageOcrResult(
            image_id=image_id,
            text=vision.text,
            language=vision.language,
            confidence=vision.confidence,
            engine=f"ollama:{self.vision_model}",
        )

    async def embed_texts(self, inputs: list[str]) -> list[list[float]]:
        if not self.embedding_model:
            raise RuntimeError("Kein Ollama-Embedding-Modell konfiguriert")
        response = await self.client.post(
            f"{self.base_url}/api/embed",
            json={"model": self.embedding_model, "input": inputs},
            timeout=180,
        )
        response.raise_for_status()
        return list(response.json()["embeddings"])

    async def health_check(self) -> ModelProviderStatus:
        try:
            response = await self.client.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            models = [item["name"] for item in response.json().get("models", [])]
            missing = [model for model in self.configured_models if model not in models]
            return ModelProviderStatus(
                available=not missing,
                provider="ollama",
                models=models,
                detail=(None if not missing else f"configured models not installed: {', '.join(missing)}"),
            )
        except httpx.HTTPError as exc:
            return ModelProviderStatus(available=False, provider="ollama", detail=str(exc))

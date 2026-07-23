from __future__ import annotations

import asyncio
import platform
import shutil
import socket
from contextlib import suppress
from io import BytesIO
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import UUID

import httpx
import psutil
import pytesseract  # type: ignore[import-untyped]
import structlog
from deal_scanner_core.models import ImageOcrResult, TextAnalysisRequest, TextAnalysisResult
from deal_scanner_extraction import RuleExtractor
from PIL import Image
from pydantic_settings import BaseSettings, SettingsConfigDict

from .ollama import OllamaProvider

logger = structlog.get_logger("deal_scanner_worker")


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DEAL_SCANNER_", env_file=".env", extra="ignore")

    environment: str = "development"
    api_url: str = "http://127.0.0.1:8000"
    api_token: str | None = None
    development_user_id: str | None = None
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_text_model: str = ""
    worker_name: str = "local-analysis-worker"
    worker_poll_seconds: float = 5.0
    worker_renew_seconds: float = 90.0
    tesseract_command: str = "tesseract"
    ocr_language: str = "deu+eng"
    health_file: str = ""


class WorkerAgent:
    def __init__(self, settings: WorkerSettings) -> None:
        self.settings = settings
        headers: dict[str, str] = {}
        if settings.api_token:
            headers["Authorization"] = f"Bearer {settings.api_token}"
        if settings.development_user_id:
            headers["X-Development-User"] = settings.development_user_id
        self.client = httpx.AsyncClient(base_url=settings.api_url, headers=headers, timeout=30)
        self.ollama = OllamaProvider(settings.ollama_url, settings.ollama_text_model, self.client)
        self.worker_id: UUID | None = None
        self.tesseract_path = shutil.which(settings.tesseract_command)
        if self.tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_path
        self.capabilities = (
            ["rules"]
            + (["text-small"] if settings.ollama_text_model else [])
            + (["ocr"] if self.tesseract_path else [])
        )

    async def register(self) -> None:
        health = await self.ollama.health_check() if self.settings.ollama_text_model else None
        gpu, vram_gb = await self._detect_gpu()
        response = await self.client.post(
            "/api/v1/workers/register",
            json={
                "name": self.settings.worker_name,
                "operatingSystem": platform.platform(),
                "hostname": socket.gethostname(),
                "cpu": platform.processor() or None,
                "ramGb": round(psutil.virtual_memory().total / 1024**3, 2),
                "gpu": gpu,
                "vramGb": vram_gb,
                "runtime": {
                    "python": platform.python_version(),
                    "ollama": self.settings.ollama_url,
                },
                "capabilities": self.capabilities,
                "installedModels": health.models if health else [],
            },
        )
        response.raise_for_status()
        self.worker_id = UUID(response.json()["id"])

    async def _detect_gpu(self) -> tuple[str | None, float | None]:
        executable = shutil.which("nvidia-smi")
        if executable is None:
            return None, None
        try:
            process = await asyncio.create_subprocess_exec(
                executable,
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=5)
            if process.returncode != 0 or not stdout:
                return None, None
            first = stdout.decode(errors="replace").splitlines()[0]
            name, memory_mib = (part.strip() for part in first.rsplit(",", 1))
            return name, round(float(memory_mib) / 1024, 2)
        except (OSError, ValueError, TimeoutError):
            return None, None

    async def heartbeat(self) -> None:
        assert self.worker_id
        response = await self.client.post(
            f"/api/v1/workers/{self.worker_id}/heartbeat",
            json={"currentLoad": psutil.cpu_percent() / 100, "capabilities": self.capabilities},
        )
        response.raise_for_status()

    async def process_one(self) -> bool:
        assert self.worker_id
        response = await self.client.post(
            "/api/v1/jobs/claim",
            json={"workerId": str(self.worker_id), "capabilities": self.capabilities},
        )
        response.raise_for_status()
        job = response.json()
        if not job:
            return False
        started_at = perf_counter()
        logger.info("job_claimed", job_id=job["id"], job_type=job["jobType"], attempts=job["attempts"])
        renewal = asyncio.create_task(self._renew_while_running(job["id"]))
        try:
            result, analysis_type, model_name, confidence = await self._analyze(job)
            completion = await self.client.post(
                f"/api/v1/jobs/{job['id']}/complete",
                json={
                    "workerId": str(self.worker_id),
                    "analysisType": analysis_type,
                    "modelName": model_name,
                    "modelVersion": "local",
                    "promptVersion": "text-v1",
                    "resultSchemaVersion": "1.0.0",
                    "inputHash": job["inputHash"],
                    "result": result,
                    "confidence": confidence,
                },
            )
            completion.raise_for_status()
            logger.info(
                "job_completed",
                job_id=job["id"],
                job_type=job["jobType"],
                duration_ms=round((perf_counter() - started_at) * 1000, 2),
            )
        except Exception as exc:
            failure = await self.client.post(
                f"/api/v1/jobs/{job['id']}/fail",
                json={"workerId": str(self.worker_id), "error": str(exc)[:4000]},
            )
            failure.raise_for_status()
            logger.error(
                "job_failed",
                job_id=job["id"],
                job_type=job["jobType"],
                error_type=type(exc).__name__,
                duration_ms=round((perf_counter() - started_at) * 1000, 2),
            )
        finally:
            renewal.cancel()
            with suppress(asyncio.CancelledError):
                await renewal
        return True

    async def _renew_while_running(self, job_id: str) -> None:
        assert self.worker_id
        while True:
            await asyncio.sleep(self.settings.worker_renew_seconds)
            response = await self.client.post(
                f"/api/v1/jobs/{job_id}/renew",
                json={"workerId": str(self.worker_id)},
            )
            response.raise_for_status()
            self._mark_healthy()

    async def _analyze(self, job: dict[str, Any]) -> tuple[dict[str, Any], str, str, float]:
        payload = job["payload"]
        if job["jobType"] == "image_ocr":
            if not self.tesseract_path:
                raise RuntimeError("OCR job claimed without an available Tesseract runtime")
            access = await self.client.get(payload["imageAccessPath"])
            access.raise_for_status()
            image_url = access.json()["url"]
            if image_url.startswith("http://") or image_url.startswith("https://"):
                async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
                    image_response = await client.get(image_url)
            else:
                image_response = await self.client.get(image_url)
            image_response.raise_for_status()
            text = await asyncio.to_thread(self._ocr, image_response.content)
            confidence = 0.7 if text.strip() else 0.2
            ocr_result = ImageOcrResult(
                image_id=UUID(payload["imageId"]),
                text=text[:100_000],
                language=self.settings.ocr_language,
                confidence=confidence,
                engine="tesseract",
            )
            return ocr_result.model_dump(mode="json", by_alias=True), "image_ocr", "tesseract", confidence
        request = TextAnalysisRequest(
            listing_id=UUID(job["listingId"]),
            title=payload["title"],
            description=payload["description"],
            category_profile=payload["categoryProfile"],
        )
        if self.settings.ollama_text_model:
            text_result = await self.ollama.analyze_text(request)
            model_name = self.settings.ollama_text_model
        else:
            rule_analysis = RuleExtractor().analyze(request.title, request.description)
            product_confidences = [product.confidence for product in rule_analysis.products]
            text_result = TextAnalysisResult(
                category=request.category_profile,
                products=rule_analysis.products,
                overall_confidence=(
                    sum(product_confidences) / len(product_confidences) if product_confidences else 0.5
                ),
                missing_information=[
                    "Kein lokales Textmodell konfiguriert; Ergebnis basiert ausschließlich auf Regeln."
                ],
            )
            model_name = "rules-v1"
        return (
            text_result.model_dump(mode="json", by_alias=True),
            "text",
            model_name,
            text_result.overall_confidence,
        )

    def _ocr(self, content: bytes) -> str:
        with Image.open(BytesIO(content)) as image:
            image.load()
            return str(pytesseract.image_to_string(image, lang=self.settings.ocr_language))

    async def run_forever(self) -> None:
        heartbeat_counter = 0
        try:
            while True:
                try:
                    if self.worker_id is None:
                        await self.register()
                        self._mark_healthy()
                    worked = await self.process_one()
                    self._mark_healthy()
                    heartbeat_counter += 1
                    if heartbeat_counter >= 6:
                        await self.heartbeat()
                        heartbeat_counter = 0
                    if not worked:
                        await asyncio.sleep(self.settings.worker_poll_seconds)
                except httpx.HTTPError as exc:
                    logger.warning("api_unavailable", error_type=type(exc).__name__, detail=str(exc))
                    self.worker_id = None
                    heartbeat_counter = 0
                    await asyncio.sleep(self.settings.worker_poll_seconds)
        finally:
            await self.client.aclose()

    def _mark_healthy(self) -> None:
        if self.settings.health_file:
            Path(self.settings.health_file).touch()


def run() -> None:
    structlog.configure(processors=[structlog.processors.TimeStamper(fmt="iso"), structlog.processors.JSONRenderer()])
    settings = WorkerSettings()
    if settings.environment == "production" and not settings.api_token:
        raise RuntimeError("production analysis worker requires an API token")
    asyncio.run(WorkerAgent(settings).run_forever())

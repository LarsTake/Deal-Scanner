from __future__ import annotations

import asyncio
import platform
import shutil
import socket
import subprocess
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
    supabase_service_role_key: str = ""
    development_user_id: str | None = None
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_text_model: str = ""
    ollama_extraction_model: str = "gemma4:12b"
    ollama_reasoning_model: str = "gpt-oss:latest"
    ollama_vision_model: str = "gemma4:12b"
    ollama_embedding_model: str = "qwen3-embedding:0.6b"
    worker_name: str = "local-analysis-worker"
    worker_poll_seconds: float = 5.0
    worker_renew_seconds: float = 90.0
    worker_concurrency: int = 2
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
        if settings.supabase_service_role_key:
            headers["X-Internal-Key"] = settings.supabase_service_role_key
        self.client = httpx.AsyncClient(base_url=settings.api_url, headers=headers, timeout=30)
        extraction_model = settings.ollama_extraction_model or settings.ollama_text_model
        self.ollama = OllamaProvider(
            settings.ollama_url,
            extraction_model,
            self.client,
            reasoning_model=settings.ollama_reasoning_model,
            vision_model=settings.ollama_vision_model,
            embedding_model=settings.ollama_embedding_model,
        )
        self.worker_id: UUID | None = None
        self.tesseract_path = shutil.which(settings.tesseract_command)
        if self.tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_path
        self.capabilities = (
            ["rules"]
            + (["text-small"] if self.ollama.model else [])
            + (["ocr"] if self.ollama.vision_model or self.tesseract_path else [])
            + (["vision"] if self.ollama.vision_model else [])
            + (["embedding"] if self.ollama.embedding_model else [])
        )

    async def register(self) -> None:
        await self._load_model_configuration()
        health = await self.ollama.health_check() if self.ollama.configured_models else None
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
                    "modelAssignments": {
                        "extraction": self.ollama.model,
                        "reasoning": self.ollama.reasoning_model,
                        "vision": self.ollama.vision_model,
                        "embedding": self.ollama.embedding_model,
                    },
                },
                "capabilities": self.capabilities,
                "installedModels": health.models if health else [],
            },
        )
        response.raise_for_status()
        self.worker_id = UUID(response.json()["id"])

    async def _load_model_configuration(self) -> None:
        response = await self.client.get("/api/v1/provider-configurations")
        if response.status_code >= 400:
            return
        configuration = next(
            (item for item in response.json() if item.get("provider") == "ollama" and item.get("enabled")),
            None,
        )
        if configuration is None:
            return
        values = configuration.get("settings") or {}
        self.ollama.model = str(values.get("extractionModel") or self.ollama.model)
        self.ollama.reasoning_model = str(values.get("reasoningModel") or self.ollama.reasoning_model)
        self.ollama.vision_model = str(values.get("visionModel") or self.ollama.vision_model)
        self.ollama.embedding_model = str(values.get("embeddingModel") or self.ollama.embedding_model)

    async def _detect_gpu(self) -> tuple[str | None, float | None]:
        return await asyncio.to_thread(self._detect_gpu_sync)

    @staticmethod
    def _detect_gpu_sync() -> tuple[str | None, float | None]:
        executable = shutil.which("nvidia-smi") or shutil.which("nvidia-smi.exe")
        if executable is None:
            candidates = [
                r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
                r"C:\Windows\System32\nvidia-smi.exe",
            ]
            for cand in candidates:
                if Path(cand).is_file():
                    executable = cand
                    break
            if executable is None and platform.system() == "Windows":
                driver_store = Path(r"C:\Windows\System32\DriverStore\FileRepository")
                if driver_store.is_dir():
                    found = list(driver_store.glob("**/nvidia-smi.exe"))
                    if found:
                        executable = str(found[0])
        if executable is None:
            return None, None
        try:
            process = subprocess.run(  # noqa: S603 - executable is resolved from trusted system paths
                [executable,
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits"],
                capture_output=True,
                check=False,
                timeout=5,
            )
            if process.returncode != 0 or not process.stdout:
                return None, None
            first = process.stdout.decode(errors="replace").splitlines()[0]
            name, memory_mib = (part.strip() for part in first.rsplit(",", 1))
            return name, round(float(memory_mib) / 1024, 2)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return None, None

    async def heartbeat(self) -> None:
        assert self.worker_id
        await self._load_model_configuration()
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
            result, analysis_type, model_name, prompt_version, confidence = await self._analyze(job)
            completion = await self.client.post(
                f"/api/v1/jobs/{job['id']}/complete",
                json={
                    "workerId": str(self.worker_id),
                    "analysisType": analysis_type,
                    "modelName": model_name,
                    "modelVersion": "local",
                    "promptVersion": prompt_version,
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
                detail=str(exc)[:1000],
                exc_info=True,
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

    async def _analyze(self, job: dict[str, Any]) -> tuple[dict[str, Any], str, str, str, float]:
        payload = job["payload"]
        if job["jobType"] == "image_ocr":
            access = await self.client.get(payload["imageAccessPath"])
            access.raise_for_status()
            image_url = access.json()["url"]
            if image_url.startswith("http://") or image_url.startswith("https://"):
                async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
                    image_response = await client.get(image_url)
            else:
                image_response = await self.client.get(image_url)
            image_response.raise_for_status()
            image_id = UUID(payload["imageId"])
            if self.ollama.vision_model:
                try:
                    ocr_result = await self.ollama.analyze_image(image_id, image_response.content)
                    return (
                        ocr_result.model_dump(mode="json", by_alias=True),
                        "image_ocr",
                        self.ollama.vision_model,
                        "vision-ocr-v1",
                        ocr_result.confidence,
                    )
                except (httpx.HTTPError, ValueError) as exc:
                    if not self.tesseract_path:
                        raise
                    logger.warning(
                        "vision_ocr_failed_using_tesseract",
                        error_type=type(exc).__name__,
                    )
            if not self.tesseract_path:
                raise RuntimeError("OCR job claimed without an available OCR runtime")
            text = await asyncio.to_thread(self._ocr, image_response.content)
            confidence = 0.7 if text.strip() else 0.2
            ocr_result = ImageOcrResult(
                image_id=image_id,
                text=text[:100_000],
                language=self.settings.ocr_language,
                confidence=confidence,
                engine="tesseract",
            )
            return (
                ocr_result.model_dump(mode="json", by_alias=True),
                "image_ocr",
                "tesseract",
                "ocr-v1",
                confidence,
            )
        request = TextAnalysisRequest(
            listing_id=UUID(job["listingId"]),
            title=payload["title"],
            description=payload["description"],
            category_profile=payload["categoryProfile"],
        )
        if self.ollama.model:
            text_result = await self.ollama.analyze_text(request)
            model_name = "+".join(
                dict.fromkeys(model for model in (self.ollama.model, self.ollama.reasoning_model) if model)
            )
            prompt_version = "text-routed-v2"
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
            prompt_version = "rules-v1"
        return (
            text_result.model_dump(mode="json", by_alias=True),
            "text",
            model_name,
            prompt_version,
            text_result.overall_confidence,
        )

    def _ocr(self, content: bytes) -> str:
        with Image.open(BytesIO(content)) as image:
            image.load()
            return str(pytesseract.image_to_string(image, lang=self.settings.ocr_language))

    async def run_forever(self) -> None:
        try:
            while True:
                try:
                    if self.worker_id is None:
                        await self.register()
                        self._mark_healthy()

                    async def _worker_loop() -> None:
                        heartbeat_counter = 0
                        while self.worker_id is not None:
                            worked = await self.process_one()
                            self._mark_healthy()
                            heartbeat_counter += 1
                            if heartbeat_counter >= 6:
                                await self.heartbeat()
                                heartbeat_counter = 0
                            if not worked:
                                await asyncio.sleep(self.settings.worker_poll_seconds)

                    concurrency = max(1, self.settings.worker_concurrency)
                    tasks = [asyncio.create_task(_worker_loop()) for _ in range(concurrency)]
                    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
                    for task in pending:
                        task.cancel()
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for result in results:
                        if isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError):
                            raise result
                except httpx.HTTPError as exc:
                    logger.warning("api_unavailable", error_type=type(exc).__name__, detail=str(exc))
                    self.worker_id = None
                    await asyncio.sleep(self.settings.worker_poll_seconds)
        finally:
            await self.client.aclose()

    def _mark_healthy(self) -> None:
        if self.settings.health_file:
            Path(self.settings.health_file).touch()


def run() -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    )
    settings = WorkerSettings()
    if settings.environment == "production" and not (
        settings.api_token or settings.supabase_service_role_key
    ):
        raise RuntimeError("production analysis worker requires internal authentication")
    asyncio.run(WorkerAgent(settings).run_forever())

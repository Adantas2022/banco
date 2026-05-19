import time
from pathlib import Path
from typing import Optional

from irpf_processor.shared.logging import get_logger

from .interfaces import IOcrEngine
from .models import OcrExtractionError, OcrResult, PdfType

logger = get_logger(__name__)


class OcrOrchestrator:

    DEFAULT_MIN_CONFIDENCE = 0.5

    def __init__(
        self,
        engines: list[IOcrEngine],
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    ):
        self._engines = engines
        self._min_confidence = min_confidence

    @property
    def engines(self) -> list[IOcrEngine]:
        return self._engines

    def add_engine(self, engine: IOcrEngine) -> None:
        self._engines.append(engine)

    def remove_engine(self, engine_name: str) -> None:
        self._engines = [e for e in self._engines if e.name != engine_name]

    def process(
        self,
        pdf_path: Path,
        timeout: Optional[int] = None,
        min_confidence: Optional[float] = None,
        preprocess: bool = True,
    ) -> OcrResult:
        min_conf = min_confidence or self._min_confidence
        start_time = time.perf_counter()

        available_engines = [e for e in self._engines if e.is_available()]

        if not available_engines:
            raise OcrExtractionError("No OCR engines available")

        logger.info(
            "Starting OCR orchestration",
            available_engines=[e.name for e in available_engines],
            pdf_path=str(pdf_path),
        )

        attempts = []
        best_result = None

        for engine in available_engines:
            try:
                logger.info("Trying OCR engine", engine=engine.name)

                result = engine.extract(pdf_path, timeout=timeout)
                attempts.append({
                    "engine": engine.name,
                    "success": True,
                    "confidence": result.confidence,
                })

                if result.confidence >= min_conf:
                    if best_result is None or result.confidence > best_result.confidence:
                        best_result = result

                    if result.confidence >= 0.8:
                        logger.info(
                            "High confidence result found",
                            engine=engine.name,
                            confidence=result.confidence,
                        )
                        break

            except Exception as e:
                logger.warning(
                    "OCR engine failed",
                    engine=engine.name,
                    error=str(e),
                )
                attempts.append({
                    "engine": engine.name,
                    "success": False,
                    "error": str(e),
                })
                continue

        if best_result is None:
            raise OcrExtractionError(
                f"All OCR engines failed or returned low confidence. Attempts: {attempts}"
            )

        total_time = time.perf_counter() - start_time

        best_result.metadata["attempts"] = attempts
        best_result.metadata["total_processing_time"] = total_time
        best_result.processing_time = total_time

        logger.info(
            "OCR orchestration completed",
            engine_used=best_result.engine_used,
            confidence=best_result.confidence,
            total_time=total_time,
            attempts=len(attempts),
        )

        return best_result

    def _get_best_result(self, results: list[OcrResult]) -> OcrResult:
        return max(results, key=lambda r: r.confidence)

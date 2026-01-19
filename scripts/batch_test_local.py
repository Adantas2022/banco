#!/usr/bin/env python3

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from irpf_processor.infrastructure.extraction import IRPFParser
from irpf_processor.infrastructure.extraction.ocr.pdf_type_detector import PdfTypeDetector
from irpf_processor.infrastructure.extraction.ocr.models import PdfType, OcrExtractionError
from irpf_processor.infrastructure.extraction.ocr.ocr_orchestrator import OcrOrchestrator
from irpf_processor.infrastructure.extraction.ocr.tesseract_engine import TesseractEngine


def requires_ocr(pdf_type: PdfType) -> bool:
    return pdf_type in (PdfType.IMAGE, PdfType.MIXED)


@dataclass
class BatchTestConfig:
    pdf_dir: Path = field(default_factory=lambda: Path("./pdfs"))
    output: Path = field(default_factory=lambda: Path("./batch_results_local.json"))
    min_confidence: float = 0.7


@dataclass
class TaxpayerInfo:
    cpf: Optional[str] = None
    name: Optional[str] = None
    exercise_year: Optional[str] = None


@dataclass
class TestResult:
    filename: str
    status: str
    processing_time: float
    confidence: Optional[float] = None
    taxpayer: TaxpayerInfo = field(default_factory=TaxpayerInfo)
    validation_errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    passed: bool = False
    error_message: Optional[str] = None
    template_version: Optional[str] = None
    total_pages: int = 0


class PDFScanner:
    def __init__(self, pdf_dir: Path):
        self.pdf_dir = pdf_dir

    def scan(self) -> list[Path]:
        if not self.pdf_dir.exists():
            return []
        pdf_files = sorted(self.pdf_dir.glob("*.pdf"))
        return pdf_files


class ResultValidator:
    CPF_PATTERN = re.compile(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$")
    YEAR_PATTERN = re.compile(r"^\d{4}$")

    def __init__(self, min_confidence: float):
        self.min_confidence = min_confidence

    def validate(self, result_dict: dict, confidence: Optional[float]) -> list[str]:
        errors = []

        if confidence is not None and confidence < self.min_confidence:
            errors.append(f"confidence_below_threshold: {confidence:.2f} < {self.min_confidence}")

        taxpayer = result_dict.get("taxpayer_identification", {})

        cpf = taxpayer.get("cpf")
        if not cpf:
            errors.append("missing_cpf")
        elif not self.CPF_PATTERN.match(cpf):
            errors.append(f"invalid_cpf_format: {cpf}")

        name = taxpayer.get("name")
        if not name or not name.strip():
            errors.append("missing_name")

        exercise_year = taxpayer.get("exercise_year")
        if not exercise_year:
            errors.append("missing_exercise_year")
        elif not self.YEAR_PATTERN.match(str(exercise_year)):
            errors.append(f"invalid_exercise_year_format: {exercise_year}")

        return errors


class LocalTestRunner:
    def __init__(self, config: BatchTestConfig):
        self.config = config
        self.parser = IRPFParser()
        self.validator = ResultValidator(config.min_confidence)
        self.pdf_detector = PdfTypeDetector()
        self.ocr_orchestrator = self._create_ocr_orchestrator()

    def _create_ocr_orchestrator(self) -> Optional[OcrOrchestrator]:
        engine = TesseractEngine(lang="por", timeout=120)
        if engine.is_available():
            return OcrOrchestrator(engines=[engine], min_confidence=0.5)
        return None

    def run_single(self, pdf_path: Path) -> TestResult:
        start_time = time.perf_counter()
        result = TestResult(
            filename=pdf_path.name,
            status="ERROR",
            processing_time=0.0,
        )

        try:
            detection = self.pdf_detector.detect_with_confidence(pdf_path)
            pdf_type = detection.pdf_type

            if requires_ocr(pdf_type):
                extraction_result = self._process_with_ocr(pdf_path, detection.total_pages)
                result.warnings.append(f"pdf_type={pdf_type.value}, processed_with_ocr=true")
            else:
                extraction_result = self.parser.parse(pdf_path)

            result_dict = extraction_result.to_dict()

            result.status = "READY"
            result.confidence = extraction_result.confidence
            result.template_version = self.parser.detected_version
            result.total_pages = extraction_result.total_pages
            result.warnings.extend(extraction_result.warnings)

            taxpayer_data = result_dict.get("taxpayer_identification", {})
            result.taxpayer = TaxpayerInfo(
                cpf=taxpayer_data.get("cpf"),
                name=taxpayer_data.get("name"),
                exercise_year=taxpayer_data.get("exercise_year"),
            )

            result.validation_errors = self.validator.validate(
                result_dict, result.confidence
            )
            result.passed = len(result.validation_errors) == 0

        except Exception as e:
            result.status = "ERROR"
            result.error_message = str(e)
            result.validation_errors.append(f"parse_error: {str(e)[:100]}")
            result.passed = False

        result.processing_time = time.perf_counter() - start_time
        return result

    def _process_with_ocr(self, pdf_path: Path, total_pages: int):
        if self.ocr_orchestrator is None:
            raise RuntimeError("OCR not available - tesseract not installed")

        ocr_result = self.ocr_orchestrator.process(pdf_path)
        return self.parser.parse_from_text(
            text=ocr_result.text,
            total_pages=total_pages,
        )

    def run_batch(self, pdf_files: list[Path]) -> list[TestResult]:
        results = []
        total = len(pdf_files)

        for i, pdf_path in enumerate(pdf_files, 1):
            log_msg(
                "processing",
                index=i,
                total=total,
                filename=pdf_path.name[:40],
            )
            result = self.run_single(pdf_path)
            status_icon = "OK" if result.passed else "FAIL"
            log_msg(
                "completed",
                index=i,
                status=status_icon,
                conf=f"{result.confidence:.2f}" if result.confidence else "-",
                time=f"{result.processing_time:.1f}s",
            )
            results.append(result)

        return results


class ReportGenerator:
    def generate_console_summary(self, results: list[TestResult], duration: float):
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        pass_rate = (passed / total * 100) if total > 0 else 0

        print(flush=True)
        print("=" * 80, flush=True)
        print("              IRPF BATCH TEST REPORT (LOCAL PARSER)", flush=True)
        print("=" * 80, flush=True)
        print(flush=True)
        print(f"Executed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        print(f"Total PDFs: {total}", flush=True)
        print(f"Duration: {duration:.1f}s", flush=True)
        print(f"Avg time per PDF: {duration/total:.1f}s" if total > 0 else "", flush=True)
        print(flush=True)
        print("RESULTS SUMMARY", flush=True)
        print("-" * 80, flush=True)
        print(f"  PASSED:  {passed} ({pass_rate:.1f}%)", flush=True)
        print(f"  FAILED:  {failed} ({100 - pass_rate:.1f}%)", flush=True)
        print(flush=True)
        print("DETAILED RESULTS", flush=True)
        print("-" * 80, flush=True)
        print(f" {'#':>3} | {'Filename':<35} | {'Status':<6} | {'Conf':<5} | {'Time':<6} | {'Ver':<4} | Result", flush=True)
        print("-" * 80, flush=True)

        for i, r in enumerate(results, 1):
            filename_display = r.filename[:32] + "..." if len(r.filename) > 35 else r.filename
            conf_display = f"{r.confidence:.2f}" if r.confidence else "-"
            time_display = f"{r.processing_time:.1f}s"
            ver_display = r.template_version or "-"
            result_display = "PASS" if r.passed else "FAIL"
            print(
                f" {i:>3} | {filename_display:<35} | {r.status:<6} | {conf_display:<5} | {time_display:<6} | {ver_display:<4} | {result_display}",
                flush=True
            )

            if not r.passed and r.validation_errors:
                for error in r.validation_errors[:2]:
                    error_display = error[:65] + "..." if len(error) > 68 else error
                    print(f"     | -> {error_display}", flush=True)

        failed_results = [r for r in results if not r.passed]
        if failed_results:
            print(flush=True)
            print("FAILED DOCUMENTS DETAILS", flush=True)
            print("-" * 80, flush=True)
            for r in failed_results:
                print(f"File: {r.filename}", flush=True)
                print(f"  Status: {r.status}", flush=True)
                if r.error_message:
                    print(f"  Error: {r.error_message[:100]}", flush=True)
                if r.validation_errors:
                    print(f"  Validation: {', '.join(r.validation_errors[:3])}", flush=True)
                print(flush=True)

        print("=" * 80, flush=True)

    def generate_json_report(
        self,
        results: list[TestResult],
        config: BatchTestConfig,
        duration: float,
        output_path: Path,
    ):
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        pass_rate = (passed / total * 100) if total > 0 else 0

        report = {
            "execution": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": round(duration, 2),
                "pdf_dir": str(config.pdf_dir),
                "min_confidence": config.min_confidence,
                "mode": "local_parser",
            },
            "summary": {
                "total": total,
                "passed": passed,
                "failed": total - passed,
                "pass_rate": round(pass_rate, 2),
            },
            "results": [self._serialize_result(r) for r in results],
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        log_msg("report_saved", path=str(output_path))

    def _serialize_result(self, result: TestResult) -> dict:
        return {
            "filename": result.filename,
            "status": result.status,
            "processing_time": round(result.processing_time, 2),
            "confidence": result.confidence,
            "template_version": result.template_version,
            "total_pages": result.total_pages,
            "taxpayer": asdict(result.taxpayer),
            "validation_errors": result.validation_errors,
            "warnings": result.warnings,
            "passed": result.passed,
            "error_message": result.error_message,
        }


def log_msg(event: str, **kwargs):
    timestamp = datetime.now().strftime("%H:%M:%S")
    parts = [f"[{timestamp}]", f"{event}:"]
    for key, value in kwargs.items():
        parts.append(f"{key}={value}")
    print(" ".join(parts), flush=True)


def parse_args() -> BatchTestConfig:
    parser = argparse.ArgumentParser(
        description="Local batch test - processes PDFs directly with IRPFParser"
    )
    parser.add_argument(
        "--pdf-dir",
        default="./pdfs",
        help="Directory containing PDF files (default: ./pdfs)",
    )
    parser.add_argument(
        "--output",
        default="./batch_results_local.json",
        help="Output JSON file path (default: ./batch_results_local.json)",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.7,
        help="Minimum confidence threshold (default: 0.7)",
    )

    args = parser.parse_args()

    return BatchTestConfig(
        pdf_dir=Path(args.pdf_dir),
        output=Path(args.output),
        min_confidence=args.min_confidence,
    )


def run_batch_test(config: BatchTestConfig) -> int:
    print("=" * 60, flush=True)
    print("  IRPF Local Parser Batch Test", flush=True)
    print("=" * 60, flush=True)
    log_msg("started", pdf_dir=str(config.pdf_dir))

    scanner = PDFScanner(config.pdf_dir)
    pdf_files = scanner.scan()

    if not pdf_files:
        log_msg("error", msg="no_pdf_files_found")
        return 1

    log_msg("found", count=len(pdf_files))
    print(flush=True)

    runner = LocalTestRunner(config)
    report_generator = ReportGenerator()

    start_time = time.perf_counter()
    results = runner.run_batch(pdf_files)
    duration = time.perf_counter() - start_time

    report_generator.generate_console_summary(results, duration)
    report_generator.generate_json_report(results, config, duration, config.output)

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    log_msg(
        "finished",
        total=total,
        passed=passed,
        failed=total - passed,
        duration=f"{duration:.1f}s",
    )

    return 0 if passed == total else 1


def main():
    config = parse_args()
    exit_code = run_batch_test(config)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

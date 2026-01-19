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

import httpx


@dataclass
class BatchTestConfig:
    api_url: str = "http://localhost:8000"
    tenant_id: str = "batch-test"
    pdf_dir: Path = field(default_factory=lambda: Path("./pdfs"))
    output: Path = field(default_factory=lambda: Path("./batch_results.json"))
    timeout: int = 300
    min_confidence: float = 0.7
    concurrency: int = 5
    poll_interval: int = 2


@dataclass
class TaxpayerInfo:
    cpf: Optional[str] = None
    name: Optional[str] = None
    exercise_year: Optional[str] = None


@dataclass
class TestResult:
    filename: str
    document_id: str
    status: str
    processing_time: float
    confidence: Optional[float] = None
    taxpayer: TaxpayerInfo = field(default_factory=TaxpayerInfo)
    validation_errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    passed: bool = False
    error_message: Optional[str] = None


class PDFScanner:
    def __init__(self, pdf_dir: Path):
        self.pdf_dir = pdf_dir

    def scan(self) -> list[Path]:
        if not self.pdf_dir.exists():
            return []
        pdf_files = sorted(self.pdf_dir.glob("*.pdf"))
        return pdf_files


class APIClient:
    def __init__(self, config: BatchTestConfig):
        self.config = config

    def _get_client(self) -> httpx.Client:
        return httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0))

    def upload(self, pdf_path: Path) -> dict:
        url = f"{self.config.api_url}/v1/documents"
        headers = {"X-Tenant-ID": self.config.tenant_id}

        with self._get_client() as client:
            with open(pdf_path, "rb") as f:
                files = {"file": (pdf_path.name, f, "application/pdf")}
                response = client.post(url, headers=headers, files=files)

            response.raise_for_status()
            return response.json()

    def get_status(self, document_id: str) -> dict:
        url = f"{self.config.api_url}/v1/documents/{document_id}/status"
        headers = {"X-Tenant-ID": self.config.tenant_id}

        with self._get_client() as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

    def get_result(self, document_id: str) -> dict:
        url = f"{self.config.api_url}/v1/documents/{document_id}"
        headers = {"X-Tenant-ID": self.config.tenant_id}

        with self._get_client() as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()


class ResultValidator:
    CPF_PATTERN = re.compile(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$")
    YEAR_PATTERN = re.compile(r"^\d{4}$")

    def __init__(self, min_confidence: float):
        self.min_confidence = min_confidence

    def validate(self, result: dict, confidence: Optional[float]) -> list[str]:
        errors = []

        if confidence is not None and confidence < self.min_confidence:
            errors.append(f"confidence_below_threshold: {confidence} < {self.min_confidence}")

        data = result.get("data", {})
        taxpayer = data.get("taxpayer_identification", {})

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


class TestRunner:
    TERMINAL_STATUSES = {"ready", "error", "failed"}

    def __init__(self, config: BatchTestConfig):
        self.config = config
        self.api_client = APIClient(config)
        self.validator = ResultValidator(config.min_confidence)

    def run_single(self, pdf_path: Path) -> TestResult:
        start_time = time.perf_counter()
        result = TestResult(
            filename=pdf_path.name,
            document_id="",
            status="ERROR",
            processing_time=0.0,
        )

        try:
            upload_response = self.api_client.upload(pdf_path)
            result.document_id = upload_response.get("document_id", "")
            log_msg(
                "document_uploaded",
                filename=pdf_path.name,
                document_id=result.document_id,
            )

            final_status = self._poll_until_complete(result.document_id)
            result.status = final_status.get("status", "UNKNOWN").upper()
            result.confidence = final_status.get("confidence")
            result.error_message = final_status.get("error_message")

            if result.status == "READY":
                extraction_result = self.api_client.get_result(result.document_id)
                data = extraction_result.get("data", {})
                taxpayer_data = data.get("taxpayer_identification", {})

                result.taxpayer = TaxpayerInfo(
                    cpf=taxpayer_data.get("cpf"),
                    name=taxpayer_data.get("name"),
                    exercise_year=taxpayer_data.get("exercise_year"),
                )
                result.warnings = extraction_result.get("warnings", [])
                result.validation_errors = self.validator.validate(
                    extraction_result, result.confidence
                )
                result.passed = len(result.validation_errors) == 0
            else:
                result.validation_errors.append(f"status_not_ready: {result.status}")
                if result.error_message:
                    result.validation_errors.append(f"api_error: {result.error_message}")
                result.passed = False

        except httpx.HTTPStatusError as e:
            result.status = "HTTP_ERROR"
            result.error_message = f"HTTP {e.response.status_code}: {e.response.text}"
            result.validation_errors.append(f"http_error: {result.error_message}")
            log_msg(
                "http_error",
                filename=pdf_path.name,
                status_code=e.response.status_code,
                error=e.response.text,
            )

        except httpx.RequestError as e:
            result.status = "CONNECTION_ERROR"
            result.error_message = str(e)
            result.validation_errors.append(f"connection_error: {result.error_message}")
            log_msg("connection_error", filename=pdf_path.name, error=str(e))

        except TimeoutError:
            result.status = "TIMEOUT"
            result.error_message = f"Timeout after {self.config.timeout}s"
            result.validation_errors.append(f"timeout: {self.config.timeout}s")
            log_msg("timeout", filename=pdf_path.name, timeout=self.config.timeout)

        except Exception as e:
            result.status = "ERROR"
            result.error_message = str(e)
            result.validation_errors.append(f"unexpected_error: {result.error_message}")
            log_msg("unexpected_error", filename=pdf_path.name, error=str(e))

        result.processing_time = time.perf_counter() - start_time
        return result

    def _poll_until_complete(self, document_id: str) -> dict:
        start_time = time.perf_counter()

        while True:
            elapsed = time.perf_counter() - start_time
            if elapsed > self.config.timeout:
                raise TimeoutError(f"Timeout after {self.config.timeout}s")

            status_data = self.api_client.get_status(document_id)
            current_status = status_data.get("status", "unknown").lower()

            log_msg(
                "polling_status",
                document_id=document_id[:8],
                status=current_status,
                elapsed=f"{elapsed:.0f}s",
            )

            if current_status in self.TERMINAL_STATUSES:
                return status_data

            time.sleep(self.config.poll_interval)

    def run_batch(self, pdf_files: list[Path]) -> list[TestResult]:
        results = []
        total = len(pdf_files)

        for i, pdf_path in enumerate(pdf_files, 1):
            log_msg(
                "processing_started",
                index=i,
                total=total,
                filename=pdf_path.name,
            )
            result = self.run_single(pdf_path)
            log_msg(
                "processing_completed",
                index=i,
                filename=pdf_path.name,
                status=result.status,
                passed=result.passed,
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

        print()
        print("=" * 80)
        print("                     IRPF BATCH TEST REPORT")
        print("=" * 80)
        print()
        print(f"Executed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total PDFs: {total}")
        print(f"Duration: {duration:.1f}s")
        print()
        print("RESULTS SUMMARY")
        print("-" * 80)
        print(f"  PASSED:  {passed} ({pass_rate:.1f}%)")
        print(f"  FAILED:  {failed} ({100 - pass_rate:.1f}%)")
        print()
        print("DETAILED RESULTS")
        print("-" * 80)
        print(f" {'#':>3} | {'Filename':<40} | {'Status':<8} | {'Conf':<6} | {'Time':<7} | Result")
        print("-" * 80)

        for i, r in enumerate(results, 1):
            filename_display = r.filename[:37] + "..." if len(r.filename) > 40 else r.filename
            conf_display = f"{r.confidence:.2f}" if r.confidence else "-"
            time_display = f"{r.processing_time:.1f}s"
            result_display = "PASS" if r.passed else "FAIL"
            print(
                f" {i:>3} | {filename_display:<40} | {r.status:<8} | {conf_display:<6} | {time_display:<7} | {result_display}"
            )

            if not r.passed and r.validation_errors:
                for error in r.validation_errors[:2]:
                    error_display = error[:70] + "..." if len(error) > 73 else error
                    print(f"     | -> {error_display}")

        failed_results = [r for r in results if not r.passed]
        if failed_results:
            print()
            print("FAILED DOCUMENTS")
            print("-" * 80)
            for r in failed_results:
                print(f"Filename: {r.filename}")
                print(f"Document ID: {r.document_id}")
                print(f"Status: {r.status}")
                if r.error_message:
                    print(f"Error: {r.error_message}")
                if r.validation_errors:
                    print("Validation Errors:")
                    for error in r.validation_errors:
                        print(f"  - {error}")
                print()

        print("=" * 80)

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
                "api_url": config.api_url,
                "tenant_id": config.tenant_id,
                "pdf_dir": str(config.pdf_dir),
                "min_confidence": config.min_confidence,
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
            "document_id": result.document_id,
            "status": result.status,
            "processing_time": round(result.processing_time, 2),
            "confidence": result.confidence,
            "taxpayer": asdict(result.taxpayer),
            "validation_errors": result.validation_errors,
            "warnings": result.warnings,
            "passed": result.passed,
            "error_message": result.error_message,
        }


def log_msg(event: str, **kwargs):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    parts = [f"ts={timestamp}", f"event={event}"]
    for key, value in kwargs.items():
        parts.append(f"{key}={value}")
    print(" ".join(parts), flush=True)


def parse_args() -> BatchTestConfig:
    parser = argparse.ArgumentParser(
        description="Batch test script for IRPF Processor API"
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--tenant-id",
        default="batch-test",
        help="Tenant ID (default: batch-test)",
    )
    parser.add_argument(
        "--pdf-dir",
        default="./pdfs",
        help="Directory containing PDF files (default: ./pdfs)",
    )
    parser.add_argument(
        "--output",
        default="./batch_results.json",
        help="Output JSON file path (default: ./batch_results.json)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Timeout per document in seconds (default: 300)",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.7,
        help="Minimum confidence threshold (default: 0.7)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Number of concurrent uploads (default: 5)",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=2,
        help="Status polling interval in seconds (default: 2)",
    )

    args = parser.parse_args()

    return BatchTestConfig(
        api_url=args.api_url,
        tenant_id=args.tenant_id,
        pdf_dir=Path(args.pdf_dir),
        output=Path(args.output),
        timeout=args.timeout,
        min_confidence=args.min_confidence,
        concurrency=args.concurrency,
        poll_interval=args.poll_interval,
    )


def run_batch_test(config: BatchTestConfig) -> int:
    log_msg(
        "batch_test_started",
        api_url=config.api_url,
        tenant_id=config.tenant_id,
        pdf_dir=str(config.pdf_dir),
    )

    scanner = PDFScanner(config.pdf_dir)
    pdf_files = scanner.scan()

    if not pdf_files:
        log_msg("no_pdf_files_found", pdf_dir=str(config.pdf_dir))
        return 1

    log_msg("pdf_files_found", count=len(pdf_files))

    runner = TestRunner(config)
    report_generator = ReportGenerator()

    start_time = time.perf_counter()
    results = runner.run_batch(pdf_files)
    duration = time.perf_counter() - start_time

    report_generator.generate_console_summary(results, duration)
    report_generator.generate_json_report(results, config, duration, config.output)

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    log_msg(
        "batch_test_completed",
        total=total,
        passed=passed,
        failed=total - passed,
        duration=f"{duration:.1f}s",
    )

    return 0 if passed == total else 1


def main():
    print("Starting batch_test.py...", flush=True)
    config = parse_args()
    print(f"Config loaded: api_url={config.api_url}, pdf_dir={config.pdf_dir}", flush=True)
    exit_code = run_batch_test(config)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

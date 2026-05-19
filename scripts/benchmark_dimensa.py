#!/usr/bin/env python3

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from irpf_processor.infrastructure.extraction import IRPFParser
from irpf_processor.infrastructure.extraction.ocr.pdf_type_detector import PdfTypeDetector
from irpf_processor.infrastructure.extraction.ocr.models import PdfType
from irpf_processor.infrastructure.extraction.ocr.ocr_orchestrator import OcrOrchestrator
from irpf_processor.infrastructure.extraction.ocr.tesseract_engine import TesseractEngine


def requires_ocr(pdf_type: PdfType) -> bool:
    return pdf_type in (PdfType.IMAGE, PdfType.MIXED)


@dataclass
class BenchmarkConfig:
    gabarito_dir: Path = field(default_factory=lambda: Path("./compare/AMOSTR1"))
    pdf_dir: Optional[Path] = None
    output_dir: Path = field(default_factory=lambda: Path("./compare/benchmark_results"))


@dataclass
class FieldComparison:
    path: str
    expected: Any
    actual: Any
    match: bool
    diff_type: str


@dataclass
class SectionComparison:
    name: str
    expected_fields: int
    matched_fields: int
    missing_fields: list[str]
    extra_fields: list[str]
    divergent_fields: list[FieldComparison]
    accuracy: float


@dataclass
class BenchmarkResult:
    filename: str
    gabarito_file: str
    processing_time: float
    total_expected_sections: int
    total_matched_sections: int
    sections: list[SectionComparison]
    overall_accuracy: float
    error_message: Optional[str] = None


class JsonComparator:
    IGNORED_FIELDS = {
        "id", "_id", "uuid", "pk", "page", "created_at", "updated_at",
        "extraction_metrics", "raw_text", "canonical_block", "canonical_block_code",
        "canonical_session", "canonical_session_code", "canonical_subsession",
        "canonical_subsession_code", "canonical_priority", "canonical_description"
    }

    def compare(self, expected: dict, actual: dict) -> list[SectionComparison]:
        sections = []

        expected_decl = self._extract_declaration(expected)
        actual_decl = self._extract_declaration(actual)

        if not expected_decl or not actual_decl:
            return sections

        all_sections = set(expected_decl.keys()) | set(actual_decl.keys())

        for section_key in all_sections:
            if section_key in self.IGNORED_FIELDS:
                continue
            if section_key.startswith("_"):
                continue

            exp_section = expected_decl.get(section_key)
            act_section = actual_decl.get(section_key)

            section_result = self._compare_section(section_key, exp_section, act_section)
            if section_result:
                sections.append(section_result)

        return sections

    def _extract_declaration(self, obj: dict) -> Optional[dict]:
        paths = [
            ["data", "ir_response", "declaration"],
            ["raw", "ir_response", "declaration"],
            ["ir_response", "declaration"],
            ["declaration"]
        ]

        for path in paths:
            temp = obj
            found = True
            for key in path:
                if isinstance(temp, dict) and key in temp:
                    temp = temp[key]
                else:
                    found = False
                    break
            if found:
                return temp

        return obj if isinstance(obj, dict) else None

    def _compare_section(
        self,
        section_key: str,
        expected: Any,
        actual: Any
    ) -> Optional[SectionComparison]:
        if expected is None and actual is None:
            return None

        if expected is None:
            return SectionComparison(
                name=section_key,
                expected_fields=0,
                matched_fields=0,
                missing_fields=[],
                extra_fields=["entire_section"],
                divergent_fields=[],
                accuracy=0.0
            )

        if actual is None:
            return SectionComparison(
                name=section_key,
                expected_fields=self._count_fields(expected),
                matched_fields=0,
                missing_fields=["entire_section"],
                extra_fields=[],
                divergent_fields=[],
                accuracy=0.0
            )

        missing = []
        extra = []
        divergent = []
        matched = 0
        total = 0

        self._compare_recursive(
            expected, actual, section_key, missing, extra, divergent
        )

        total = self._count_fields(expected)
        matched = total - len(missing) - len(divergent)

        accuracy = (matched / total * 100) if total > 0 else 100.0

        return SectionComparison(
            name=section_key,
            expected_fields=total,
            matched_fields=matched,
            missing_fields=missing,
            extra_fields=extra,
            divergent_fields=divergent,
            accuracy=round(accuracy, 2)
        )

    def _compare_recursive(
        self,
        expected: Any,
        actual: Any,
        path: str,
        missing: list,
        extra: list,
        divergent: list
    ):
        if isinstance(expected, dict) and isinstance(actual, dict):
            all_keys = set(expected.keys()) | set(actual.keys())

            for key in all_keys:
                if key in self.IGNORED_FIELDS or key.startswith("_"):
                    continue

                new_path = f"{path}.{key}"

                if key not in actual:
                    missing.append(new_path)
                elif key not in expected:
                    if actual[key] not in (None, "N/A", False, {}, []):
                        extra.append(new_path)
                else:
                    self._compare_recursive(
                        expected[key], actual[key], new_path,
                        missing, extra, divergent
                    )

        elif isinstance(expected, list) and isinstance(actual, list):
            if len(expected) != len(actual):
                divergent.append(FieldComparison(
                    path=path,
                    expected=f"list[{len(expected)}]",
                    actual=f"list[{len(actual)}]",
                    match=False,
                    diff_type="list_length"
                ))

            min_len = min(len(expected), len(actual))
            for i in range(min_len):
                self._compare_recursive(
                    expected[i], actual[i], f"{path}[{i}]",
                    missing, extra, divergent
                )

        else:
            if not self._values_equal(expected, actual):
                divergent.append(FieldComparison(
                    path=path,
                    expected=expected,
                    actual=actual,
                    match=False,
                    diff_type="value_mismatch"
                ))

    def _values_equal(self, val1: Any, val2: Any) -> bool:
        if val1 is None and val2 == "N/A":
            return True
        if val2 is None and val1 == "N/A":
            return True
        if val1 is None and val2 == {}:
            return True
        if val2 is None and val1 == {}:
            return True
        if val1 == "N/A" and val2 == {}:
            return True
        if val2 == "N/A" and val1 == {}:
            return True
        if val1 == "N/A" and val2 is False:
            return True
        if val2 == "N/A" and val1 is False:
            return True

        if isinstance(val1, str) and isinstance(val2, str):
            return self._normalize_string(val1) == self._normalize_string(val2)

        if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
            return abs(float(val1) - float(val2)) < 0.01

        return val1 == val2

    def _normalize_string(self, s: str) -> str:
        import re
        s = re.sub(r"\s*;\s*", "; ", s)
        s = re.sub(r"\s+([,.:%)!\]])", r"\1", s)
        s = re.sub(r"([\[(])\s+", r"\1", s)
        s = re.sub(r"\s*/\s*", "/", s)
        s = re.sub(r"\s*-\s*", "-", s)
        s = re.sub(r"R\s*\$", "R$", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s.lower()

    def _count_fields(self, obj: Any, count: int = 0) -> int:
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key not in self.IGNORED_FIELDS and not key.startswith("_"):
                    if isinstance(value, (dict, list)):
                        count = self._count_fields(value, count)
                    else:
                        count += 1
        elif isinstance(obj, list):
            for item in obj:
                count = self._count_fields(item, count)
        else:
            count += 1
        return count


class BenchmarkRunner:
    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.parser = IRPFParser()
        self.comparator = JsonComparator()
        self.pdf_detector = PdfTypeDetector()
        self.ocr_orchestrator = self._create_ocr_orchestrator()

    def _create_ocr_orchestrator(self) -> Optional[OcrOrchestrator]:
        engine = TesseractEngine(lang="por", timeout=120)
        if engine.is_available():
            return OcrOrchestrator(engines=[engine], min_confidence=0.5)
        return None

    def find_gabarito_files(self) -> list[Path]:
        if not self.config.gabarito_dir.exists():
            return []
        return sorted(self.config.gabarito_dir.glob("*_GABARITO.json"))

    def find_pdf_for_gabarito(self, gabarito_path: Path) -> Optional[Path]:
        if not self.config.pdf_dir:
            return None

        base_name = gabarito_path.stem.replace("_GABARITO", "")
        pdf_path = self.config.pdf_dir / f"{base_name}.pdf"

        if pdf_path.exists():
            return pdf_path

        for pdf in self.config.pdf_dir.glob("*.pdf"):
            if base_name.lower() in pdf.stem.lower():
                return pdf

        return None

    def process_pdf(self, pdf_path: Path) -> dict:
        detection = self.pdf_detector.detect_with_confidence(pdf_path)
        pdf_type = detection.pdf_type

        if requires_ocr(pdf_type):
            if self.ocr_orchestrator is None:
                raise RuntimeError("OCR not available - tesseract not installed")
            ocr_result = self.ocr_orchestrator.process(pdf_path)
            extraction_result = self.parser.parse_from_text(
                text=ocr_result.text,
                total_pages=detection.total_pages,
            )
        else:
            extraction_result = self.parser.parse(pdf_path)

        result_dict = extraction_result.to_dict()
        return {"data": {"ir_response": {"declaration": result_dict}}}

    def run_single(self, gabarito_path: Path, pdf_path: Optional[Path] = None) -> BenchmarkResult:
        start_time = time.perf_counter()

        try:
            with open(gabarito_path, "r", encoding="utf-8") as f:
                gabarito_data = json.load(f)

            if pdf_path:
                actual_data = self.process_pdf(pdf_path)
            else:
                actual_data = {"data": {"ir_response": {"declaration": {}}}}

            sections = self.comparator.compare(gabarito_data, actual_data)

            total_expected = len([s for s in sections if s.expected_fields > 0])
            total_matched = len([s for s in sections if s.accuracy == 100.0])

            total_fields = sum(s.expected_fields for s in sections)
            matched_fields = sum(s.matched_fields for s in sections)
            overall_accuracy = (matched_fields / total_fields * 100) if total_fields > 0 else 0.0

            processing_time = time.perf_counter() - start_time

            return BenchmarkResult(
                filename=pdf_path.name if pdf_path else "N/A",
                gabarito_file=gabarito_path.name,
                processing_time=round(processing_time, 2),
                total_expected_sections=total_expected,
                total_matched_sections=total_matched,
                sections=sections,
                overall_accuracy=round(overall_accuracy, 2)
            )

        except Exception as e:
            return BenchmarkResult(
                filename=pdf_path.name if pdf_path else "N/A",
                gabarito_file=gabarito_path.name,
                processing_time=time.perf_counter() - start_time,
                total_expected_sections=0,
                total_matched_sections=0,
                sections=[],
                overall_accuracy=0.0,
                error_message=str(e)
            )

    def run_batch(self) -> list[BenchmarkResult]:
        results = []
        gabarito_files = self.find_gabarito_files()

        if not gabarito_files:
            log_msg("error", msg="no_gabarito_files_found")
            return results

        log_msg("found", count=len(gabarito_files))

        for i, gabarito_path in enumerate(gabarito_files, 1):
            log_msg(
                "processing",
                index=i,
                total=len(gabarito_files),
                filename=gabarito_path.name[:40]
            )

            pdf_path = self.find_pdf_for_gabarito(gabarito_path) if self.config.pdf_dir else None

            result = self.run_single(gabarito_path, pdf_path)
            results.append(result)

            status_icon = "OK" if result.overall_accuracy >= 90 else "WARN" if result.overall_accuracy >= 70 else "LOW"
            log_msg(
                "completed",
                index=i,
                status=status_icon,
                accuracy=f"{result.overall_accuracy:.1f}%",
                time=f"{result.processing_time:.1f}s"
            )

        return results


class ReportGenerator:
    def generate_console_summary(self, results: list[BenchmarkResult], duration: float):
        total = len(results)
        avg_accuracy = sum(r.overall_accuracy for r in results) / total if total > 0 else 0

        print(flush=True)
        print("=" * 80, flush=True)
        print("              DIMENSA PARITY BENCHMARK REPORT", flush=True)
        print("=" * 80, flush=True)
        print(flush=True)
        print(f"Executed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        print(f"Total Gabaritos: {total}", flush=True)
        print(f"Duration: {duration:.1f}s", flush=True)
        print(f"Average Accuracy: {avg_accuracy:.1f}%", flush=True)
        print(flush=True)

        print("ACCURACY BY DOCUMENT", flush=True)
        print("-" * 80, flush=True)
        print(f" {'#':>3} | {'Gabarito':<40} | {'Accuracy':>8} | {'Sections':>10}", flush=True)
        print("-" * 80, flush=True)

        for i, r in enumerate(results, 1):
            filename = r.gabarito_file[:37] + "..." if len(r.gabarito_file) > 40 else r.gabarito_file
            sections_str = f"{r.total_matched_sections}/{r.total_expected_sections}"
            print(f" {i:>3} | {filename:<40} | {r.overall_accuracy:>7.1f}% | {sections_str:>10}", flush=True)

        print(flush=True)
        print("SECTION ANALYSIS (AGGREGATE)", flush=True)
        print("-" * 80, flush=True)

        section_stats = {}
        for r in results:
            for s in r.sections:
                if s.name not in section_stats:
                    section_stats[s.name] = {"total": 0, "accuracy_sum": 0, "count": 0}
                section_stats[s.name]["total"] += s.expected_fields
                section_stats[s.name]["accuracy_sum"] += s.accuracy
                section_stats[s.name]["count"] += 1

        for name, stats in sorted(section_stats.items()):
            avg_acc = stats["accuracy_sum"] / stats["count"] if stats["count"] > 0 else 0
            status = "OK" if avg_acc >= 90 else "WARN" if avg_acc >= 70 else "LOW"
            print(f" [{status:>4}] {name:<50} {avg_acc:>6.1f}%", flush=True)

        print("=" * 80, flush=True)

    def generate_json_report(
        self,
        results: list[BenchmarkResult],
        config: BenchmarkConfig,
        duration: float,
        output_path: Path
    ):
        total = len(results)
        avg_accuracy = sum(r.overall_accuracy for r in results) / total if total > 0 else 0

        report = {
            "execution": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": round(duration, 2),
                "gabarito_dir": str(config.gabarito_dir),
                "pdf_dir": str(config.pdf_dir) if config.pdf_dir else None,
            },
            "summary": {
                "total_gabaritos": total,
                "average_accuracy": round(avg_accuracy, 2),
                "high_accuracy_count": len([r for r in results if r.overall_accuracy >= 90]),
                "medium_accuracy_count": len([r for r in results if 70 <= r.overall_accuracy < 90]),
                "low_accuracy_count": len([r for r in results if r.overall_accuracy < 70]),
            },
            "results": [self._serialize_result(r) for r in results],
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        log_msg("report_saved", path=str(output_path))

    def _serialize_result(self, result: BenchmarkResult) -> dict:
        return {
            "filename": result.filename,
            "gabarito_file": result.gabarito_file,
            "processing_time": result.processing_time,
            "total_expected_sections": result.total_expected_sections,
            "total_matched_sections": result.total_matched_sections,
            "overall_accuracy": result.overall_accuracy,
            "error_message": result.error_message,
            "sections": [
                {
                    "name": s.name,
                    "expected_fields": s.expected_fields,
                    "matched_fields": s.matched_fields,
                    "accuracy": s.accuracy,
                    "missing_fields": s.missing_fields[:10],
                    "extra_fields": s.extra_fields[:10],
                    "divergent_count": len(s.divergent_fields),
                }
                for s in result.sections
            ],
        }


def log_msg(event: str, **kwargs):
    timestamp = datetime.now().strftime("%H:%M:%S")
    parts = [f"[{timestamp}]", f"{event}:"]
    for key, value in kwargs.items():
        parts.append(f"{key}={value}")
    print(" ".join(parts), flush=True)


def parse_args() -> BenchmarkConfig:
    parser = argparse.ArgumentParser(
        description="Benchmark IRPF extraction against Dimensa gabaritos"
    )
    parser.add_argument(
        "--gabarito-dir",
        default="./compare/AMOSTR1",
        help="Directory containing GABARITO JSON files (default: ./compare/AMOSTR1)",
    )
    parser.add_argument(
        "--pdf-dir",
        default=None,
        help="Directory containing PDF files to process (optional)",
    )
    parser.add_argument(
        "--output-dir",
        default="./compare/benchmark_results",
        help="Output directory for reports (default: ./compare/benchmark_results)",
    )

    args = parser.parse_args()

    return BenchmarkConfig(
        gabarito_dir=Path(args.gabarito_dir),
        pdf_dir=Path(args.pdf_dir) if args.pdf_dir else None,
        output_dir=Path(args.output_dir),
    )


def run_benchmark(config: BenchmarkConfig) -> int:
    print("=" * 60, flush=True)
    print("  IRPF Dimensa Parity Benchmark", flush=True)
    print("=" * 60, flush=True)
    log_msg("started", gabarito_dir=str(config.gabarito_dir))

    runner = BenchmarkRunner(config)
    report_generator = ReportGenerator()

    start_time = time.perf_counter()
    results = runner.run_batch()
    duration = time.perf_counter() - start_time

    if not results:
        log_msg("error", msg="no_results")
        return 1

    report_generator.generate_console_summary(results, duration)

    output_path = config.output_dir / f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_generator.generate_json_report(results, config, duration, output_path)

    avg_accuracy = sum(r.overall_accuracy for r in results) / len(results)
    log_msg(
        "finished",
        total=len(results),
        avg_accuracy=f"{avg_accuracy:.1f}%",
        duration=f"{duration:.1f}s"
    )

    return 0 if avg_accuracy >= 80 else 1


def main():
    config = parse_args()
    exit_code = run_benchmark(config)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

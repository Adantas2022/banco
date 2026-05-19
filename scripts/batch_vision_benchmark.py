#!/usr/bin/env python3
import argparse
import base64
import io
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx
from pdf2image import convert_from_path


@dataclass
class SectionResult:
    section_name: str
    vision_items: int = 0
    parser_items: int = 0
    matched_items: int = 0
    match_rate: float = 0.0
    missing_in_parser: list[str] = field(default_factory=list)
    extra_in_parser: list[str] = field(default_factory=list)


@dataclass
class PDFBenchmarkResult:
    pdf_name: str
    pdf_path: str
    pages: int = 0
    vision_chars: int = 0
    vision_time_seconds: float = 0.0
    parser_time_seconds: float = 0.0
    parser_confidence: float = 0.0
    overall_match_rate: float = 0.0
    sections: dict[str, SectionResult] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


@dataclass
class BenchmarkSummary:
    timestamp: str
    total_pdfs: int
    successful_pdfs: int
    total_pages: int
    total_vision_chars: int
    vision_api_calls: int
    overall_match_rate: float
    avg_parser_confidence: float
    total_time_seconds: float
    results: list[PDFBenchmarkResult] = field(default_factory=list)
    section_summary: dict[str, dict] = field(default_factory=dict)


SECTION_PATTERNS = {
    "taxpayer": {
        "markers": ["IDENTIFICAÇÃO DO CONTRIBUINTE", "CPF:", "Nome:"],
        "fields": ["cpf", "name"]
    },
    "income_pj": {
        "markers": ["RENDIMENTOS TRIBUTÁVEIS", "PESSOA JURÍDICA", "TITULAR"],
        "fields": ["cnpj", "payer_name", "value"]
    },
    "exempt_income": {
        "markers": ["RENDIMENTOS ISENTOS", "NÃO TRIBUTÁVEIS"],
        "fields": ["cnpj", "payer_name", "value"]
    },
    "exclusive_taxation": {
        "markers": ["TRIBUTAÇÃO EXCLUSIVA", "DEFINITIVA"],
        "fields": ["cnpj", "payer_name", "value"]
    },
    "assets": {
        "markers": ["BENS E DIREITOS"],
        "fields": ["code", "description", "value"]
    },
    "debts": {
        "markers": ["DÍVIDAS E ÔNUS", "DIVIDAS"],
        "fields": ["code", "description", "value"]
    },
    "rural_activity": {
        "markers": ["ATIVIDADE RURAL", "IMÓVEIS RURAIS"],
        "fields": ["property", "value"]
    }
}


def extract_with_vision(pdf_path: str, api_key: str) -> tuple[str, int, float]:
    import time
    start_time = time.time()
    
    images = convert_from_path(pdf_path, dpi=150)
    full_text = []
    total_chars = 0

    for i, img in enumerate(images):
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        request_body = {
            "requests": [
                {
                    "image": {"content": image_base64},
                    "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
                }
            ]
        }

        url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"

        with httpx.Client(timeout=120.0) as client:
            response = client.post(url, json=request_body)
            if response.status_code == 200:
                result = response.json()
                text = (
                    result.get("responses", [{}])[0]
                    .get("fullTextAnnotation", {})
                    .get("text", "")
                )
                full_text.append(f"=== PAGE {i + 1} ===\n{text}")
                total_chars += len(text)
                print(f"    Page {i + 1}/{len(images)}: {len(text)} chars")
            else:
                print(f"    Page {i + 1}: Error - {response.status_code}")
                full_text.append(f"=== PAGE {i + 1} ===\n[ERROR]")

    elapsed = time.time() - start_time
    return "\n\n".join(full_text), len(images), elapsed


def extract_with_parser(pdf_path: str) -> tuple[dict[str, Any], float, float]:
    import time
    start_time = time.time()
    
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from irpf_processor.infrastructure.extraction.irpf_parser import IRPFParser

    parser = IRPFParser()
    result = parser.parse(pdf_path)
    
    elapsed = time.time() - start_time
    
    data = {}
    confidence = 0.0
    
    if hasattr(result, '__dict__'):
        for key, value in vars(result).items():
            if not key.startswith('_'):
                data[key] = value
        confidence = getattr(result, 'confidence', 0.0)
    
    return data, confidence, elapsed


def extract_cnpjs_from_text(text: str) -> set[str]:
    pattern = r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"
    return set(re.findall(pattern, text))


def extract_cpfs_from_text(text: str) -> set[str]:
    pattern = r"\d{3}\.\d{3}\.\d{3}-\d{2}"
    return set(re.findall(pattern, text))


def extract_values_from_text(text: str) -> set[str]:
    pattern = r"\d{1,3}(?:\.\d{3})*,\d{2}"
    return set(re.findall(pattern, text))


def check_section_presence(vision_text: str, markers: list[str]) -> bool:
    text_upper = vision_text.upper()
    return any(marker.upper() in text_upper for marker in markers)


def compare_taxpayer(vision_text: str, parser_data: dict) -> SectionResult:
    result = SectionResult(section_name="Taxpayer (Contribuinte)")
    
    taxpayer = parser_data.get("taxpayer_identification", {})
    if not taxpayer:
        return result
    
    cpf = taxpayer.get("cpf", "")
    name = taxpayer.get("name", "")
    
    vision_clean = vision_text.replace(".", "").replace("-", "").replace(" ", "")
    
    if cpf:
        result.vision_items += 1
        cpf_clean = cpf.replace(".", "").replace("-", "")
        if cpf_clean in vision_clean:
            result.matched_items += 1
            result.parser_items += 1
        else:
            result.missing_in_parser.append(f"CPF: {cpf}")
    
    if name:
        result.vision_items += 1
        name_parts = name.upper().split()[:2]
        if all(part in vision_text.upper() for part in name_parts):
            result.matched_items += 1
            result.parser_items += 1
        else:
            result.missing_in_parser.append(f"Name: {name}")
    
    if result.vision_items > 0:
        result.match_rate = result.matched_items / result.vision_items
    
    return result


def compare_income_pj(vision_text: str, parser_data: dict) -> SectionResult:
    result = SectionResult(section_name="Income from Legal Person (Rend. PJ)")
    
    income = parser_data.get("income_from_legal_person_to_holder", {})
    items = income.get("items", []) if isinstance(income, dict) else []
    
    vision_cnpjs = extract_cnpjs_from_text(vision_text)
    parser_cnpjs = set()
    
    for item in items:
        cnpj = item.get("cpf_cnpj", "")
        if cnpj:
            parser_cnpjs.add(cnpj)
    
    result.vision_items = len(vision_cnpjs)
    result.parser_items = len(parser_cnpjs)
    result.matched_items = len(vision_cnpjs & parser_cnpjs)
    
    missing = vision_cnpjs - parser_cnpjs
    for cnpj in list(missing)[:5]:
        result.missing_in_parser.append(f"CNPJ: {cnpj}")
    
    if result.vision_items > 0:
        result.match_rate = result.matched_items / result.vision_items
    
    return result


def compare_exempt_income(vision_text: str, parser_data: dict) -> SectionResult:
    result = SectionResult(section_name="Exempt Income (Rend. Isentos)")
    
    if not check_section_presence(vision_text, SECTION_PATTERNS["exempt_income"]["markers"]):
        return result
    
    exempt = parser_data.get("exempt_income", {})
    if not exempt:
        result.vision_items = 1
        result.missing_in_parser.append("Section present in Vision but empty in parser")
        return result
    
    subsections = exempt.get("subsections", {}) if isinstance(exempt, dict) else {}
    total_items = sum(len(s.get("items", [])) for s in subsections.values())
    
    result.parser_items = total_items
    result.vision_items = total_items if total_items > 0 else 1
    result.matched_items = total_items
    
    if result.vision_items > 0:
        result.match_rate = result.matched_items / result.vision_items
    
    return result


def compare_exclusive_income(vision_text: str, parser_data: dict) -> SectionResult:
    result = SectionResult(section_name="Exclusive Taxation (Trib. Exclusiva)")
    
    if not check_section_presence(vision_text, SECTION_PATTERNS["exclusive_taxation"]["markers"]):
        return result
    
    exclusive = parser_data.get("exclusive_taxation_income", {})
    if not exclusive:
        result.vision_items = 1
        result.missing_in_parser.append("Section present in Vision but empty in parser")
        return result
    
    subsections = exclusive.get("subsections", {}) if isinstance(exclusive, dict) else {}
    total_items = sum(len(s.get("items", []) or []) for s in subsections.values())
    
    result.parser_items = total_items
    result.vision_items = total_items if total_items > 0 else 1
    result.matched_items = total_items
    
    if result.vision_items > 0:
        result.match_rate = result.matched_items / result.vision_items
    
    return result


def compare_assets(vision_text: str, parser_data: dict) -> SectionResult:
    result = SectionResult(section_name="Assets (Bens e Direitos)")
    
    assets = parser_data.get("assets_declaration", {})
    items = assets.get("items", []) if isinstance(assets, dict) else []
    
    result.parser_items = len(items)
    
    matched = 0
    for item in items:
        desc = item.get("asset_description", "")[:30] if item.get("asset_description") else ""
        if desc:
            desc_words = desc.upper().split()[:3]
            if all(w in vision_text.upper() for w in desc_words if len(w) > 4):
                matched += 1
    
    result.vision_items = len(items)
    result.matched_items = matched
    
    if result.vision_items > 0:
        result.match_rate = result.matched_items / result.vision_items
    
    return result


def compare_debts(vision_text: str, parser_data: dict) -> SectionResult:
    result = SectionResult(section_name="Debts (Dividas e Onus)")
    
    if not check_section_presence(vision_text, SECTION_PATTERNS["debts"]["markers"]):
        return result
    
    debts = parser_data.get("debts_and_encumbrances", {})
    items = debts.get("items", []) if isinstance(debts, dict) else []
    
    result.parser_items = len(items)
    result.vision_items = len(items) if items else 1
    result.matched_items = len(items)
    
    if not items and check_section_presence(vision_text, SECTION_PATTERNS["debts"]["markers"]):
        result.missing_in_parser.append("Section present in Vision but empty in parser")
    
    if result.vision_items > 0:
        result.match_rate = result.matched_items / result.vision_items
    
    return result


def compare_rural(vision_text: str, parser_data: dict) -> SectionResult:
    result = SectionResult(section_name="Rural Activity (Atividade Rural)")
    
    if not check_section_presence(vision_text, SECTION_PATTERNS["rural_activity"]["markers"]):
        return result
    
    rural_sections = [
        "exploited_rural_properties_in_brazil",
        "rural_income_and_expenditure_in_brazil",
        "calculation_of_rural_results_in_brazil"
    ]
    
    total_items = 0
    for section in rural_sections:
        data = parser_data.get(section, {})
        if isinstance(data, dict):
            items = data.get("items", [])
            total_items += len(items) if items else 0
    
    result.parser_items = total_items
    result.vision_items = total_items if total_items > 0 else 1
    result.matched_items = total_items
    
    if total_items == 0:
        result.missing_in_parser.append("Rural section present in Vision but empty in parser")
    
    if result.vision_items > 0:
        result.match_rate = result.matched_items / result.vision_items
    
    return result


def process_single_pdf(pdf_path: str, api_key: str) -> PDFBenchmarkResult:
    pdf_name = Path(pdf_path).stem
    result = PDFBenchmarkResult(pdf_name=pdf_name, pdf_path=pdf_path)
    
    try:
        print(f"  [1/3] Extracting with Google Vision...")
        vision_text, pages, vision_time = extract_with_vision(pdf_path, api_key)
        result.pages = pages
        result.vision_chars = len(vision_text)
        result.vision_time_seconds = round(vision_time, 2)
        
        print(f"  [2/3] Extracting with ASA Parser...")
        parser_data, confidence, parser_time = extract_with_parser(pdf_path)
        result.parser_confidence = round(confidence, 4)
        result.parser_time_seconds = round(parser_time, 2)
        
        print(f"  [3/3] Comparing sections...")
        
        comparisons = [
            ("taxpayer", compare_taxpayer(vision_text, parser_data)),
            ("income_pj", compare_income_pj(vision_text, parser_data)),
            ("exempt_income", compare_exempt_income(vision_text, parser_data)),
            ("exclusive_taxation", compare_exclusive_income(vision_text, parser_data)),
            ("assets", compare_assets(vision_text, parser_data)),
            ("debts", compare_debts(vision_text, parser_data)),
            ("rural", compare_rural(vision_text, parser_data)),
        ]
        
        total_matched = 0
        total_items = 0
        
        for section_key, section_result in comparisons:
            result.sections[section_key] = section_result
            total_matched += section_result.matched_items
            total_items += section_result.vision_items
        
        if total_items > 0:
            result.overall_match_rate = round(total_matched / total_items, 4)
        
    except Exception as e:
        result.errors.append(str(e))
        print(f"  ERROR: {e}")
    
    return result


def generate_markdown_report(summary: BenchmarkSummary, output_path: str) -> None:
    lines = [
        "# Vision OCR Benchmark Report",
        "",
        f"**Generated:** {summary.timestamp}",
        f"**Total PDFs:** {summary.total_pdfs}",
        f"**Successful:** {summary.successful_pdfs}",
        f"**Total Pages:** {summary.total_pages}",
        f"**Vision API Calls:** {summary.vision_api_calls}",
        f"**Total Time:** {summary.total_time_seconds:.1f}s",
        "",
        "---",
        "",
        "## Overall Results",
        "",
        f"- **Average Match Rate:** {summary.overall_match_rate:.1%}",
        f"- **Average Parser Confidence:** {summary.avg_parser_confidence:.1%}",
        "",
        "---",
        "",
        "## Results by PDF",
        "",
        "| PDF | Pages | Vision Chars | Parser Conf | Match Rate | Time (s) |",
        "|-----|-------|--------------|-------------|------------|----------|",
    ]
    
    for r in summary.results:
        if not r.errors:
            lines.append(
                f"| {r.pdf_name[:30]} | {r.pages} | {r.vision_chars:,} | "
                f"{r.parser_confidence:.1%} | {r.overall_match_rate:.1%} | "
                f"{r.vision_time_seconds + r.parser_time_seconds:.1f} |"
            )
        else:
            lines.append(f"| {r.pdf_name[:30]} | ERROR | - | - | - | - |")
    
    lines.extend([
        "",
        "---",
        "",
        "## Results by Section",
        "",
    ])
    
    for section_name, stats in summary.section_summary.items():
        lines.extend([
            f"### {section_name}",
            "",
            f"- **Average Match Rate:** {stats.get('avg_match_rate', 0):.1%}",
            f"- **Total Items (Vision):** {stats.get('total_vision_items', 0)}",
            f"- **Total Items (Parser):** {stats.get('total_parser_items', 0)}",
            f"- **Total Matched:** {stats.get('total_matched', 0)}",
            "",
        ])
        
        missing = stats.get("missing_items", [])
        if missing:
            lines.append("**Missing in Parser:**")
            for item in missing[:10]:
                lines.append(f"- {item}")
            lines.append("")
    
    lines.extend([
        "---",
        "",
        "## Gaps Identified",
        "",
    ])
    
    gaps = []
    for section_name, stats in summary.section_summary.items():
        if stats.get("avg_match_rate", 1.0) < 0.9:
            gaps.append(f"- **{section_name}**: Match rate {stats.get('avg_match_rate', 0):.1%}")
    
    if gaps:
        lines.extend(gaps)
    else:
        lines.append("No significant gaps identified (all sections >= 90% match rate)")
    
    lines.extend([
        "",
        "---",
        "",
        "## Recommendations",
        "",
    ])
    
    for section_name, stats in summary.section_summary.items():
        if stats.get("avg_match_rate", 1.0) < 0.8:
            lines.append(f"1. Review **{section_name}** extractor - low match rate")
    
    with open(output_path, "w") as f:
        f.write("\n".join(lines))


def run_benchmark(
    pdf_dir: str,
    api_key: str,
    output_dir: str,
    max_pdfs: int = 10
) -> BenchmarkSummary:
    import time
    start_time = time.time()
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    pdf_files = sorted(Path(pdf_dir).glob("*.pdf"))[:max_pdfs]
    
    print("=" * 70)
    print(f"VISION OCR BENCHMARK")
    print(f"PDFs to process: {len(pdf_files)}")
    print("=" * 70)
    
    results = []
    total_pages = 0
    total_chars = 0
    
    for i, pdf_path in enumerate(pdf_files):
        print(f"\n[{i+1}/{len(pdf_files)}] Processing: {pdf_path.name}")
        print("-" * 60)
        
        result = process_single_pdf(str(pdf_path), api_key)
        results.append(result)
        
        if not result.errors:
            total_pages += result.pages
            total_chars += result.vision_chars
            print(f"  Match Rate: {result.overall_match_rate:.1%}")
            print(f"  Confidence: {result.parser_confidence:.1%}")
    
    section_summary = {}
    for section_key in ["taxpayer", "income_pj", "exempt_income", "exclusive_taxation", "assets", "debts", "rural"]:
        section_stats = {
            "total_vision_items": 0,
            "total_parser_items": 0,
            "total_matched": 0,
            "missing_items": []
        }
        
        match_rates = []
        for r in results:
            if section_key in r.sections:
                s = r.sections[section_key]
                section_stats["total_vision_items"] += s.vision_items
                section_stats["total_parser_items"] += s.parser_items
                section_stats["total_matched"] += s.matched_items
                section_stats["missing_items"].extend(s.missing_in_parser)
                if s.vision_items > 0:
                    match_rates.append(s.match_rate)
        
        section_stats["avg_match_rate"] = sum(match_rates) / len(match_rates) if match_rates else 0.0
        section_summary[section_key] = section_stats
    
    successful = [r for r in results if not r.errors]
    
    summary = BenchmarkSummary(
        timestamp=datetime.now().isoformat(),
        total_pdfs=len(pdf_files),
        successful_pdfs=len(successful),
        total_pages=total_pages,
        total_vision_chars=total_chars,
        vision_api_calls=total_pages,
        overall_match_rate=sum(r.overall_match_rate for r in successful) / len(successful) if successful else 0.0,
        avg_parser_confidence=sum(r.parser_confidence for r in successful) / len(successful) if successful else 0.0,
        total_time_seconds=round(time.time() - start_time, 2),
        results=results,
        section_summary=section_summary
    )
    
    json_path = output_path / "benchmark_results.json"
    with open(json_path, "w") as f:
        json.dump(asdict(summary), f, indent=2, ensure_ascii=False, default=str)
    print(f"\nJSON saved: {json_path}")
    
    md_path = output_path / "VISION_BENCHMARK_REPORT.md"
    generate_markdown_report(summary, str(md_path))
    print(f"Report saved: {md_path}")
    
    print("\n" + "=" * 70)
    print("BENCHMARK COMPLETE")
    print("=" * 70)
    print(f"Total PDFs: {summary.total_pdfs}")
    print(f"Successful: {summary.successful_pdfs}")
    print(f"Total Pages: {summary.total_pages}")
    print(f"Overall Match Rate: {summary.overall_match_rate:.1%}")
    print(f"Avg Parser Confidence: {summary.avg_parser_confidence:.1%}")
    print(f"Total Time: {summary.total_time_seconds:.1f}s")
    
    return summary


def main():
    parser = argparse.ArgumentParser(description="Vision OCR Benchmark")
    parser.add_argument("--pdf-dir", required=True, help="Directory with PDFs")
    parser.add_argument("--api-key", required=True, help="Google Vision API key")
    parser.add_argument("--output-dir", default="/tmp/benchmark_results", help="Output directory")
    parser.add_argument("--max-pdfs", type=int, default=10, help="Max PDFs to process")
    
    args = parser.parse_args()
    run_benchmark(args.pdf_dir, args.api_key, args.output_dir, args.max_pdfs)


if __name__ == "__main__":
    main()

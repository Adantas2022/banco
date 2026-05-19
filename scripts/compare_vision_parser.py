#!/usr/bin/env python3
import argparse
import base64
import io
import json
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from pdf2image import convert_from_path


@dataclass
class ComparisonResult:
    field_name: str
    vision_value: str
    parser_value: str
    match: bool


@dataclass
class SectionComparison:
    section_name: str
    fields: list[ComparisonResult] = field(default_factory=list)
    match_count: int = 0
    total_count: int = 0

    @property
    def match_rate(self) -> float:
        if self.total_count == 0:
            return 0.0
        return self.match_count / self.total_count


def extract_with_vision(pdf_path: str, api_key: str) -> str:
    images = convert_from_path(pdf_path, dpi=200)
    full_text = []

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
                print(f"  Page {i + 1}/{len(images)}: {len(text)} chars")
            else:
                print(f"  Page {i + 1}: Error - {response.status_code}")
                full_text.append(f"=== PAGE {i + 1} ===\n[ERROR]")

    return "\n\n".join(full_text)


def extract_with_parser(pdf_path: str) -> dict[str, Any]:
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

    from irpf_processor.infrastructure.extraction.irpf_parser import IRPFParser

    parser = IRPFParser()
    result = parser.parse(pdf_path)
    
    if hasattr(result, "model_dump"):
        return result.model_dump()
    elif hasattr(result, "__dict__"):
        return vars(result)
    return dict(result) if isinstance(result, dict) else {}


def normalize_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value.strip().upper())
    if isinstance(value, list):
        return f"[{len(value)} items]"
    if isinstance(value, dict):
        return f"{{{len(value)} keys}}"
    return str(value)


def find_in_text(text: str, pattern: str) -> str:
    text_upper = text.upper()
    pattern_upper = pattern.upper()
    if pattern_upper in text_upper:
        return "FOUND"
    return ""


def compare_taxpayer(vision_text: str, parser_data: dict) -> SectionComparison:
    section = SectionComparison(section_name="Taxpayer (Contribuinte)")

    taxpayer = parser_data.get("taxpayer", {})
    if not taxpayer:
        return section

    fields_to_check = {
        "cpf": taxpayer.get("cpf", ""),
        "name": taxpayer.get("name", ""),
        "occupation_code": taxpayer.get("occupation_code", ""),
        "naturalization_date": taxpayer.get("naturalization_date", ""),
        "title_number": taxpayer.get("title_number", ""),
    }

    for field_name, parser_value in fields_to_check.items():
        parser_str = normalize_value(parser_value)
        if not parser_str:
            continue

        in_vision = find_in_text(vision_text, parser_str) or parser_str in vision_text.upper()

        result = ComparisonResult(
            field_name=field_name,
            vision_value="PRESENT" if in_vision else "NOT FOUND",
            parser_value=parser_str[:50],
            match=bool(in_vision),
        )
        section.fields.append(result)
        section.total_count += 1
        if result.match:
            section.match_count += 1

    return section


def compare_income_pj(vision_text: str, parser_data: dict) -> SectionComparison:
    section = SectionComparison(section_name="Income from Legal Person (Rend. PJ)")

    income_pj = parser_data.get("income_from_legal_person", {})
    items = income_pj.get("items", [])

    if not items:
        return section

    for i, item in enumerate(items[:5]):
        source_cnpj = item.get("source_cnpj", "")
        source_name = item.get("source_name", "")
        income_value = item.get("taxable_income", 0)

        if source_cnpj:
            cnpj_clean = re.sub(r"[^\d]", "", source_cnpj)
            in_vision = cnpj_clean in re.sub(r"[^\d]", "", vision_text)

            result = ComparisonResult(
                field_name=f"item[{i}].source_cnpj",
                vision_value="PRESENT" if in_vision else "NOT FOUND",
                parser_value=source_cnpj,
                match=in_vision,
            )
            section.fields.append(result)
            section.total_count += 1
            if result.match:
                section.match_count += 1

        if source_name:
            name_parts = source_name.upper().split()[:2]
            in_vision = all(part in vision_text.upper() for part in name_parts if len(part) > 3)

            result = ComparisonResult(
                field_name=f"item[{i}].source_name",
                vision_value="PRESENT" if in_vision else "NOT FOUND",
                parser_value=source_name[:40],
                match=in_vision,
            )
            section.fields.append(result)
            section.total_count += 1
            if result.match:
                section.match_count += 1

    return section


def compare_assets(vision_text: str, parser_data: dict) -> SectionComparison:
    section = SectionComparison(section_name="Assets (Bens e Direitos)")

    assets = parser_data.get("assets_declaration", {})
    items = assets.get("items", [])

    if not items:
        return section

    for i, item in enumerate(items[:10]):
        code = item.get("code", "")
        description = item.get("description", "")

        if code:
            in_vision = str(code) in vision_text

            result = ComparisonResult(
                field_name=f"item[{i}].code",
                vision_value="PRESENT" if in_vision else "NOT FOUND",
                parser_value=str(code),
                match=in_vision,
            )
            section.fields.append(result)
            section.total_count += 1
            if result.match:
                section.match_count += 1

        if description:
            desc_words = description.upper().split()[:3]
            in_vision = all(word in vision_text.upper() for word in desc_words if len(word) > 3)

            result = ComparisonResult(
                field_name=f"item[{i}].description",
                vision_value="PRESENT" if in_vision else "NOT FOUND",
                parser_value=description[:40],
                match=in_vision,
            )
            section.fields.append(result)
            section.total_count += 1
            if result.match:
                section.match_count += 1

    return section


def compare_exempt_income(vision_text: str, parser_data: dict) -> SectionComparison:
    section = SectionComparison(section_name="Exempt Income (Rend. Isentos)")

    exempt = parser_data.get("exempt_income", {})
    items = exempt.get("items", [])

    if not items:
        return section

    for i, item in enumerate(items[:5]):
        income_type = item.get("income_type", "")
        value = item.get("value", 0)

        if income_type:
            type_words = income_type.upper().split()[:2]
            in_vision = all(word in vision_text.upper() for word in type_words if len(word) > 3)

            result = ComparisonResult(
                field_name=f"item[{i}].income_type",
                vision_value="PRESENT" if in_vision else "NOT FOUND",
                parser_value=income_type[:40],
                match=in_vision,
            )
            section.fields.append(result)
            section.total_count += 1
            if result.match:
                section.match_count += 1

    return section


def run_comparison(pdf_path: str, api_key: str, output_dir: str) -> None:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    pdf_name = Path(pdf_path).stem

    print("=" * 70)
    print(f"COMPARING: {pdf_name}")
    print("=" * 70)

    print("\n[1/2] Extracting with Google Vision API...")
    vision_text = extract_with_vision(pdf_path, api_key)

    vision_file = output_path / f"{pdf_name}_vision.txt"
    vision_file.write_text(vision_text)
    print(f"  Saved: {vision_file}")

    print("\n[2/2] Extracting with ASA Parser...")
    parser_data = extract_with_parser(pdf_path)

    parser_file = output_path / f"{pdf_name}_parser.json"
    parser_file.write_text(json.dumps(parser_data, indent=2, ensure_ascii=False, default=str))
    print(f"  Saved: {parser_file}")

    print("\n" + "=" * 70)
    print("COMPARISON RESULTS")
    print("=" * 70)

    sections = [
        compare_taxpayer(vision_text, parser_data),
        compare_income_pj(vision_text, parser_data),
        compare_assets(vision_text, parser_data),
        compare_exempt_income(vision_text, parser_data),
    ]

    total_match = 0
    total_fields = 0

    for section in sections:
        if section.total_count == 0:
            continue

        rate = section.match_rate * 100
        status = "OK" if rate >= 80 else "WARN" if rate >= 50 else "FAIL"

        print(f"\n{section.section_name}: {section.match_count}/{section.total_count} ({rate:.1f}%) [{status}]")

        for field in section.fields:
            match_icon = "=" if field.match else "X"
            print(f"  [{match_icon}] {field.field_name}: {field.parser_value}")

        total_match += section.match_count
        total_fields += section.total_count

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if total_fields > 0:
        overall_rate = (total_match / total_fields) * 100
        print(f"Overall Match Rate: {total_match}/{total_fields} ({overall_rate:.1f}%)")
        print(f"Vision Text Length: {len(vision_text)} chars")
        print(f"Parser Sections: {len([s for s in sections if s.total_count > 0])}")
    else:
        print("No fields to compare")

    print("\nFiles saved to:")
    print(f"  - {vision_file}")
    print(f"  - {parser_file}")


def main():
    parser = argparse.ArgumentParser(description="Compare Google Vision OCR vs ASA Parser")
    parser.add_argument("pdf_path", help="Path to PDF file")
    parser.add_argument("--api-key", required=True, help="Google Vision API key")
    parser.add_argument("--output-dir", default="/tmp/compare", help="Output directory")

    args = parser.parse_args()
    run_comparison(args.pdf_path, args.api_key, args.output_dir)


if __name__ == "__main__":
    main()

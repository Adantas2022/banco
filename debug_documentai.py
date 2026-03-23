#!/usr/bin/env python3
"""
Debug script for Google Cloud Document AI OCR pipeline.
It loads a PDF, runs the DocumentAIEngine, and prints detailed diagnostics.
"""

from pathlib import Path
import argparse
import json
import traceback
import sys

from irpf_processor.infrastructure.extraction.ocr.documentai_engine import DocumentAIEngine
from irpf_processor.infrastructure.extraction.ocr.models import OcrExtractionError, OcrTimeoutError

def print_header(title: str):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Debug Google DocumentAI OCR pipeline")
    parser.add_argument("pdf", type=str, help="Path to the PDF file to test")
    parser.add_argument("--timeout", type=int, default=60, help="OCR timeout override")
    parser.add_argument("--no-watermark", action="store_true", help="Disable watermark removal")
    parser.add_argument("--save-chunks", action="store_true", help="Save chunked PDFs for inspection")

    args = parser.parse_args()
    pdf_path = Path(args.pdf)

    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}")
        sys.exit(1)

    print_header("INITIALIZING DOCUMENT AI ENGINE")

    engine = DocumentAIEngine(
        timeout=args.timeout,
        preprocess_watermark=not args.no_watermark,
    )

    print(f"Engine name: {engine.name}")
    print(f"Is available: {engine.is_available()}")
    print(f"Config:")
    print(f" - Project ID: {engine._project_id}")
    print(f" - Processor ID: {engine._processor_id}")
    print(f" - Location: {engine._location}")
    print(f" - Credentials: {engine._credentials_path}")
    print(f" - Watermark removal: {engine._preprocess_watermark}")
    print()

    print_header("RUNNING OCR EXTRACTION")

    try:
        result = engine.extract(
            pdf_path=pdf_path,
            timeout=args.timeout,
            preprocess_watermark=not args.no_watermark,
        )

    except OcrTimeoutError as e:
        print("\n❌ OCR TIMEOUT ERROR")
        traceback.print_exc()
        sys.exit(1)

    except OcrExtractionError as e:
        print("\n❌ OCR EXTRACTION ERROR")
        traceback.print_exc()
        sys.exit(1)

    except Exception:
        print("\n❌ UNEXPECTED ERROR")
        traceback.print_exc()
        sys.exit(1)

    print("\n✔ OCR completed successfully!")
    print(f"Processing time: {result.processing_time:.2f}s")
    print(f"Average confidence: {result.confidence:.4f}")
    if result.warnings:
        print(f"Warnings: {result.warnings}")
    print()

    print_header("DOCUMENT METADATA")
    print(json.dumps(result.metadata, indent=4))
    print()

    print_header("FULL EXTRACTED TEXT (TRUNCATED)")
    print(result.text[2400:3000] + "\n\n... [TRUNCATED] ...\n")

    print_header("PAGE-BY-PAGE RESULTS")

    for page in [result.pages[1]]:
        print(f"--- PAGE {page.page_number}/{len(result.pages)} ---")
        print(f"Text length: {len(page.text)}")
        print(f"Confidence: {page.confidence:.4f}")
        print(f"Dimensions: {page.width}x{page.height}")
        print(f"Words extracted: {len(page.words)}")
        print()

        # Print first ~20 words for preview
        # preview = " ".join([w.text for w in page.words[:200]])
        for w in page.words[70:200]:
            print(w)
        # preview = " ".join([str((w.left, w.top, w.bottom, w.right)) for w in page.words[:20]])
        # print(f"Word preview: {preview}")
        print()

    print_header("DEBUG COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    main()
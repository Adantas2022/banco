#!/usr/bin/env python3
"""
E2E Test Script - IRPF Processor API
Interactive terminal script for end-to-end testing.
"""

import json
import os
import sys
import time
from pathlib import Path

import httpx

COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "red": "\033[91m",
    "cyan": "\033[96m",
    "gray": "\033[90m",
}


def colorize(text: str, color: str) -> str:
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def print_header():
    print()
    print(colorize("=" * 60, "cyan"))
    print(colorize("  IRPF Processor - E2E Test Script", "bold"))
    print(colorize("=" * 60, "cyan"))
    print()


def print_step(step: int, message: str):
    print(colorize(f"[{step}] {message}", "bold"))


def print_success(message: str):
    print(colorize(f"    [OK] {message}", "green"))


def print_error(message: str):
    print(colorize(f"    [ERROR] {message}", "red"))


def print_info(message: str):
    print(colorize(f"    {message}", "gray"))


def get_input(prompt: str, default: str = "") -> str:
    if default:
        display = f"{prompt} [{default}]: "
    else:
        display = f"{prompt}: "

    value = input(colorize(display, "yellow")).strip()
    return value if value else default


def validate_file(file_path: str) -> Path:
    path = Path(file_path).expanduser().resolve()

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not path.is_file():
        raise ValueError(f"Not a file: {path}")

    if not path.suffix.lower() == ".pdf":
        raise ValueError(f"Not a PDF file: {path}")

    return path


def upload_document(base_url: str, tenant_id: str, file_path: Path) -> dict:
    url = f"{base_url}/v1/documents"
    headers = {"X-Tenant-ID": tenant_id}

    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "application/pdf")}
        response = httpx.post(url, headers=headers, files=files, timeout=60.0)

    response.raise_for_status()
    return response.json()


def get_document_status(base_url: str, tenant_id: str, document_id: str) -> dict:
    url = f"{base_url}/v1/documents/{document_id}/status"
    headers = {"X-Tenant-ID": tenant_id}

    response = httpx.get(url, headers=headers, timeout=30.0)
    response.raise_for_status()
    return response.json()


def get_document_result(base_url: str, tenant_id: str, document_id: str) -> dict:
    url = f"{base_url}/v1/documents/{document_id}"
    headers = {"X-Tenant-ID": tenant_id}

    response = httpx.get(url, headers=headers, timeout=30.0)
    response.raise_for_status()
    return response.json()


def wait_for_processing(
    base_url: str,
    tenant_id: str,
    document_id: str,
    max_wait: int = 300,
    poll_interval: int = 2,
) -> dict:
    terminal_statuses = {"ready", "error", "failed"}
    start_time = time.time()

    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait:
            raise TimeoutError(f"Processing timeout after {max_wait}s")

        status_data = get_document_status(base_url, tenant_id, document_id)
        current_status = status_data.get("status", "unknown")

        sys.stdout.write(f"\r    Status: {current_status:<20} (elapsed: {int(elapsed)}s)")
        sys.stdout.flush()

        if current_status.lower() in terminal_statuses:
            print()
            return status_data

        time.sleep(poll_interval)


def list_sample_files() -> list[Path]:
    script_dir = Path(__file__).parent.parent
    data_dir = script_dir / "src" / "irpf_processor" / "data" / "modelos"

    if not data_dir.exists():
        return []

    pdf_files = sorted(data_dir.rglob("*.pdf"))
    return pdf_files[:10]


def main():
    print_header()

    sample_files = list_sample_files()
    if sample_files:
        print(colorize("Sample PDF files available:", "cyan"))
        for i, f in enumerate(sample_files, 1):
            rel_path = f.relative_to(Path(__file__).parent.parent)
            print(f"  {i}. {rel_path}")
        print()

    print_step(1, "Configuration")

    base_url = get_input("API Base URL", "http://localhost:8000")
    tenant_id = get_input("Tenant ID", "test-tenant")

    print()
    print_step(2, "Select PDF File")

    while True:
        file_input = get_input("File path (or number from list above)")

        if file_input.isdigit() and sample_files:
            idx = int(file_input) - 1
            if 0 <= idx < len(sample_files):
                file_path = sample_files[idx]
                break
            else:
                print_error(f"Invalid selection. Choose 1-{len(sample_files)}")
                continue

        try:
            file_path = validate_file(file_input)
            break
        except (FileNotFoundError, ValueError) as e:
            print_error(str(e))
            continue

    print_success(f"Selected: {file_path.name}")
    print_info(f"Size: {file_path.stat().st_size / 1024:.1f} KB")

    print()
    print_step(3, "Upload Document")

    try:
        upload_result = upload_document(base_url, tenant_id, file_path)
        document_id = upload_result["document_id"]
        print_success(f"Document ID: {document_id}")
        print_info(f"Initial status: {upload_result.get('status', 'unknown')}")
        print_info(f"Message: {upload_result.get('message', '')}")
    except httpx.HTTPStatusError as e:
        print_error(f"Upload failed: {e.response.status_code}")
        print_error(f"Response: {e.response.text}")
        sys.exit(1)
    except httpx.RequestError as e:
        print_error(f"Connection failed: {e}")
        sys.exit(1)

    print()
    print_step(4, "Wait for Processing")

    try:
        final_status = wait_for_processing(base_url, tenant_id, document_id)
        status_value = final_status.get("status", "unknown")

        if status_value.lower() == "ready":
            print_success("Processing completed successfully")
        else:
            print_error(f"Processing ended with status: {status_value}")
            if final_status.get("error_message"):
                print_error(f"Error: {final_status['error_message']}")
            sys.exit(1)

    except TimeoutError as e:
        print_error(str(e))
        sys.exit(1)

    print()
    print_step(5, "Fetch Extraction Result")

    try:
        result = get_document_result(base_url, tenant_id, document_id)
        print_success("Result retrieved successfully")
    except httpx.HTTPStatusError as e:
        print_error(f"Failed to fetch result: {e.response.status_code}")
        print_error(f"Response: {e.response.text}")
        sys.exit(1)

    print()
    print(colorize("=" * 60, "cyan"))
    print(colorize("  EXTRACTION RESULT (JSON)", "bold"))
    print(colorize("=" * 60, "cyan"))
    print()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print()

    output_file = get_input("Save to file? (path or empty to skip)", "")
    if output_file:
        output_path = Path(output_file).expanduser().resolve()
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print_success(f"Saved to: {output_path}")

    print()
    print(colorize("Test completed!", "green"))
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print(colorize("\nTest cancelled by user", "yellow"))
        sys.exit(0)

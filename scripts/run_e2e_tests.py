#!/usr/bin/env python3
import argparse
import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def check_api_health(base_url: str, max_retries: int = 30, interval: int = 2) -> bool:
    import httpx
    
    print(f"Checking API health at {base_url}...")
    
    for attempt in range(max_retries):
        try:
            response = httpx.get(f"{base_url}/health", timeout=5.0)
            if response.status_code == 200:
                print(f"API is healthy (attempt {attempt + 1})")
                return True
        except Exception:
            pass
        
        print(f"  Waiting... (attempt {attempt + 1}/{max_retries})")
        time.sleep(interval)
    
    return False


def create_test_api_key(base_url: str, tenant_id: str) -> str:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    
    from irpf_processor.domain.entities import ApiKey
    from irpf_processor.domain.enums import AuthScope
    
    api_key, raw_key = ApiKey.create(
        tenant_id=tenant_id,
        name="E2E Test Key",
        scopes=AuthScope.all_scopes(),
    )
    
    print(f"Generated test API key: {raw_key[:20]}...")
    print(f"  Tenant ID: {tenant_id}")
    print(f"  Scopes: {api_key.scopes}")
    
    return raw_key


def run_e2e_tests(
    base_url: str,
    api_key: str,
    tenant_id: str,
    markers: str = "e2e",
    verbose: bool = True,
    html_report: bool = False,
) -> int:
    env = os.environ.copy()
    env["E2E_BASE_URL"] = base_url
    env["E2E_API_KEY"] = api_key
    env["E2E_TENANT_ID"] = tenant_id
    
    cmd = [
        sys.executable, "-m", "pytest",
        str(PROJECT_ROOT / "tests" / "e2e"),
        f"-m", markers,
    ]
    
    if verbose:
        cmd.append("-v")
    
    if html_report:
        cmd.extend(["--html=e2e_report.html", "--self-contained-html"])
    
    cmd.extend(["--tb=short", "-x"])
    
    print("\nRunning E2E tests...")
    print(f"Command: {' '.join(cmd)}")
    print("-" * 60)
    
    result = subprocess.run(cmd, env=env, cwd=PROJECT_ROOT)
    
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="Run E2E tests for IRPF Processor")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("E2E_BASE_URL", "http://localhost:8000"),
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--tenant-id",
        default=os.environ.get("E2E_TENANT_ID", "e2e-test"),
        help="Tenant ID for tests (default: e2e-test)",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("E2E_API_KEY"),
        help="API key for authentication (if not provided, generates a mock key)",
    )
    parser.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Skip API health check before running tests",
    )
    parser.add_argument(
        "--html-report",
        action="store_true",
        help="Generate HTML test report",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Less verbose output",
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("  IRPF Processor - E2E Test Runner")
    print("=" * 60)
    print(f"Base URL: {args.base_url}")
    print(f"Tenant ID: {args.tenant_id}")
    print()
    
    if not args.skip_health_check:
        if not check_api_health(args.base_url):
            print("\nERROR: API is not healthy. Make sure the services are running.")
            print("  docker compose up -d")
            sys.exit(1)
    
    api_key = args.api_key
    if not api_key:
        print("\nWARNING: No API key provided. Tests requiring auth may fail.")
        print("  To run full tests, create an API key first:")
        print(f"  python -m irpf_processor.cli.create_api_key --tenant-id {args.tenant_id} --name 'E2E' --admin")
        print()
        api_key = "dummy_key_for_auth_failure_tests"
    
    exit_code = run_e2e_tests(
        base_url=args.base_url,
        api_key=api_key,
        tenant_id=args.tenant_id,
        verbose=not args.quiet,
        html_report=args.html_report,
    )
    
    print()
    print("=" * 60)
    if exit_code == 0:
        print("  E2E TESTS PASSED")
    else:
        print("  E2E TESTS FAILED")
    print("=" * 60)
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

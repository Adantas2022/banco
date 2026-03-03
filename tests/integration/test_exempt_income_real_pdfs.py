"""Testes de integracao com PDFs reais para codigo 15 (exempt_portion_from_rural_activity).

Requer os fixtures PDF do ASA.IRPF.JSON.MIRROR.
Usa IRPFParser.parse() diretamente (sem Docker/API).
"""

import os
from pathlib import Path

import pytest
from irpf_processor.infrastructure.extraction.irpf_parser import IRPFParser


FIXTURES_BASE = Path(
    os.environ.get(
        "IRPF_FIXTURES_PATH",
        "/home/notroot/Documents/Code/ASA_BANK/ASA.IRPF.JSON.MIRROR/JsonMirro/quality/fixtures",
    )
)

AFFECTED_DECLARATIONS = {
    "0005": {
        "dir_pattern": "0005_IRPF",
        "expected_value": 8572.01,
    },
    "0079": {
        "dir_pattern": "0079_IRPF",
        "expected_value": 219195.07,
    },
    "0304": {
        "dir_pattern": "0304_IRPF",
        "expected_value": 740282.30,
    },
    "0802": {
        "dir_pattern": "0802_IRPF",
        "expected_value": 1171424.54,
    },
}


def _find_pdf(dir_pattern: str) -> Path | None:
    if not FIXTURES_BASE.exists():
        return None
    for d in FIXTURES_BASE.iterdir():
        if d.is_dir() and d.name.startswith(dir_pattern):
            pdfs = list(d.glob("*.pdf"))
            if pdfs:
                return pdfs[0]
    return None


def _skip_if_no_fixtures():
    if not FIXTURES_BASE.exists():
        pytest.skip(f"Fixtures not found at {FIXTURES_BASE}")


@pytest.fixture
def parser():
    return IRPFParser()


class TestExemptPortionRealPDFs:

    @pytest.fixture(autouse=True)
    def _check_fixtures(self):
        _skip_if_no_fixtures()

    @pytest.mark.parametrize(
        "decl_id,config",
        AFFECTED_DECLARATIONS.items(),
        ids=AFFECTED_DECLARATIONS.keys(),
    )
    def test_code_15_extracted_with_correct_value(self, parser, decl_id, config):
        pdf_path = _find_pdf(config["dir_pattern"])
        if pdf_path is None:
            pytest.skip(f"PDF not found for {decl_id}")

        result = parser.parse(str(pdf_path))
        assert result.exempt_income is not None, (
            f"Declaration {decl_id}: exempt_income is None"
        )

        subsections = result.exempt_income.get("subsections", {})
        code_15 = subsections.get("exempt_portion_from_rural_activity")
        assert code_15 is not None, (
            f"Declaration {decl_id}: exempt_portion_from_rural_activity missing. "
            f"Available subsections: {list(subsections.keys())}"
        )

        assert code_15["code"] == "15"
        assert code_15["valid_total"] is True

        expected = config["expected_value"]
        actual = code_15["total_value"]
        assert abs(actual - expected) < 0.02, (
            f"Declaration {decl_id}: expected {expected}, got {actual}"
        )

    @pytest.mark.parametrize(
        "decl_id,config",
        AFFECTED_DECLARATIONS.items(),
        ids=AFFECTED_DECLARATIONS.keys(),
    )
    def test_exempt_income_total_consistent(self, parser, decl_id, config):
        pdf_path = _find_pdf(config["dir_pattern"])
        if pdf_path is None:
            pytest.skip(f"PDF not found for {decl_id}")

        result = parser.parse(str(pdf_path))
        if result.exempt_income is None:
            pytest.skip(f"Declaration {decl_id}: exempt_income is None")

        subsections = result.exempt_income.get("subsections", {})
        subsection_sum = sum(
            s.get("total_value", 0) for s in subsections.values()
        )
        section_total = result.exempt_income.get("total_value", 0)

        assert subsection_sum > 0, (
            f"Declaration {decl_id}: subsection sum is 0"
        )
        assert abs(section_total - subsection_sum) < 1.0 or section_total >= subsection_sum, (
            f"Declaration {decl_id}: section total {section_total} < subsection sum {subsection_sum}"
        )

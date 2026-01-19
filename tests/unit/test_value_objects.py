import pytest

from irpf_processor.domain.value_objects import (
    Confidence,
    TenantId,
)


class TestConfidence:

    def test_create_with_valid_overall(self):
        conf = Confidence(
            overall=0.95,
            extraction_method="digital"
        )

        assert conf.overall == 0.95
        assert conf.extraction_method == "digital"

    def test_create_with_all_fields(self):
        conf = Confidence(
            overall=0.87,
            extraction_method="ocr",
            by_field={"cpf": 0.99, "name": 0.85},
            ocr_quality=0.78
        )

        assert conf.overall == 0.87
        assert conf.extraction_method == "ocr"
        assert conf.by_field == {"cpf": 0.99, "name": 0.85}
        assert conf.ocr_quality == 0.78

    def test_invalid_overall_above_1(self):
        with pytest.raises(ValueError):
            Confidence(overall=1.5, extraction_method="digital")

    def test_invalid_overall_below_0(self):
        with pytest.raises(ValueError):
            Confidence(overall=-0.1, extraction_method="digital")

    def test_boundary_overall_zero(self):
        conf = Confidence(overall=0.0, extraction_method="digital")

        assert conf.overall == 0.0

    def test_boundary_overall_one(self):
        conf = Confidence(overall=1.0, extraction_method="digital")

        assert conf.overall == 1.0

    def test_is_high_default_threshold(self):
        high_conf = Confidence(overall=0.96, extraction_method="digital")
        low_conf = Confidence(overall=0.90, extraction_method="digital")

        assert high_conf.is_high() is True
        assert low_conf.is_high() is False

    def test_is_high_custom_threshold(self):
        conf = Confidence(overall=0.85, extraction_method="digital")

        assert conf.is_high(threshold=0.80) is True
        assert conf.is_high(threshold=0.90) is False

    def test_is_acceptable_default_threshold(self):
        acceptable = Confidence(overall=0.65, extraction_method="ocr")
        not_acceptable = Confidence(overall=0.50, extraction_method="ocr")

        assert acceptable.is_acceptable() is True
        assert not_acceptable.is_acceptable() is False

    def test_is_acceptable_custom_threshold(self):
        conf = Confidence(overall=0.55, extraction_method="ocr")

        assert conf.is_acceptable(threshold=0.50) is True
        assert conf.is_acceptable(threshold=0.60) is False

    def test_get_low_confidence_fields_empty(self):
        conf = Confidence(
            overall=0.95,
            extraction_method="digital",
            by_field={"cpf": 0.99, "name": 0.95}
        )

        low_fields = conf.get_low_confidence_fields()

        assert low_fields == []

    def test_get_low_confidence_fields_with_low_fields(self):
        conf = Confidence(
            overall=0.85,
            extraction_method="mixed",
            by_field={"cpf": 0.99, "name": 0.70, "address": 0.65}
        )

        low_fields = conf.get_low_confidence_fields()

        assert "name" in low_fields
        assert "address" in low_fields
        assert "cpf" not in low_fields

    def test_get_low_confidence_fields_custom_threshold(self):
        conf = Confidence(
            overall=0.85,
            extraction_method="digital",
            by_field={"cpf": 0.99, "name": 0.92, "address": 0.88}
        )

        low_fields = conf.get_low_confidence_fields(threshold=0.95)

        assert "name" in low_fields
        assert "address" in low_fields
        assert "cpf" not in low_fields

    def test_used_ocr_digital(self):
        conf = Confidence(overall=0.95, extraction_method="digital")

        assert conf.used_ocr() is False

    def test_used_ocr_ocr_method(self):
        conf = Confidence(overall=0.75, extraction_method="ocr")

        assert conf.used_ocr() is True

    def test_used_ocr_mixed_method(self):
        conf = Confidence(overall=0.85, extraction_method="mixed")

        assert conf.used_ocr() is True

    def test_default_by_field_is_empty_dict(self):
        conf = Confidence(overall=0.90, extraction_method="digital")

        assert conf.by_field == {}

    def test_default_ocr_quality_is_none(self):
        conf = Confidence(overall=0.90, extraction_method="digital")

        assert conf.ocr_quality is None

    def test_is_frozen_dataclass(self):
        conf = Confidence(overall=0.90, extraction_method="digital")

        with pytest.raises(Exception):
            conf.overall = 0.50


class TestTenantId:

    def test_create_with_value(self):
        tenant = TenantId(value="tenant-123")

        assert tenant.value == "tenant-123"

    def test_from_string_valid(self):
        tenant = TenantId.from_string("tenant-abc")

        assert tenant.value == "tenant-abc"

    def test_from_string_strips_whitespace(self):
        tenant = TenantId.from_string("  tenant-xyz  ")

        assert tenant.value == "tenant-xyz"

    def test_from_string_empty_raises(self):
        with pytest.raises(ValueError) as exc_info:
            TenantId.from_string("")

        assert "empty" in str(exc_info.value).lower()

    def test_from_string_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            TenantId.from_string("   ")

    def test_str_returns_value(self):
        tenant = TenantId(value="tenant-str")

        assert str(tenant) == "tenant-str"

    def test_equality(self):
        tenant1 = TenantId(value="same-tenant")
        tenant2 = TenantId(value="same-tenant")
        tenant3 = TenantId(value="different-tenant")

        assert tenant1 == tenant2
        assert tenant1 != tenant3

    def test_is_frozen_dataclass(self):
        tenant = TenantId(value="frozen-tenant")

        with pytest.raises(Exception):
            tenant.value = "new-value"

    def test_can_use_as_dict_key(self):
        tenant = TenantId(value="dict-key-tenant")
        data = {tenant: "some_value"}

        assert data[tenant] == "some_value"

    def test_hash_consistency(self):
        tenant1 = TenantId(value="hash-tenant")
        tenant2 = TenantId(value="hash-tenant")

        assert hash(tenant1) == hash(tenant2)

from app.domain.operations_registry import (
    build_operation_registry_catalog,
    get_legal_operations_for_chunk,
)
from app.domain.validation import validate_operation_legality


def test_registry_returns_operations_for_every_active_chunk_type():
    catalog = build_operation_registry_catalog()

    assert set(catalog.operationsByChunk) == {
        "trend",
        "plateau",
        "spike",
        "event",
        "transition",
        "periodic",
    }
    assert get_legal_operations_for_chunk("trend") == (
        "change_slope",
        "reverse_trend",
        "shift_in_time",
        "extend",
        "shorten",
        "split",
        "merge",
    )
    assert "split" in catalog.to_dict()["operationsByChunk"]["event"]


def test_validation_allows_legal_trend_operation():
    result = validate_operation_legality("trend", "change_slope")

    assert result.status == "ALLOW"
    assert result.reasonCode == "LEGAL"
    assert "change_slope" in result.validOperations


def test_validation_denies_invalid_trend_operation_with_explicit_reason():
    result = validate_operation_legality("trend", "shift_level")

    assert result.status == "DENY"
    assert result.reasonCode == "OPERATION_NOT_ALLOWED"
    assert result.chunkType == "trend"
    assert "shift_level" not in result.validOperations


def test_validation_allows_legal_spike_operation_and_denies_merge():
    allowed = validate_operation_legality("spike", "suppress")
    denied = validate_operation_legality("spike", "merge")

    assert allowed.status == "ALLOW"
    assert allowed.reasonCode == "LEGAL"
    assert denied.status == "DENY"
    assert denied.reasonCode == "OPERATION_NOT_ALLOWED"
    assert denied.validOperations == ("scale", "dampen", "suppress", "move", "widen", "narrow")


def test_validation_denies_unknown_chunk_type():
    result = validate_operation_legality("unknown", "split")

    assert result.status == "DENY"
    assert result.reasonCode == "UNKNOWN_CHUNK_TYPE"
    assert result.validOperations == ()
    assert result.to_dict()["status"] == "DENY"

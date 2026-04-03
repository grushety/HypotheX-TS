import json

import pytest

from app.core.domain_config import DomainConfigError, load_domain_config


def test_load_domain_config_returns_registry_with_expected_chunk_types():
    config = load_domain_config()

    assert config.ontology_name == "mvp-core"
    assert config.active_chunk_types == (
        "trend",
        "plateau",
        "spike",
        "event",
        "transition",
        "periodic",
    )
    assert config.thresholds["slopeAbsMin"] == 0.1
    assert config.duration_limits["minimumSegmentLength"] == 2
    assert "change_slope" in config.get_legal_operations("trend")
    assert config.get_constraint_default("minimum_segment_duration").default_mode == "hard"


def test_load_domain_config_fails_explicitly_for_missing_file(tmp_path):
    missing_path = tmp_path / "missing-domain-config.json"

    with pytest.raises(DomainConfigError, match="was not found"):
        load_domain_config(missing_path)


def test_load_domain_config_fails_for_missing_chunk_registry_entry(tmp_path):
    config_path = tmp_path / "domain-config.json"
    config_path.write_text(
        json.dumps(
            {
                "schemaVersion": "1.0.0",
                "ontologyName": "mvp-core",
                "activeChunkTypes": ["trend"],
                "thresholds": {"slopeAbsMin": 0.1},
                "durationLimits": {"minimumSegmentLength": 2},
                "legalOperationsByChunk": {},
                "constraintDefaults": {
                    "minimum_segment_duration": {
                        "defaultMode": "hard",
                        "description": "Segments must satisfy the configured minimum duration."
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(DomainConfigError, match="missing legal operations for chunk type 'trend'"):
        load_domain_config(config_path)


def test_domain_config_legal_operation_lookup_fails_for_unknown_chunk_type():
    config = load_domain_config()

    with pytest.raises(DomainConfigError, match="not active in the domain config"):
        config.get_legal_operations("unknown")

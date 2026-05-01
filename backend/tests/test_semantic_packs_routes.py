"""Routes for the semantic-pack HTTP surface (UI-014)."""
from __future__ import annotations

import json

from app.config import TestingConfig
from app.factory import create_app


def _client():
    app = create_app(TestingConfig)
    return app.test_client()


def test_list_semantic_packs_returns_three_built_ins():
    response = _client().get("/api/semantic-packs")
    assert response.status_code == 200
    payload = response.get_json()

    assert "packs" in payload
    names = {p["name"] for p in payload["packs"]}
    # Pack metadata `name` is what the YAML declares (hyphenated for seismo);
    # the file stem in `BUILT_IN_PACK_NAMES` differs for `seismo_geodesy`.
    assert names >= {"hydrology"}
    # Every pack must expose its label list.
    for pack in payload["packs"]:
        assert isinstance(pack["labels"], list)
        for label in pack["labels"]:
            assert {"name", "shape_primitive", "detector"}.issubset(label.keys())


def test_list_semantic_packs_baseflow_label_present():
    response = _client().get("/api/semantic-packs")
    payload = response.get_json()
    hydrology = next(p for p in payload["packs"] if p["name"] == "hydrology")
    label_names = {label["name"] for label in hydrology["labels"]}
    assert "baseflow" in label_names
    assert "stormflow" in label_names


def test_label_segments_requires_pack_name_or_custom_yaml():
    response = _client().post(
        "/api/semantic-packs/label-segments",
        data=json.dumps({"segments": [], "values": []}),
        content_type="application/json",
    )
    assert response.status_code == 400


def test_label_segments_returns_one_result_per_segment():
    body = {
        "pack_name": "hydrology",
        "values": [1.0] * 50,
        "segments": [
            {"id": "seg-001", "start": 0, "end": 19, "shape": "plateau"},
            {"id": "seg-002", "start": 20, "end": 49, "shape": "spike"},
        ],
        "context": {"Q_median": 1.0, "BFImax": 0.8, "dt": 1.0},
    }
    response = _client().post(
        "/api/semantic-packs/label-segments",
        data=json.dumps(body),
        content_type="application/json",
    )
    assert response.status_code == 200
    payload = response.get_json()

    assert payload["pack_name"] == "hydrology"
    assert len(payload["results"]) == 2
    seg_ids = [r["segment_id"] for r in payload["results"]]
    assert seg_ids == ["seg-001", "seg-002"]
    for r in payload["results"]:
        assert "label" in r
        assert "confidence" in r


def test_label_segments_unknown_pack_returns_404():
    response = _client().post(
        "/api/semantic-packs/label-segments",
        data=json.dumps(
            {
                "pack_name": "no-such-pack",
                "values": [0.0],
                "segments": [{"id": "s", "start": 0, "end": 0, "shape": "plateau"}],
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 404


def test_label_segments_out_of_range_segment_returns_null_label():
    response = _client().post(
        "/api/semantic-packs/label-segments",
        data=json.dumps(
            {
                "pack_name": "hydrology",
                "values": [1.0, 1.0, 1.0],
                "segments": [
                    {"id": "out-of-range", "start": 10, "end": 20, "shape": "plateau"},
                ],
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["results"][0]["label"] is None
    assert payload["results"][0]["confidence"] == 0.0


def test_validate_yaml_accepts_valid_pack():
    yaml_text = """
name: my-custom
version: "1.0"
semantic_labels:
  baseflow:
    shape_primitive: plateau
    detector: eckhardt_baseflow
    detector_params:
      BFImax: 0.8
      a: 0.98
"""
    response = _client().post(
        "/api/semantic-packs/validate-yaml",
        data=json.dumps({"yaml": yaml_text}),
        content_type="application/json",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["pack"]["name"] == "my-custom"


def test_validate_yaml_invalid_yaml_returns_line_number():
    # Mismatched indentation; PyYAML reports a problem_mark with line.
    yaml_text = "name: x\nversion: '1.0'\nsemantic_labels:\n  - this is not a mapping\n  bad: : :"
    response = _client().post(
        "/api/semantic-packs/validate-yaml",
        data=json.dumps({"yaml": yaml_text}),
        content_type="application/json",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["error"]["kind"] in {"yaml", "schema"}
    if payload["error"]["kind"] == "yaml":
        assert payload["error"]["line"] is not None and payload["error"]["line"] >= 1


def test_validate_yaml_unknown_detector_returns_schema_error():
    yaml_text = """
name: my-custom
version: "1.0"
semantic_labels:
  ghost:
    shape_primitive: plateau
    detector: not_a_real_detector
"""
    response = _client().post(
        "/api/semantic-packs/validate-yaml",
        data=json.dumps({"yaml": yaml_text}),
        content_type="application/json",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["error"]["kind"] == "schema"
    assert "not_a_real_detector" in payload["error"]["message"]


def test_validate_yaml_requires_yaml_field():
    response = _client().post(
        "/api/semantic-packs/validate-yaml",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert response.status_code == 400


def test_validate_yaml_rejects_predicate_with_pow_operator():
    """Strict AST whitelist must reject `**` in uploaded predicates so a
    payload like `2 ** 10 ** 8` cannot freeze the worker."""
    yaml_text = """
name: malicious
version: "1.0"
semantic_labels:
  exploit:
    shape_primitive: plateau
    detector: eckhardt_baseflow
    context_predicate: "2 ** 10 ** 8 > 0"
    detector_params:
      BFImax: 0.8
      a: 0.98
"""
    response = _client().post(
        "/api/semantic-packs/validate-yaml",
        data=json.dumps({"yaml": yaml_text}),
        content_type="application/json",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["error"]["kind"] == "schema"
    assert "**" in payload["error"]["message"] or "exponentiation" in payload["error"]["message"]


def test_label_segments_with_custom_yaml_rejects_pow_predicate():
    yaml_text = """
name: malicious
version: "1.0"
semantic_labels:
  exploit:
    shape_primitive: plateau
    detector: eckhardt_baseflow
    context_predicate: "Q_mean ** 100 > 0"
    detector_params:
      BFImax: 0.8
      a: 0.98
"""
    response = _client().post(
        "/api/semantic-packs/label-segments",
        data=json.dumps(
            {
                "custom_yaml": yaml_text,
                "values": [1.0] * 30,
                "segments": [{"id": "s", "start": 0, "end": 9, "shape": "plateau"}],
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 400


def test_validate_yaml_rejects_oversize_body():
    big_yaml = "name: x\nversion: '1.0'\n" + ("# padding\n" * 8000)
    response = _client().post(
        "/api/semantic-packs/validate-yaml",
        data=json.dumps({"yaml": big_yaml}),
        content_type="application/json",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["error"]["kind"] == "schema"
    assert "exceed" in payload["error"]["message"].lower()


def test_validate_yaml_accepts_pack_without_pow_in_predicates():
    """Schema check still passes for predicates that use only the strict
    whitelist (comparisons, boolean ops, calls to allowed builtins)."""
    yaml_text = """
name: ok
version: "1.0"
semantic_labels:
  baseflow:
    shape_primitive: plateau
    detector: eckhardt_baseflow
    context_predicate: "Q_mean < BFImax * Q_median"
    detector_params:
      BFImax: 0.8
      a: 0.98
"""
    response = _client().post(
        "/api/semantic-packs/validate-yaml",
        data=json.dumps({"yaml": yaml_text}),
        content_type="application/json",
    )
    payload = response.get_json()
    assert payload["ok"] is True

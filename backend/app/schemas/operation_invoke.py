"""Request/response DTOs for the op-invocation route (HTS-100).

Frozen dataclasses per CLAUDE.md "Frozen dataclasses for all DTOs". The
JSON Schema for the request payload lives at
``schemas/operation-invoke.schema.json`` (repo root) — keep both in sync.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


_ALLOWED_TIERS = frozenset({1, 2, 3})
_ALLOWED_COMPENSATION_MODES = frozenset({"naive", "local", "coupled"})


class InvokeRequestError(ValueError):
    """Raised when the request payload fails validation at the DTO layer."""


@dataclass(frozen=True)
class SegmentSpec:
    """One segment in the request payload's ``segments`` array.

    Attributes:
        id:    Segment identifier; matches ``segment_id`` for the target.
        start: Inclusive left bound (sample index in the full series).
        end:   Inclusive right bound.
        label: Shape primitive label (one of the 7-shape vocabulary).
    """

    id: str
    start: int
    end: int
    label: str

    @classmethod
    def from_dict(cls, raw: Any) -> "SegmentSpec":
        if not isinstance(raw, dict):
            raise InvokeRequestError(
                f"segment entry must be an object; got {type(raw).__name__}"
            )
        for key in ("id", "start", "end", "label"):
            if key not in raw:
                raise InvokeRequestError(f"segment entry missing required key {key!r}")
        try:
            start = int(raw["start"])
            end = int(raw["end"])
        except (TypeError, ValueError) as exc:
            raise InvokeRequestError(
                f"segment {raw.get('id', '<unknown>')!r}: start/end must be integers"
            ) from exc
        if end < start:
            raise InvokeRequestError(
                f"segment {raw['id']!r}: end ({end}) < start ({start})"
            )
        return cls(
            id=str(raw["id"]),
            start=start,
            end=end,
            label=str(raw["label"]),
        )


@dataclass(frozen=True)
class OperationInvokeRequest:
    """Validated request payload for ``POST /api/operations/invoke``."""

    series_id: str
    segment_id: str
    tier: int
    op_name: str
    params: dict[str, Any]
    domain_hint: str | None
    sample_values: list[float]
    segments: tuple[SegmentSpec, ...]
    compensation_mode: str | None
    target_class: int | None

    @classmethod
    def from_json(cls, payload: Any) -> "OperationInvokeRequest":
        if not isinstance(payload, dict):
            raise InvokeRequestError(
                f"request body must be a JSON object; got {type(payload).__name__}"
            )
        for key in ("series_id", "segment_id", "tier", "op_name",
                    "sample_values", "segments"):
            if key not in payload:
                raise InvokeRequestError(f"request missing required key {key!r}")

        try:
            tier = int(payload["tier"])
        except (TypeError, ValueError) as exc:
            raise InvokeRequestError(f"tier must be an integer; got {payload['tier']!r}") from exc
        if tier not in _ALLOWED_TIERS:
            raise InvokeRequestError(
                f"tier must be one of {sorted(_ALLOWED_TIERS)}; got {tier}"
            )

        sample_values = payload["sample_values"]
        if not isinstance(sample_values, list) or not all(
            isinstance(v, (int, float)) for v in sample_values
        ):
            raise InvokeRequestError("sample_values must be a list of numbers")

        segments_raw = payload["segments"]
        if not isinstance(segments_raw, list):
            raise InvokeRequestError("segments must be a list")
        segments = tuple(SegmentSpec.from_dict(s) for s in segments_raw)

        params = payload.get("params") or {}
        if not isinstance(params, dict):
            raise InvokeRequestError("params must be an object")

        compensation_mode = payload.get("compensation_mode")
        if compensation_mode is not None and compensation_mode not in _ALLOWED_COMPENSATION_MODES:
            raise InvokeRequestError(
                f"compensation_mode must be one of {sorted(_ALLOWED_COMPENSATION_MODES)} "
                f"or null; got {compensation_mode!r}"
            )

        target_class = payload.get("target_class")
        if target_class is not None:
            try:
                target_class = int(target_class)
            except (TypeError, ValueError) as exc:
                raise InvokeRequestError(
                    f"target_class must be int or null; got {payload['target_class']!r}"
                ) from exc

        return cls(
            series_id=str(payload["series_id"]),
            segment_id=str(payload["segment_id"]),
            tier=tier,
            op_name=str(payload["op_name"]),
            params=dict(params),
            domain_hint=str(payload["domain_hint"]) if payload.get("domain_hint") is not None else None,
            sample_values=[float(v) for v in sample_values],
            segments=segments,
            compensation_mode=compensation_mode,
            target_class=target_class,
        )

    def find_segment(self) -> SegmentSpec | None:
        for seg in self.segments:
            if seg.id == self.segment_id:
                return seg
        return None


@dataclass(frozen=True)
class OperationInvokeResponse:
    """Validated response payload for ``POST /api/operations/invoke``.

    All fields except ``op_name`` and ``edit_space`` may be ``None``
    depending on tier / op.
    """

    op_name: str
    tier: int
    edit_space: str
    values: list[float] | None
    constraint_residual: dict[str, Any] | None
    validation: dict[str, Any] | None
    label_chip: dict[str, Any] | None
    audit_id: int | None
    aggregate_result: dict[str, Any] | None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "op_name": self.op_name,
            "tier": self.tier,
            "edit_space": self.edit_space,
            "values": self.values,
            "constraint_residual": self.constraint_residual,
            "validation": self.validation,
            "label_chip": self.label_chip,
            "audit_id": self.audit_id,
            "aggregate_result": self.aggregate_result,
        }
        if self.extra:
            out["extra"] = self.extra
        return out

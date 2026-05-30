"""Schemas for the min-flip counterfactual probe (REWORK-07)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MinFlipConfig:
    """Tuning knobs for the closed-form L2-minimal-flip probe.

    Attributes:
        epsilon:           Tiny positive push past the decision boundary so
                           the flipped point is *strictly* on the new
                           half-space, not exactly on the boundary itself.
                           Smaller = closer to the true minimum-distance
                           counterfactual; large enough that the model's
                           argmax is well-defined at the new point.
        max_values:        Hard cap on input vector length, mirrors the
                           predict-values endpoint defense.
    """

    epsilon: float = 1e-3
    max_values: int = 65_536

    def __post_init__(self) -> None:
        if not (0 < self.epsilon < 1.0):
            raise ValueError(f"epsilon must be in (0, 1); got {self.epsilon}")
        if self.max_values < 1:
            raise ValueError(f"max_values must be ≥ 1; got {self.max_values}")


@dataclass(frozen=True)
class MinFlipResult:
    """Outcome of one min-flip probe.

    `found` is False when no class flip is reachable (e.g. all prototypes
    are equidistant or coincident — degenerate model). The remaining
    fields are populated only when `found` is True; the route serializes
    them as nulls otherwise so the UI can render a clean "no flip found"
    state without guessing.
    """

    found: bool
    artifact_id: str
    baseline_class: str | None
    flipped_class: str | None
    distance: float | None
    edit_values: tuple[float, ...]
    method: str
    reference: str
    reason: str | None = None

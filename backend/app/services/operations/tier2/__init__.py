from .plateau import (
    Tier2OpResult,
    invert,
    raise_lower,
    replace_with_cycle,
    replace_with_trend,
    tilt_detrend,
)
from .trend import (
    add_acceleration,
    change_slope,
    extrapolate,
    flatten,
    linearise,
    reverse_direction,
)

__all__ = [
    "add_acceleration",
    "change_slope",
    "extrapolate",
    "flatten",
    "invert",
    "linearise",
    "raise_lower",
    "replace_with_cycle",
    "replace_with_trend",
    "reverse_direction",
    "Tier2OpResult",
    "tilt_detrend",
]

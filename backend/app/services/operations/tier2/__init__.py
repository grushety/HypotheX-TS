from .plateau import (
    Tier2OpResult,
    invert,
    raise_lower,
    replace_with_cycle,
    replace_with_trend,
    tilt_detrend,
)
from .step import (
    convert_to_ramp,
    de_jump,
    duplicate,
    invert_sign,
    scale_magnitude,
    shift_in_time,
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
    "convert_to_ramp",
    "de_jump",
    "duplicate",
    "extrapolate",
    "flatten",
    "invert",
    "invert_sign",
    "linearise",
    "raise_lower",
    "replace_with_cycle",
    "replace_with_trend",
    "reverse_direction",
    "scale_magnitude",
    "shift_in_time",
    "Tier2OpResult",
    "tilt_detrend",
]

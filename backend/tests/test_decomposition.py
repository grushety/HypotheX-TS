"""Tests for DecompositionBlob, FITTER_REGISTRY, and dispatch_fitter (SEG-019)."""

from __future__ import annotations

import json
import numpy as np
import pytest

from app.models.decomposition import DecompositionBlob, _deserialize_value, _serialize_value
from app.services.decomposition.dispatcher import (
    FITTER_REGISTRY,
    dispatch_fitter,
    register_fitter,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALL_SHAPES = ["plateau", "trend", "step", "spike", "cycle", "transient", "noise"]
_DOMAIN_HINTS = [None, "hydrology", "seismo-geodesy", "remote-sensing", "other"]


def _make_blob(n: int = 40) -> DecompositionBlob:
    rng = np.random.default_rng(42)
    arr = rng.normal(size=n)
    trend = np.linspace(0, 1, n)
    residual = arr - trend
    return DecompositionBlob(
        method="ETM",
        components={"trend": trend, "residual": residual},
        coefficients={"slope": 1.0 / (n - 1), "intercept": 0.0},
        residual=residual,
        fit_metadata={"rmse": float(np.sqrt(np.mean(residual ** 2))), "rank": 2, "n_params": 2, "convergence": True, "version": "test-1.0"},
    )


# ---------------------------------------------------------------------------
# DecompositionBlob — reassemble
# ---------------------------------------------------------------------------


def test_reassemble_sums_components():
    n = 30
    trend = np.linspace(0, 1, n)
    seasonal = np.sin(np.linspace(0, 2 * np.pi, n))
    residual = np.random.default_rng(0).normal(scale=0.01, size=n)
    blob = DecompositionBlob(
        method="STL",
        components={"trend": trend, "seasonal": seasonal, "residual": residual},
        coefficients={},
        fit_metadata={},
    )
    recon = blob.reassemble()
    assert np.allclose(recon, trend + seasonal + residual)


def test_reassemble_single_component():
    arr = np.ones(10)
    blob = DecompositionBlob(method="Constant", components={"trend": arr}, coefficients={}, fit_metadata={})
    assert np.allclose(blob.reassemble(), arr)


def test_reassemble_raises_on_empty_components():
    blob = DecompositionBlob(method="Constant", components={}, coefficients={}, fit_metadata={})
    with pytest.raises(ValueError, match="no components"):
        blob.reassemble()


# ---------------------------------------------------------------------------
# DecompositionBlob — JSON round-trip
# ---------------------------------------------------------------------------


def test_json_roundtrip_preserves_arrays():
    blob = _make_blob(50)
    blob2 = DecompositionBlob.from_json(blob.to_json())
    for key in blob.components:
        assert np.allclose(blob.components[key], blob2.components[key], rtol=1e-12), key
    assert blob.method == blob2.method


def test_json_roundtrip_bit_identical():
    blob = _make_blob(20)
    d = blob.to_json()
    blob2 = DecompositionBlob.from_json(d)
    for key in blob.components:
        # base64 encoding is bit-identical
        assert np.array_equal(blob.components[key], blob2.components[key]), key


def test_json_roundtrip_residual_none():
    blob = DecompositionBlob(
        method="Constant",
        components={"trend": np.ones(10)},
        coefficients={"level": 1.0},
        residual=None,
        fit_metadata={"rmse": 0.0},
    )
    blob2 = DecompositionBlob.from_json(blob.to_json())
    assert blob2.residual is None


def test_json_roundtrip_residual_array():
    residual = np.array([0.1, -0.2, 0.05])
    blob = DecompositionBlob(
        method="ETM",
        components={"trend": np.array([1.0, 2.0, 3.0])},
        coefficients={},
        residual=residual,
        fit_metadata={},
    )
    blob2 = DecompositionBlob.from_json(blob.to_json())
    assert np.array_equal(blob2.residual, residual)


def test_json_serialisable():
    blob = _make_blob(10)
    d = blob.to_json()
    # Ensure the output is JSON-serialisable (no numpy scalars, etc.)
    json.dumps(d)


def test_json_roundtrip_coefficients_with_array():
    coeff_arr = np.array([1.0, 2.0, 3.0])
    blob = DecompositionBlob(
        method="ETM",
        components={"trend": np.ones(5)},
        coefficients={"weights": coeff_arr, "scale": 2.5},
        fit_metadata={},
    )
    blob2 = DecompositionBlob.from_json(blob.to_json())
    assert np.array_equal(blob2.coefficients["weights"], coeff_arr)
    assert blob2.coefficients["scale"] == 2.5


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def test_serialize_value_plain():
    assert _serialize_value(42) == 42
    assert _serialize_value("hello") == "hello"
    assert _serialize_value(None) is None


def test_serialize_value_ndarray():
    arr = np.array([1.0, 2.0, 3.0])
    d = _serialize_value(arr)
    assert d["__ndarray__"] is True
    assert d["dtype"] == "float64"
    assert d["shape"] == [3]
    arr2 = _deserialize_value(d)
    assert np.array_equal(arr, arr2)


def test_serialize_value_nested_dict():
    arr = np.ones(5)
    d = _serialize_value({"a": arr, "b": 1.0})
    assert d["b"] == 1.0
    assert d["a"]["__ndarray__"] is True


# ---------------------------------------------------------------------------
# FITTER_REGISTRY — registration
# ---------------------------------------------------------------------------


def test_register_fitter_adds_to_registry():
    # Use a unique name to avoid polluting the real registry
    _test_method = "__test_fitter_xyz__"

    @register_fitter(_test_method)
    def _dummy(X, **kw):
        pass

    assert _test_method in FITTER_REGISTRY
    assert FITTER_REGISTRY[_test_method] is _dummy
    # Cleanup
    del FITTER_REGISTRY[_test_method]


def test_register_fitter_preserves_function():
    _test_method = "__test_preserve__"

    @register_fitter(_test_method)
    def _my_fn(X, **kw):
        return "ok"

    assert FITTER_REGISTRY[_test_method](None) == "ok"
    del FITTER_REGISTRY[_test_method]


# ---------------------------------------------------------------------------
# dispatch_fitter — all 7 shapes × domain hints
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("shape", _ALL_SHAPES)
def test_dispatch_all_shapes_no_hint(shape):
    fn = dispatch_fitter(shape, domain_hint=None)
    assert callable(fn)


@pytest.mark.parametrize("shape", _ALL_SHAPES)
@pytest.mark.parametrize("hint", _DOMAIN_HINTS)
def test_dispatch_all_shapes_all_hints(shape, hint):
    fn = dispatch_fitter(shape, domain_hint=hint)
    assert callable(fn)


def test_dispatch_remote_sensing_trend_gives_landtrendr():
    fn = dispatch_fitter("trend", domain_hint="remote-sensing")
    # LandTrendr is registered for this combination
    from app.services.decomposition.fitters import landtrendr  # noqa: F401
    assert fn is FITTER_REGISTRY["LandTrendr"]


def test_dispatch_seismo_transient_gives_gratsid():
    fn = dispatch_fitter("transient", domain_hint="seismo-geodesy")
    from app.services.decomposition.fitters import gratsid  # noqa: F401
    assert fn is FITTER_REGISTRY["GrAtSiD"]


def test_dispatch_multi_period_cycle_gives_mstl():
    fn = dispatch_fitter("cycle", domain_hint="multi-period")
    from app.services.decomposition.fitters import mstl  # noqa: F401
    assert fn is FITTER_REGISTRY["MSTL"]


def test_dispatch_unknown_hint_falls_back_to_none():
    fn_default = dispatch_fitter("trend", domain_hint=None)
    fn_unknown = dispatch_fitter("trend", domain_hint="hydrology")
    assert fn_default is fn_unknown


def test_dispatch_unknown_shape_raises_key_error():
    with pytest.raises(KeyError, match="Unknown shape label"):
        dispatch_fitter("unknown_shape")


def test_dispatch_unknown_shape_message_contains_known():
    with pytest.raises(KeyError) as exc_info:
        dispatch_fitter("bogus")
    msg = str(exc_info.value)
    assert "plateau" in msg or "trend" in msg


# ---------------------------------------------------------------------------
# End-to-end: dispatch → fitter produces a valid DecompositionBlob
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("shape", _ALL_SHAPES)
def test_dispatch_fitter_produces_valid_blob(shape):
    rng = np.random.default_rng(123)
    X = rng.normal(size=40)
    fn = dispatch_fitter(shape)
    blob = fn(X)
    assert isinstance(blob, DecompositionBlob)
    assert blob.method  # non-empty
    assert blob.components  # at least one component
    # All component arrays must have shape (40,)
    for name, arr in blob.components.items():
        assert arr.shape == (40,), f"component {name} has wrong shape"


@pytest.mark.parametrize("shape", _ALL_SHAPES)
def test_dispatch_fitter_blob_reassembles(shape):
    X = np.linspace(0, 1, 50) + 0.01 * np.random.default_rng(0).normal(size=50)
    fn = dispatch_fitter(shape)
    blob = fn(X)
    recon = blob.reassemble()
    # Reconstruction must equal X within float tolerance
    assert np.allclose(recon, X, rtol=1e-6, atol=1e-6), (
        f"reassemble() diverges for {blob.method}: max_err={float(np.max(np.abs(recon - X))):.2e}"
    )


@pytest.mark.parametrize("shape", _ALL_SHAPES)
def test_dispatch_fitter_blob_json_roundtrip(shape):
    X = np.random.default_rng(7).normal(size=30)
    fn = dispatch_fitter(shape)
    blob = fn(X)
    blob2 = DecompositionBlob.from_json(blob.to_json())
    for key in blob.components:
        assert np.allclose(blob.components[key], blob2.components[key], rtol=1e-12)

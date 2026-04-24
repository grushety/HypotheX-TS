"""Synthetic shape fixtures for SEG-008 classification tests.

Generates >= 30 labelled examples per shape class with known parameters.
Each shape matches the 7-primitive vocabulary: plateau, trend, step, spike,
cycle, transient, noise.
"""

from __future__ import annotations

import random
from typing import NamedTuple

import numpy as np


class ShapeExample(NamedTuple):
    label: str
    values: np.ndarray
    ctx_pre: np.ndarray
    ctx_post: np.ndarray


def generate_plateau(n: int = 32, rng: np.random.Generator | None = None) -> ShapeExample:
    rng = rng or np.random.default_rng()
    level = float(rng.uniform(-2.0, 2.0))
    noise_scale = float(rng.uniform(0.001, 0.008))
    values = np.full(n, level) + rng.normal(0, noise_scale, n)
    ctx = np.full(12, level) + rng.normal(0, noise_scale, 12)
    return ShapeExample("plateau", values, ctx[:6], ctx[6:])


def generate_trend(n: int = 32, rng: np.random.Generator | None = None) -> ShapeExample:
    rng = rng or np.random.default_rng()
    slope = float(rng.choice([-1, 1])) * float(rng.uniform(0.15, 0.5))
    start = float(rng.uniform(-1.0, 1.0))
    xs = np.arange(n, dtype=float) / (n - 1)
    values = start + slope * xs + rng.normal(0, 0.005, n)
    ctx_pre = np.linspace(start - slope * 0.3, start, 6) + rng.normal(0, 0.005, 6)
    ctx_post = np.linspace(start + slope, start + slope * 1.3, 6) + rng.normal(0, 0.005, 6)
    return ShapeExample("trend", values, ctx_pre, ctx_post)


def generate_step(n: int = 32, rng: np.random.Generator | None = None) -> ShapeExample:
    rng = rng or np.random.default_rng()
    level_before = float(rng.uniform(-1.0, 0.0))
    step_size = float(rng.uniform(0.8, 2.0)) * float(rng.choice([-1, 1]))
    level_after = level_before + step_size
    transition_at = n // 2
    values = np.concatenate([
        np.full(transition_at, level_before) + rng.normal(0, 0.01, transition_at),
        np.full(n - transition_at, level_after) + rng.normal(0, 0.01, n - transition_at),
    ])
    ctx_pre = np.full(8, level_before) + rng.normal(0, 0.01, 8)
    ctx_post = np.full(8, level_after) + rng.normal(0, 0.01, 8)
    return ShapeExample("step", values, ctx_pre, ctx_post)


def generate_spike(rng: np.random.Generator | None = None) -> ShapeExample:
    rng = rng or np.random.default_rng()
    n = int(rng.integers(6, 16))
    baseline = float(rng.uniform(-0.5, 0.5))
    peak_height = float(rng.uniform(3.0, 6.0)) * float(rng.choice([-1, 1]))
    peak_idx = n // 2
    values = np.full(n, baseline, dtype=float) + rng.normal(0, 0.02, n)
    values[peak_idx] = baseline + peak_height
    ctx = np.full(10, baseline) + rng.normal(0, 0.02, 10)
    return ShapeExample("spike", values, ctx[:5], ctx[5:])


def generate_cycle(rng: np.random.Generator | None = None) -> ShapeExample:
    rng = rng or np.random.default_rng()
    period = int(rng.integers(6, 14))
    n_periods = int(rng.integers(2, 5))
    n = period * n_periods
    amplitude = float(rng.uniform(0.5, 1.5))
    phase = float(rng.uniform(0, 2 * np.pi))
    xs = np.arange(n, dtype=float)
    values = amplitude * np.sin(2 * np.pi * xs / period + phase) + rng.normal(0, 0.02, n)
    ctx = amplitude * np.sin(2 * np.pi * np.arange(-8, 0, dtype=float) / period + phase)
    ctx_post = amplitude * np.sin(2 * np.pi * np.arange(n, n + 8, dtype=float) / period + phase)
    return ShapeExample("cycle", values, ctx, ctx_post)


def generate_transient(n: int = 32, rng: np.random.Generator | None = None) -> ShapeExample:
    rng = rng or np.random.default_rng()
    baseline = float(rng.uniform(-0.5, 0.5))
    height = float(rng.uniform(1.0, 3.0))
    rise_end = n // 3
    fall_start = rise_end
    xs = np.arange(n, dtype=float)
    bump = np.where(
        xs < rise_end,
        height * xs / max(1, rise_end),
        height * np.exp(-(xs - fall_start) / max(1, n - fall_start) * 3),
    )
    values = baseline + bump + rng.normal(0, 0.02, n)
    ctx = np.full(8, baseline) + rng.normal(0, 0.02, 8)
    return ShapeExample("transient", values, ctx[:4], ctx[4:])


def generate_noise(n: int = 32, rng: np.random.Generator | None = None) -> ShapeExample:
    rng = rng or np.random.default_rng()
    values = rng.normal(0, float(rng.uniform(0.3, 1.0)), n)
    ctx = rng.normal(0, 0.5, 12)
    return ShapeExample("noise", values, ctx[:6], ctx[6:])


_GENERATORS = {
    "plateau":   generate_plateau,
    "trend":     generate_trend,
    "step":      generate_step,
    "spike":     generate_spike,
    "cycle":     generate_cycle,
    "transient": generate_transient,
    "noise":     generate_noise,
}


def generate_all(n_per_class: int = 50, seed: int = 42) -> list[ShapeExample]:
    """Generate n_per_class examples for each of the 7 shape primitives."""
    examples: list[ShapeExample] = []
    for label, gen_fn in _GENERATORS.items():
        for i in range(n_per_class):
            rng = np.random.default_rng(seed + i * 7 + hash(label) % 1000)
            examples.append(gen_fn(rng=rng))
    return examples

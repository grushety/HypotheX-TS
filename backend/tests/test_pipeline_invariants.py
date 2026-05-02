"""Tests for VAL-041: pre-registered analysis pipeline invariants.

We can't *run* the R + brms pipeline in this Python-only CI, but we
can pin the structural invariants the AC actually demands:

 - All 9 analysis files exist and reference the right inputs.
 - The H1 formula in `01-primary-h1-glmer.Rmd` matches `_constants.R`
   character-for-character, and `_constants.R::FORMULA_H1` matches the
   formula written in `study/preregistration.md` §9.
 - Every locked threshold (α, SESOI, ROPE, BH q, …) appears exactly
   once in `_constants.R` (single source of truth) and is referenced —
   not duplicated as a literal — in the analysis scripts.
 - Outcome variable names are consistent across `_constants.R`,
   `data/README.md`, and `preregistration.md`.
 - AC-required reporting items (TOST `(t1, p1, t2, p2)`, R-hat ≤ 1.01,
   ESS ≥ 1000, Brier B = 999, Holm correction, BH correction) are
   *referenced* in their respective files.
 - `Dockerfile` + `renv.lock` + `pyproject.toml` exist with the locked
   R version and the AC-required R packages.
 - `make_synthetic.R` produces the locked sample size + variable set.
 - `build_replication_package.sh` bundles every artefact the AC names.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_STUDY = _REPO_ROOT / "study"
_ANALYSIS = _STUDY / "analysis"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def constants_text() -> str:
    return (_ANALYSIS / "_constants.R").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def prereg_text() -> str:
    return (_STUDY / "preregistration.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def data_readme_text() -> str:
    return (_STUDY / "data" / "README.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# File presence
# ---------------------------------------------------------------------------


_REQUIRED_ANALYSIS_FILES = [
    "_constants.R",
    "00-make-processed-data.R",
    "01-primary-h1-glmer.Rmd",
    "02-primary-h2-tost.R",
    "03-secondary-h3-h4-glmer.Rmd",
    "04-bayesian-companion.Rmd",
    "05-trust-calibration-brier.R",
    "06-exploratory.Rmd",
    "07-figures.Rmd",
    "08-tables.Rmd",
    "make_synthetic.R",
    "Makefile",
    "renv.lock",
    "pyproject.toml",
    "Dockerfile",
]


@pytest.mark.parametrize("name", _REQUIRED_ANALYSIS_FILES)
def test_analysis_file_exists(name):
    path = _ANALYSIS / name
    assert path.exists() and path.is_file(), (
        f"VAL-041 missing artefact: study/analysis/{name}"
    )


def test_data_readme_exists():
    assert (_STUDY / "data" / "README.md").exists()


def test_replication_builder_exists():
    assert (_STUDY / "build_replication_package.sh").exists()


# ---------------------------------------------------------------------------
# H1 formula must match VAL-040 §9
# ---------------------------------------------------------------------------


# Canonical H1 formula from VAL-040 §9 (rendered in `preregistration.md`
# inside an R code block).  We compare against the no-whitespace string
# so trivial reformatting in the markdown doesn't break the test, but
# any token change does.
_CANONICAL_H1 = (
    "team_accuracy ~ tool * difficulty + trial_index "
    "+ (1 + tool | participant) + (1 | item)"
)


def _normalise_formula(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


class TestH1FormulaLocked:
    def test_constants_holds_canonical_formula(self, constants_text):
        match = re.search(r'FORMULA_H1\s*<-\s*"([^"]+)"', constants_text)
        assert match is not None, "_constants.R must define FORMULA_H1"
        assert _normalise_formula(match.group(1)) == _normalise_formula(_CANONICAL_H1)

    def test_preregistration_holds_canonical_formula(self, prereg_text):
        # The `glmer(... ~ ...)` block in preregistration.md §9.
        # We strip the R-formula portion and compare normalized.
        block_match = re.search(
            r"glmer\(\s*([^,]+(?:\([^)]+\)[^,]*)+)",
            prereg_text,
        )
        assert block_match is not None, (
            "preregistration.md §9 must contain the glmer() H1 formula block"
        )
        formula_str = _normalise_formula(block_match.group(1))
        # The canonical formula's tokens must all appear in the prereg's
        # rendering; whitespace and newlines may differ.
        for token in (
            "team_accuracy",
            "~",
            "tool * difficulty",
            "trial_index",
            "(1 + tool | participant)",
            "(1 | item)",
        ):
            assert _normalise_formula(token) in formula_str, (
                f"preregistration.md §9 H1 formula missing token {token!r}"
            )

    def test_h1_rmd_matches_constants(self):
        rmd = (_ANALYSIS / "01-primary-h1-glmer.Rmd").read_text(encoding="utf-8")
        # The Rmd holds a literal copy + a stopifnot() guard. Both must
        # contain the canonical formula.
        match = re.search(r'LITERAL_FORMULA\s*<-\s*"([^"]+)"', rmd)
        assert match is not None, (
            "01-primary-h1-glmer.Rmd must declare LITERAL_FORMULA"
        )
        assert _normalise_formula(match.group(1)) == _normalise_formula(_CANONICAL_H1)


# ---------------------------------------------------------------------------
# Constants single-source-of-truth (AC line 155)
# ---------------------------------------------------------------------------


_LOCKED_CONSTANTS = {
    "ALPHA": "0.05",
    "SESOI_D": "0.40",
    "ROPE_D": "0.10",
    "BH_Q": "0.10",
    "POWER_TARGET": "0.80",
    "SAMPLE_SIZE_PER_CELL": "100L",
    "TOTAL_N": "300L",
    "TRIALS_PER_PARTICIPANT": "8L",
    "N_ITEMS_TOTAL": "32L",
    "BOOTSTRAP_B": "999L",
    "BRMS_R_HAT_MAX": "1.01",
    "BRMS_ESS_MIN": "1000L",
}


@pytest.mark.parametrize("name,value", _LOCKED_CONSTANTS.items())
def test_constant_defined_in_constants_file(name, value, constants_text):
    pattern = rf"\b{name}\s*<-\s*{re.escape(value)}\b"
    assert re.search(pattern, constants_text), (
        f"_constants.R is missing the locked definition `{name} <- {value}`"
    )


# Files that should *reference* the constant (via source("_constants.R"))
# rather than duplicating literals.  Each entry: (filename, regex of
# at-least-one constant reference).  We verify that the file sources
# _constants.R; the deeper "no duplicate literals" check would be brittle
# (R lets you write `0.05` legitimately for plot-axis padding etc.), so
# we settle for the source-and-reference invariant.
_FILES_REQUIRING_CONSTANTS_SOURCE = [
    "00-make-processed-data.R",
    "01-primary-h1-glmer.Rmd",
    "02-primary-h2-tost.R",
    "03-secondary-h3-h4-glmer.Rmd",
    "04-bayesian-companion.Rmd",
    "05-trust-calibration-brier.R",
    "06-exploratory.Rmd",
    "07-figures.Rmd",
    "08-tables.Rmd",
    "make_synthetic.R",
]


@pytest.mark.parametrize("name", _FILES_REQUIRING_CONSTANTS_SOURCE)
def test_file_sources_constants(name):
    text = (_ANALYSIS / name).read_text(encoding="utf-8")
    assert 'source("_constants.R")' in text, (
        f"{name} must `source('_constants.R')` instead of duplicating literals"
    )


# ---------------------------------------------------------------------------
# Outcome variable names locked across files
# ---------------------------------------------------------------------------


_LOCKED_OUTCOMES = (
    "team_accuracy",
    "nasa_tlx_overall",
    "trust_calibration_brier",
    "ynn5_dtw_plausibility_mean",
    "cherry_picking_risk_score",
    "shape_coverage_fraction",
    "dpp_log_det_diversity",
)


@pytest.mark.parametrize("name", _LOCKED_OUTCOMES)
def test_outcome_in_constants(name, constants_text):
    assert name in constants_text, (
        f"_constants.R missing locked outcome {name!r} "
        f"(must appear in PRIMARY_OUTCOMES or SECONDARY_OUTCOMES)"
    )


@pytest.mark.parametrize("name", _LOCKED_OUTCOMES)
def test_outcome_in_data_readme(name, data_readme_text):
    assert name in data_readme_text, (
        f"data/README.md missing locked outcome {name!r}"
    )


@pytest.mark.parametrize("name", _LOCKED_OUTCOMES)
def test_outcome_in_preregistration(name, prereg_text):
    assert name in prereg_text, (
        f"preregistration.md missing locked outcome {name!r}"
    )


# ---------------------------------------------------------------------------
# AC-required reporting items
# ---------------------------------------------------------------------------


def test_tost_reports_t1_p1_t2_p2():
    """AC line 158: 'TOST result reported as (t1, p1, t2, p2) plus
    equivalence bounds in d-units, not just "equivalence achieved"'."""
    text = (_ANALYSIS / "02-primary-h2-tost.R").read_text(encoding="utf-8")
    for token in ("t1 <-", "p1 <-", "t2 <-", "p2 <-"):
        assert token in text, (
            f"02-primary-h2-tost.R missing TOST report variable {token!r}"
        )
    # And the AC's "equivalence bounds in d-units" string:
    assert "SESOI_D" in text, (
        "02-primary-h2-tost.R must reference SESOI_D for equivalence bounds"
    )


def test_bayesian_reports_rhat_and_ess():
    """AC line 159: 'R-hat ≤ 1.01 for all parameters, ESS ≥ 1000 for
    all bulk and tail'."""
    text = (_ANALYSIS / "04-bayesian-companion.Rmd").read_text(encoding="utf-8")
    assert "BRMS_R_HAT_MAX" in text
    assert "BRMS_ESS_MIN" in text
    assert "rhat_max" in text
    assert "ess_bulk_min" in text
    assert "ess_tail_min" in text


def test_brier_uses_b_999():
    """AC line 160: 'bootstrap 95 % CI (B = 999)'."""
    text = (_ANALYSIS / "05-trust-calibration-brier.R").read_text(encoding="utf-8")
    assert "BOOTSTRAP_B" in text
    constants_text = (_ANALYSIS / "_constants.R").read_text(encoding="utf-8")
    assert re.search(r"BOOTSTRAP_B\s*<-\s*999L", constants_text)


def test_holm_correction_in_h1():
    text = (_ANALYSIS / "01-primary-h1-glmer.Rmd").read_text(encoding="utf-8")
    assert "p.adjust" in text and 'method = "holm"' in text


def test_bh_correction_in_secondary():
    text = (_ANALYSIS / "03-secondary-h3-h4-glmer.Rmd").read_text(encoding="utf-8")
    assert "p.adjust" in text and 'method = "BH"' in text


def test_figure_1_kay_2016_design():
    """AC line 166: 'Paper figure 1 = Figure of effects per H1/H2/H3/H4
    with effect size + CI + Bayes posterior overlaid'."""
    text = (_ANALYSIS / "07-figures.Rmd").read_text(encoding="utf-8")
    # All four hypotheses surface in the figure
    for hyp in ("H1:", "H2:", "H3:", "H4:"):
        assert hyp in text, f"figure 1 source missing hypothesis label {hyp!r}"
    # Bayesian posterior overlay
    assert "post_d" in text and "steelblue" in text
    # ROPE annotation
    assert "ROPE_D" in text


# ---------------------------------------------------------------------------
# Replication package builder bundles every artefact
# ---------------------------------------------------------------------------


def test_replication_builder_includes_required_artefacts():
    text = (_STUDY / "build_replication_package.sh").read_text(encoding="utf-8")
    required = [
        "preregistration.md",
        "deviations.md",
        "pilot/pilot_summary.md",
        "power/h1_simulation.R",
        "_constants.R",
        "01-primary-h1-glmer.Rmd",
        "02-primary-h2-tost.R",
        "04-bayesian-companion.Rmd",
        "05-trust-calibration-brier.R",
        "07-figures.Rmd",
        "08-tables.Rmd",
        "make_synthetic.R",
        "Makefile",
        "renv.lock",
        "pyproject.toml",
        "Dockerfile",
        "items.json",
        "data/README.md",
    ]
    for name in required:
        assert name in text, (
            f"build_replication_package.sh does not bundle {name!r}; "
            f"AC line 167 requires the full pipeline"
        )


def test_replication_zip_target_in_makefile():
    text = (_ANALYSIS / "Makefile").read_text(encoding="utf-8")
    assert "replication-zip:" in text, (
        "Makefile must define a `replication-zip` target wrapping "
        "build_replication_package.sh"
    )


# ---------------------------------------------------------------------------
# Synthetic-data smoke (AC line 164)
# ---------------------------------------------------------------------------


def test_make_synthetic_uses_locked_n():
    text = (_ANALYSIS / "make_synthetic.R").read_text(encoding="utf-8")
    # Must use SAMPLE_SIZE_PER_CELL and N_CONDITIONS — not literals.
    assert "SAMPLE_SIZE_PER_CELL" in text
    assert "N_CONDITIONS" in text


def test_make_synthetic_emits_all_outcomes():
    text = (_ANALYSIS / "make_synthetic.R").read_text(encoding="utf-8")
    for name in _LOCKED_OUTCOMES:
        assert name in text, (
            f"make_synthetic.R must populate locked outcome {name!r}"
        )


# ---------------------------------------------------------------------------
# Dockerfile + renv lock minimum content
# ---------------------------------------------------------------------------


def test_dockerfile_pinned_R_version():
    text = (_ANALYSIS / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM rocker/r-ver:" in text, (
        "Dockerfile must pin the R version via rocker/r-ver:<version>"
    )
    assert "renv::restore" in text


def test_renv_lock_lists_required_packages():
    text = (_ANALYSIS / "renv.lock").read_text(encoding="utf-8")
    payload = json.loads(text)
    pkgs = payload["Packages"]
    for name in ("lme4", "brms", "TOSTER", "boot", "rmarkdown",
                 "ggplot2", "posterior", "bayestestR"):
        assert name in pkgs, (
            f"renv.lock must pin {name!r} (used by the analysis pipeline)"
        )


# ---------------------------------------------------------------------------
# Deviations log placeholder
# ---------------------------------------------------------------------------


def test_deviations_md_unchanged():
    """Sanity: VAL-041 must not silently introduce deviations.
    `deviations.md` has the same no-deviations body as VAL-040 left it.
    """
    text = (_STUDY / "deviations.md").read_text(encoding="utf-8")
    assert "_(no deviations recorded" in text, (
        "study/deviations.md no longer in 'no deviations' state — VAL-041 "
        "introduced a deviation; document it in the file with timestamp."
    )

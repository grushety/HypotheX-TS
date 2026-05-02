"""Tests for VAL-040: pre-registered user-study spec.

A documentation ticket — these tests pin the AC-required invariants
that the registered protocol does not silently drift:

 - All referenced files in `study/` exist
 - `materials/items.json` schema is well-formed: 32 items, 8 per
   domain, 4 domains, locked shape vocabulary
 - Outcome-variable names in `preregistration.md` and `README.md`
   are consistent with each other and with the locked list (the
   contract VAL-041 reads from)
 - All locked numeric constants from AC line 121 appear in
   `preregistration.md`
 - `deviations.md` exists and is initially empty (no entries)
 - The R power-simulation script declares the locked seed
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_STUDY = _REPO_ROOT / "study"


# ---------------------------------------------------------------------------
# File presence
# ---------------------------------------------------------------------------


class TestFilesExist:
    """AC: every artefact listed in the study layout exists."""

    @pytest.mark.parametrize("relpath", [
        "preregistration.md",
        "README.md",
        "deviations.md",
        "power/h1_simulation.R",
        "materials/items.json",
        "protocol/instructions_hypothex_tips.md",
        "protocol/instructions_hypothex_no_tips.md",
        "protocol/instructions_native_guide.md",
        "pilot/pilot_summary.md",
    ])
    def test_artefact_exists(self, relpath):
        path = _STUDY / relpath
        assert path.exists(), f"missing artefact: study/{relpath}"
        assert path.is_file(), f"expected file: study/{relpath}"


# ---------------------------------------------------------------------------
# items.json schema
# ---------------------------------------------------------------------------


class TestItemsSchema:
    @pytest.fixture
    def items(self):
        path = _STUDY / "materials" / "items.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_top_level_keys(self, items):
        for key in ("version", "n_items", "n_domains", "items_per_domain",
                    "shape_vocabulary", "items"):
            assert key in items, f"items.json missing top-level key {key!r}"

    def test_locked_counts(self, items):
        # AC: 32 items, 8 per domain, 4 domains, 7-shape vocabulary
        assert items["n_items"] == 32
        assert items["n_domains"] == 4
        assert items["items_per_domain"] == 8
        assert len(items["items"]) == 32
        assert len(items["shape_vocabulary"]) == 7

    def test_shape_vocabulary_matches_canon(self, items):
        canon = ["plateau", "trend", "step", "spike", "cycle", "transient", "noise"]
        assert items["shape_vocabulary"] == canon

    def test_each_item_has_required_fields(self, items):
        required = {
            "item_id", "domain", "difficulty",
            "ground_truth_label", "locked_cf_label",
            "series_path", "pilot_accuracy",
            "shape_primitives_present",
        }
        for entry in items["items"]:
            missing = required - entry.keys()
            assert not missing, (
                f"items.json item {entry.get('item_id', '<unknown>')} missing "
                f"required fields {sorted(missing)}"
            )

    def test_difficulty_values_locked(self, items):
        for entry in items["items"]:
            assert entry["difficulty"] in ("easy", "hard"), (
                f"items.json {entry['item_id']} has unknown difficulty "
                f"{entry['difficulty']!r}"
            )

    def test_each_domain_has_4_easy_4_hard(self, items):
        from collections import Counter
        for domain in {entry["domain"] for entry in items["items"]}:
            domain_items = [e for e in items["items"] if e["domain"] == domain]
            counts = Counter(e["difficulty"] for e in domain_items)
            assert counts["easy"] == 4 and counts["hard"] == 4, (
                f"domain {domain!r} item-difficulty counts {dict(counts)} "
                f"do not match the locked 4-easy / 4-hard split"
            )

    def test_item_ids_unique(self, items):
        ids = [e["item_id"] for e in items["items"]]
        assert len(ids) == len(set(ids)), "items.json has duplicate item_ids"

    def test_shape_primitives_subset_of_vocabulary(self, items):
        vocab = set(items["shape_vocabulary"])
        for entry in items["items"]:
            assert set(entry["shape_primitives_present"]) <= vocab, (
                f"items.json {entry['item_id']} references shape primitives "
                f"outside the vocabulary"
            )


# ---------------------------------------------------------------------------
# Outcome-variable name contract
# ---------------------------------------------------------------------------


_LOCKED_OUTCOME_NAMES = (
    # Primary
    "team_accuracy",
    "nasa_tlx_overall",
    "trust_calibration_brier",
    # Secondary
    "ynn5_dtw_plausibility_mean",
    "cherry_picking_risk_score",
    "shape_coverage_fraction",
    "dpp_log_det_diversity",
)


class TestOutcomeVariableContract:
    """AC: 'All primary and secondary outcome variable names match exactly
    the variable names that VAL-041 will use'.

    The names appear in two places — preregistration.md §7/§8 and
    README.md's contract section. Both files must contain every name.
    """

    @pytest.fixture
    def prereg_text(self):
        return (_STUDY / "preregistration.md").read_text(encoding="utf-8")

    @pytest.fixture
    def readme_text(self):
        return (_STUDY / "README.md").read_text(encoding="utf-8")

    @pytest.mark.parametrize("name", _LOCKED_OUTCOME_NAMES)
    def test_outcome_in_preregistration(self, name, prereg_text):
        assert name in prereg_text, (
            f"locked outcome variable {name!r} missing from preregistration.md"
        )

    @pytest.mark.parametrize("name", _LOCKED_OUTCOME_NAMES)
    def test_outcome_in_readme(self, name, readme_text):
        assert name in readme_text, (
            f"locked outcome variable {name!r} missing from README.md "
            f"(VAL-041 contract section)"
        )


# ---------------------------------------------------------------------------
# Locked numeric constants (AC line 121)
# ---------------------------------------------------------------------------


class TestNumericConstants:
    """AC: 'All threshold values […] are stated as numeric constants in
    the markdown — no "appropriate value" hand-waving'."""

    @pytest.fixture
    def prereg_text(self):
        return (_STUDY / "preregistration.md").read_text(encoding="utf-8")

    @pytest.mark.parametrize("token", [
        "0.05",                  # α
        "0.40 d",                # SESOI
        "0.1 d",                 # ROPE
        "0.10",                  # BH q
        "0.80",                  # power target
        "100",                   # per-cell N
        "300",                   # total N
        "90 days",               # stop-after
        "N = 150",               # mid-study audit
        "1.5",                   # IQR multiplier
        "32",                    # number of items
        "8",                     # items per domain / trials per participant
        "£15/hour",              # compensation
    ])
    def test_constant_present(self, token, prereg_text):
        assert token in prereg_text, (
            f"locked constant {token!r} missing from preregistration.md — "
            f"AC line 121 forbids hand-waving."
        )

    def test_no_tbd_other_than_irb(self, prereg_text):
        """AC: 'all numbers locked (not "TBD" except IRB # which depends
        on institution timing)'."""
        # Allow "TBD-IRB-2026-NN" placeholder for the IRB number; everything
        # else marked TBD is a pre-registration violation.
        non_irb_tbd = re.findall(r"TBD(?!-IRB)", prereg_text)
        assert non_irb_tbd == [], (
            f"preregistration.md contains non-IRB TBD placeholders: {non_irb_tbd}"
        )


# ---------------------------------------------------------------------------
# deviations.md initial state
# ---------------------------------------------------------------------------


class TestDeviationsLog:
    def test_no_deviations_at_registration_time(self):
        text = (_STUDY / "deviations.md").read_text(encoding="utf-8")
        # Must have a "Deviations" heading and contain the no-deviations
        # marker — append-only, but at v1.0 no entries exist yet.
        assert "## Deviations" in text
        # No Markdown ## sub-section headings *under* Deviations
        # (each deviation would be a `### <timestamp>` entry per the
        # AC's "timestamp + reason + consequence" format).
        sub_entries = re.findall(r"^### ", text, re.MULTILINE)
        assert sub_entries == [], (
            f"deviations.md has {len(sub_entries)} entries already; "
            f"expected empty at v1.0 registration time."
        )


# ---------------------------------------------------------------------------
# h1_simulation.R seeded
# ---------------------------------------------------------------------------


class TestPowerSimulation:
    @pytest.fixture
    def script_text(self):
        return (_STUDY / "power" / "h1_simulation.R").read_text(encoding="utf-8")

    def test_seed_declared(self, script_text):
        assert "set.seed(" in script_text, (
            "h1_simulation.R must declare a deterministic seed."
        )

    def test_locked_seed_value(self, script_text):
        # The seed itself is locked at registration time; document the
        # locked value here so a code change to it is a registered
        # deviation. The expected value matches what's in the R script.
        match = re.search(r"set\.seed\((\d+)\)", script_text)
        assert match is not None
        seed = int(match.group(1))
        assert seed == 20260502, (
            f"h1_simulation.R seed {seed} differs from the registered "
            f"value 20260502 — this is a deviation."
        )

    def test_locked_design_constants(self, script_text):
        for token in ("n_per_cell <- if", "n_conditions  <- 3L",
                      "n_items_total <- 32L", "n_trials_per  <- 8L"):
            assert token in script_text, (
                f"h1_simulation.R missing locked design constant: {token!r}"
            )

    def test_pilot_variance_components_locked(self, script_text):
        # Pilot summary records σ²_p = 0.85, σ²_i = 0.43; the R script
        # must encode the same numbers verbatim.
        assert "sigma2_participant <- 0.85" in script_text
        assert "sigma2_item        <- 0.43" in script_text


# ---------------------------------------------------------------------------
# Cross-file consistency
# ---------------------------------------------------------------------------


class TestCrossFileConsistency:
    """README.md mirrors the constants table from preregistration.md.
    Both files must agree on the locked thresholds."""

    @pytest.fixture
    def prereg(self):
        return (_STUDY / "preregistration.md").read_text(encoding="utf-8")

    @pytest.fixture
    def readme(self):
        return (_STUDY / "README.md").read_text(encoding="utf-8")

    @pytest.mark.parametrize("token", [
        "0.05",
        "0.10",
        "0.80",
        "100",
        "300",
        "1.5",
        "32",
    ])
    def test_constant_in_both(self, token, prereg, readme):
        assert token in prereg
        assert token in readme

    def test_pilot_summary_referenced(self, prereg):
        assert "pilot/pilot_summary.md" in prereg or "pilot_summary" in prereg

    def test_h1_simulation_referenced(self, prereg):
        assert "power/h1_simulation.R" in prereg or "h1_simulation" in prereg

#' Single source of truth for all pre-registered constants (VAL-041).
#'
#' Every threshold, formula, and seed used by the analysis pipeline lives
#' in this file. Renaming or modifying any value here is a registered
#' deviation per `study/preregistration.md` §13. The Python invariant tests
#' (`backend/tests/test_pipeline_invariants.py`) cross-check this file
#' against `study/preregistration.md` so a silent edit fails CI.
#'
#' If you find yourself wanting to write a literal threshold value in any
#' analysis file: STOP. Source this file with `source("_constants.R")`
#' and reference the named constant. The AC binds analysis correctness
#' to the pre-registered values — duplicating literals across files
#' invites drift between this file and the analysis pipeline.

# Reproducibility ---------------------------------------------------------
# Locked seed for every R script in study/analysis/. Same seed as VAL-040
# `power/h1_simulation.R` uses; intentional, so power simulation and main
# analysis share an RNG history under the same registered protocol.
SEED <- 42L

# Hypothesis-testing thresholds -------------------------------------------
ALPHA <- 0.05                    # NHST significance
SESOI_D <- 0.40                  # H2 TOST equivalence bound (Cohen's d)
ROPE_D <- 0.10                   # Bayesian companion ROPE half-width (d)
BH_Q <- 0.10                     # Benjamini-Hochberg q-value (secondary family)
HOLM_FAMILY <- c("h1", "h3", "h4")  # primary directional family for Holm correction

# Power justification (matches VAL-040 §4) --------------------------------
POWER_TARGET <- 0.80
DETECTABLE_D <- 0.40
SAMPLE_SIZE_PER_CELL <- 100L
TOTAL_N <- 300L
N_CONDITIONS <- 3L
TRIALS_PER_PARTICIPANT <- 8L
N_ITEMS_TOTAL <- 32L
N_DOMAINS <- 4L

# Pilot variance components (feeds power simulation; pinned in pilot/) ----
SIGMA2_PARTICIPANT <- 0.85
SIGMA2_ITEM <- 0.43

# Stopping rule -----------------------------------------------------------
STOP_AFTER_DAYS <- 90L
MID_STUDY_AUDIT_N <- 150L

# Inclusion / exclusion ---------------------------------------------------
ATTENTION_CHECK_PASS_THRESHOLD <- 2L  # ≥ 2 of 3
COMPLETION_TIME_IQR_MULTIPLIER <- 1.5

# Bootstrap ---------------------------------------------------------------
BOOTSTRAP_B <- 999L  # Brier score CI bootstrap

# brms sampler ------------------------------------------------------------
BRMS_CHAINS <- 4L
BRMS_ITER <- 4000L
BRMS_WARMUP <- 1000L
BRMS_ADAPT_DELTA <- 0.95
BRMS_R_HAT_MAX <- 1.01     # convergence threshold per AC
BRMS_ESS_MIN <- 1000L      # bulk + tail ESS minimum per AC

# Compensation ------------------------------------------------------------
COMPENSATION_GBP_PER_HOUR <- 15L

# Outcome variable names (LOCKED — must match VAL-040 §7-§8) --------------
PRIMARY_OUTCOMES <- c(
  "team_accuracy",
  "nasa_tlx_overall",
  "trust_calibration_brier"
)
SECONDARY_OUTCOMES <- c(
  "ynn5_dtw_plausibility_mean",
  "cherry_picking_risk_score",
  "shape_coverage_fraction",
  "dpp_log_det_diversity"
)
ALL_OUTCOMES <- c(PRIMARY_OUTCOMES, SECONDARY_OUTCOMES)

# H1 model formula (LOCKED — must match VAL-040 §9 character-for-character)
# The Python invariant test pins this string to preregistration.md.
FORMULA_H1 <- "team_accuracy ~ tool * difficulty + trial_index + (1 + tool | participant) + (1 | item)"

# Tool conditions (LOCKED, ordered: native_guide is the reference level) --
TOOL_LEVELS <- c("native_guide", "hypothex_no_tips", "hypothex_tips")

# Difficulty levels -------------------------------------------------------
DIFFICULTY_LEVELS <- c("easy", "hard")

# Difficulty bins from pilot (VAL-040 §5) ---------------------------------
EASY_BIN_PILOT_ACCURACY_MIN <- 0.80
HARD_BIN_PILOT_ACCURACY_RANGE <- c(0.40, 0.60)

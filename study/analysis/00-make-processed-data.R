#' Apply pre-registered exclusions and produce the analysis-ready dataset.
#'
#' Reads raw exports from `data/raw/`, applies the *exact* exclusion
#' criteria from VAL-040 §4, writes `data/processed/study.rds` plus an
#' audit log of how many participants were excluded by each criterion.
#'
#' Exclusion rules (VAL-040 §4, LOCKED):
#'   1. Failed any attention check (≥ 2 of 3 must pass).
#'   2. Incomplete trials (must complete all 8).
#'   3. Completion time outside 1.5 × IQR of the pilot-derived median.
#'   4. Self-reported English non-fluency (post-task).
#'
#' Each rule is applied in sequence; the audit log reports the count
#' eliminated by *that* rule (after prior rules already filtered).
#'
#' Output: `data/processed/study.rds` (analysis-ready trial-level data
#' frame) and `data/processed/exclusion_audit.csv`.
#'
#' Reference: VAL-040 §4 ("Inclusion / exclusion (pre-registered)").

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
})

source("_constants.R")
set.seed(SEED)

# Load raw data ------------------------------------------------------------
trials_raw <- readRDS(file.path("data", "raw", "trials.rds"))
participants_raw <- readRDS(file.path("data", "raw", "participants.rds"))

# Audit log ----------------------------------------------------------------
audit <- data.frame(
  step = character(0),
  excluded_n = integer(0),
  remaining_n = integer(0),
  stringsAsFactors = FALSE
)
.append_audit <- function(step, excluded_n, remaining_n) {
  audit <<- rbind(audit, data.frame(
    step = step,
    excluded_n = as.integer(excluded_n),
    remaining_n = as.integer(remaining_n),
    stringsAsFactors = FALSE
  ))
}

n_initial <- nrow(participants_raw)
.append_audit("initial", 0L, n_initial)

# 1. Attention checks ------------------------------------------------------
attention_passed <- participants_raw$attention_check_pass_count >= ATTENTION_CHECK_PASS_THRESHOLD
n_after_ac <- sum(attention_passed)
.append_audit("attention_check_failed",
              n_initial - n_after_ac,
              n_after_ac)

# 2. Incomplete trials -----------------------------------------------------
trials_per_pid <- trials_raw %>%
  group_by(participant) %>%
  summarise(n_trials = n(), .groups = "drop")
complete_pids <- trials_per_pid$participant[
  trials_per_pid$n_trials == TRIALS_PER_PARTICIPANT
]
keep_pids <- intersect(participants_raw$participant[attention_passed], complete_pids)
n_after_complete <- length(keep_pids)
.append_audit("incomplete_trials",
              n_after_ac - n_after_complete,
              n_after_complete)

# 3. Completion time IQR --------------------------------------------------
times <- participants_raw[participants_raw$participant %in% keep_pids,
                          c("participant", "completion_time_min")]
median_t <- median(times$completion_time_min, na.rm = TRUE)
iqr_t <- IQR(times$completion_time_min, na.rm = TRUE)
upper_bound <- median_t + COMPLETION_TIME_IQR_MULTIPLIER * iqr_t
lower_bound <- max(0, median_t - COMPLETION_TIME_IQR_MULTIPLIER * iqr_t)
within_iqr <- times$completion_time_min >= lower_bound &
              times$completion_time_min <= upper_bound
keep_pids <- times$participant[within_iqr]
n_after_iqr <- length(keep_pids)
.append_audit("completion_time_outside_iqr",
              n_after_complete - n_after_iqr,
              n_after_iqr)

# 4. English non-fluency (self-reported post-task) ------------------------
english_ok <- participants_raw$english_fluent_self_report
keep_pids <- intersect(keep_pids,
                       participants_raw$participant[english_ok])
n_after_english <- length(keep_pids)
.append_audit("english_non_fluent",
              n_after_iqr - n_after_english,
              n_after_english)

# Per-condition final counts ----------------------------------------------
final_per_cond <- participants_raw %>%
  filter(participant %in% keep_pids) %>%
  count(tool, name = "n_kept")
cat("Final per-condition N:\n")
print(final_per_cond)

# Attrition tolerance flag (≤ 5%) ----------------------------------------
attrition <- 1.0 - (n_after_english / n_initial)
attrition_flag <- if (attrition > 0.05) {
  cat(sprintf(
    "  ATTRITION FLAG: %.1f%% > 5%% — flagged for paper discussion per AC.\n",
    100 * attrition
  ))
  TRUE
} else {
  FALSE
}

# Filter trials and write outputs -----------------------------------------
trials_processed <- trials_raw %>%
  filter(participant %in% keep_pids)

dir.create(file.path("data", "processed"), showWarnings = FALSE, recursive = TRUE)
saveRDS(trials_processed, file.path("data", "processed", "study.rds"))
write_csv(audit, file.path("data", "processed", "exclusion_audit.csv"))

cat(sprintf(
  "Wrote %d trials for %d participants (initial %d, attrition %.1f%%).\n",
  nrow(trials_processed), n_after_english, n_initial, 100 * attrition
))

#' Generate a 300-participant synthetic dataset matching the locked schema.
#'
#' Used by the CI smoke-test (AC line 164): "study/data/synthetic.rds with
#' 300 fake participants and known ground truth; pipeline runs end-to-end
#' and recovers known effects within Monte-Carlo error".
#'
#' Ground truth baked in:
#'   - hypothex_tips improves accuracy by d ≈ 0.40 vs. native_guide (matches
#'     the registered detectable effect).
#'   - hypothex_no_tips sits halfway between (d ≈ 0.20 vs. native_guide).
#'   - TLX is generated near-equivalent across conditions (Δ < SESOI_D)
#'     so H2 should reject the H2-null.
#'
#' Output: `data/synthetic.rds` (a single trials data frame), plus a
#' `data/synthetic_participants.rds` companion with one row per
#' participant for the post-task instruments.

suppressPackageStartupMessages({
  library(dplyr)
})

source("_constants.R")
set.seed(SEED)

n_per_cell <- SAMPLE_SIZE_PER_CELL  # 100
trials_per <- TRIALS_PER_PARTICIPANT  # 8
n_total <- N_CONDITIONS * n_per_cell  # 300

# Participants ------------------------------------------------------------
participants <- expand.grid(
  pid_index = seq_len(n_per_cell),
  tool = factor(TOOL_LEVELS, levels = TOOL_LEVELS)
)
participants$participant <- sprintf("P%04d", seq_len(nrow(participants)))
participants$attention_check_pass_count <- sample(2:3, nrow(participants),
                                                   replace = TRUE,
                                                   prob = c(0.10, 0.90))
participants$completion_time_min <- pmax(15, rnorm(nrow(participants),
                                                    mean = 38, sd = 8))
participants$english_fluent_self_report <- rep(TRUE, nrow(participants))
participants$nasa_tlx_overall <- pmax(0, pmin(100,
  ifelse(participants$tool == "native_guide", rnorm(nrow(participants), 60, 10),
  ifelse(participants$tool == "hypothex_no_tips", rnorm(nrow(participants), 58, 10),
                                                  rnorm(nrow(participants), 57, 10)))
))
participants$cherry_picking_risk_score <-
  pmax(0, pmin(1,
    ifelse(participants$tool == "native_guide", rbeta(nrow(participants), 6, 4),
    ifelse(participants$tool == "hypothex_no_tips", rbeta(nrow(participants), 4, 6),
                                                    rbeta(nrow(participants), 3, 7)))))
participants$shape_coverage_fraction <-
  pmax(0, pmin(1,
    ifelse(participants$tool == "native_guide", rbeta(nrow(participants), 2, 5),
    ifelse(participants$tool == "hypothex_no_tips", rbeta(nrow(participants), 4, 4),
                                                    rbeta(nrow(participants), 5, 3)))))
participants$dpp_log_det_diversity <-
  rnorm(nrow(participants),
        mean = ifelse(participants$tool == "native_guide", -2.0,
                ifelse(participants$tool == "hypothex_no_tips", -1.5, -1.0)),
        sd = 0.4)
participants$trust_calibration_brier <-
  pmax(0, pmin(1,
    ifelse(participants$tool == "native_guide", rbeta(nrow(participants), 3, 9),
    ifelse(participants$tool == "hypothex_no_tips", rbeta(nrow(participants), 2, 9),
                                                    rbeta(nrow(participants), 1.5, 9)))))

# Items -------------------------------------------------------------------
items <- expand.grid(
  domain_pack = c("cardiac_ecg", "eeg", "gps_displacement", "ndvi_phenology"),
  difficulty = c("easy", "hard"),
  rep = seq_len(4)
)
items$item <- sprintf("%s_%s_%02d",
                       substr(items$domain_pack, 1, 3),
                       items$difficulty,
                       items$rep)
items$shape_primitive <- sample(
  c("plateau", "trend", "step", "spike", "cycle", "transient", "noise"),
  size = nrow(items), replace = TRUE
)
items$item_intercept <- rnorm(nrow(items), 0, sqrt(SIGMA2_ITEM))

# Trials ------------------------------------------------------------------
trials <- list()
for (k in seq_len(nrow(participants))) {
  pid <- participants$participant[k]
  tool_k <- participants$tool[k]
  pid_random <- rnorm(1, 0, sqrt(SIGMA2_PARTICIPANT))
  easy_pool <- items[items$difficulty == "easy", ]
  hard_pool <- items[items$difficulty == "hard", ]
  chosen <- rbind(
    easy_pool[sample(nrow(easy_pool), 4), ],
    hard_pool[sample(nrow(hard_pool), 4), ]
  )
  chosen <- chosen[sample(nrow(chosen)), ]  # randomise trial order
  chosen$participant <- pid
  chosen$tool <- tool_k
  chosen$trial_index <- seq_len(nrow(chosen))
  chosen$pid_random <- pid_random

  # team_accuracy: logistic with tool effect
  beta_tool <- ifelse(tool_k == "hypothex_tips", 0.50,
                ifelse(tool_k == "hypothex_no_tips", 0.25, 0.0))
  beta_diff <- ifelse(chosen$difficulty == "hard", -0.30, 0.0)
  eta <- 0.5 + beta_tool + beta_diff + pid_random + chosen$item_intercept
  chosen$team_accuracy <- as.integer(runif(nrow(chosen)) < plogis(eta))

  # confidence: trended toward correctness for HypotheX, less so for baseline
  base_calib <- ifelse(tool_k == "hypothex_tips", 0.85,
                ifelse(tool_k == "hypothex_no_tips", 0.75, 0.65))
  chosen$confidence <- pmax(0, pmin(100,
    100 * (base_calib * chosen$team_accuracy +
           (1 - base_calib) * (1 - chosen$team_accuracy))
    + rnorm(nrow(chosen), 0, 8)
  ))

  # secondary outcomes: per-trial values
  chosen$ynn5_dtw_plausibility_mean <- pmax(0, pmin(1,
    ifelse(tool_k == "native_guide", rbeta(nrow(chosen), 3, 6),
    ifelse(tool_k == "hypothex_no_tips", rbeta(nrow(chosen), 4, 4),
                                          rbeta(nrow(chosen), 6, 4)))))
  chosen$cherry_picking_risk_score <- participants$cherry_picking_risk_score[k]
  chosen$shape_coverage_fraction   <- participants$shape_coverage_fraction[k]
  chosen$dpp_log_det_diversity     <- participants$dpp_log_det_diversity[k]
  chosen$trust_calibration_brier   <- participants$trust_calibration_brier[k]
  chosen$nasa_tlx_overall          <- participants$nasa_tlx_overall[k]
  chosen$tip_modality <- if (tool_k == "hypothex_tips") {
    sample(c("cf", "feature_importance", "contingency", "contrastive"),
           size = nrow(chosen), replace = TRUE)
  } else {
    NA_character_
  }

  trials[[k]] <- chosen
}
trials_df <- do.call(rbind, trials)
trials_df$participant <- factor(trials_df$participant)
trials_df$item <- factor(trials_df$item)
trials_df$tool <- factor(trials_df$tool, levels = TOOL_LEVELS)
trials_df$difficulty <- factor(trials_df$difficulty,
                                levels = DIFFICULTY_LEVELS)

# Output ------------------------------------------------------------------
dir.create(file.path("data"), showWarnings = FALSE, recursive = TRUE)
saveRDS(trials_df, file.path("data", "synthetic.rds"))
saveRDS(participants, file.path("data", "synthetic_participants.rds"))
cat(sprintf("Wrote synthetic dataset: %d trials × %d participants × %d conditions.\n",
             nrow(trials_df), nrow(participants), N_CONDITIONS))

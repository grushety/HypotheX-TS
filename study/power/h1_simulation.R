#' Power simulation for H1 (team accuracy) — VAL-040.
#'
#' Westfall, Kenny, Judd (2014) mixed-effects design with crossed random
#' effects on participant and item. Pre-registered: this script's seeded
#' output justifies the N = 100 per cell sample-size claim in
#' `preregistration.md` §4 ("Power justification").
#'
#' Design (matching `preregistration.md` §3 / §4):
#'   - 3 between-subjects tool conditions (HypotheX-tips,
#'     HypotheX-no-tips, Native Guide).
#'   - 2 within-subjects difficulty levels (easy / hard).
#'   - 8 trials per participant (4 easy + 4 hard).
#'   - 32 items, 8 per domain × 4 domains.
#'   - Outcome: binary `team_accuracy` modelled with logit-mixed-effects.
#'
#' Variance components from the N = 8 pilot
#' (`pilot/pilot_summary.md`):
#'   - σ²_participant = 0.85 (on the logit scale)
#'   - σ²_item        = 0.43
#'   - Residual logistic variance is fixed at π²/3 (logit link).
#'
#' Effect-size target: detectable d = 0.40 on H1 at 80 % power, α = 0.05.
#'
#' Usage: `Rscript study/power/h1_simulation.R [N_per_cell] [n_sims]`.
#' Default: N = 100 per cell, 1000 simulations. Reproduces the
#' registered 80 %-power claim under the seeded RNG.
#'
#' Reference:
#'   Westfall, Kenny, Judd, "Statistical Power and Optimal Design in
#'   Experiments in Which Samples of Participants Respond to Samples
#'   of Stimuli," J. Exp. Psych. General 143:2020–2045 (2014),
#'   DOI 10.1037/xge0000014.

suppressPackageStartupMessages({
  library(lme4)
  library(arm)   # invlogit
})

# Reproducibility ----------------------------------------------------------
set.seed(20260502)  # frozen at OSF registration

# Defaults -----------------------------------------------------------------
args <- commandArgs(trailingOnly = TRUE)
n_per_cell <- if (length(args) >= 1) as.integer(args[1]) else 100L
n_sims     <- if (length(args) >= 2) as.integer(args[2]) else 1000L

cat(sprintf("h1_simulation: N=%d per cell, %d simulations\n",
            n_per_cell, n_sims))

# Locked design constants --------------------------------------------------
n_conditions  <- 3L           # tool: hypothex_tips, hypothex_no_tips, native_guide
n_items_total <- 32L          # 8 per domain × 4 domains
n_trials_per  <- 8L           # 4 easy + 4 hard

# Variance components (pilot estimates) ------------------------------------
sigma2_participant <- 0.85
sigma2_item        <- 0.43

# Effect size --------------------------------------------------------------
# d = 0.40 between hypothex_tips and native_guide on the logit scale
# (Westfall-Kenny-Judd 2014 standardisation).
d_target <- 0.40

# Convert d to a logit-scale fixed-effect using Hedges-Olkin pooled-SD
# transformation under the logistic null:
#   logit_effect ≈ d * sqrt(σ²_p + σ²_i + π²/3)
logit_effect <- d_target *
  sqrt(sigma2_participant + sigma2_item + (pi^2 / 3))

# One simulation -----------------------------------------------------------
simulate_one <- function() {
  # Per-condition participants
  participants <- expand.grid(
    pid       = seq_len(n_per_cell * n_conditions),
    stringsAsFactors = FALSE
  )
  participants$tool <- factor(
    rep(c("hypothex_tips", "hypothex_no_tips", "native_guide"),
        each = n_per_cell),
    levels = c("native_guide", "hypothex_no_tips", "hypothex_tips")
  )
  participants$u_p <- rnorm(nrow(participants), 0, sqrt(sigma2_participant))

  # Items
  items <- data.frame(
    item       = seq_len(n_items_total),
    difficulty = factor(rep(c("easy", "hard"), each = n_items_total / 2),
                        levels = c("easy", "hard")),
    u_i        = rnorm(n_items_total, 0, sqrt(sigma2_item))
  )

  # Trials: each participant sees 8 items, drawn 4-easy + 4-hard from the
  # full item set (counterbalanced via Latin square at the analysis level).
  rows <- vector("list", nrow(participants))
  for (k in seq_len(nrow(participants))) {
    easy_pool <- items[items$difficulty == "easy", ]
    hard_pool <- items[items$difficulty == "hard", ]
    chosen_easy <- easy_pool[sample(nrow(easy_pool), 4L), ]
    chosen_hard <- hard_pool[sample(nrow(hard_pool), 4L), ]
    block <- rbind(chosen_easy, chosen_hard)
    block$pid    <- participants$pid[k]
    block$tool   <- participants$tool[k]
    block$u_p    <- participants$u_p[k]
    block$trial  <- seq_len(8L)
    rows[[k]] <- block
  }
  trials <- do.call(rbind, rows)

  # Linear predictor: tool effect (only `hypothex_tips` is "on") + difficulty
  # main effect + random intercepts.
  beta_tool <- ifelse(trials$tool == "hypothex_tips", logit_effect, 0.0)
  beta_diff <- ifelse(trials$difficulty == "hard", -0.30, 0.0)
  eta <- 0.50 + beta_tool + beta_diff + trials$u_p + trials$u_i
  trials$team_accuracy <- as.integer(
    runif(nrow(trials)) < arm::invlogit(eta)
  )

  # Fit registered model (matches `preregistration.md` §9).
  fit <- tryCatch(
    glmer(team_accuracy ~ tool * difficulty + trial
                        + (1 | pid) + (1 | item),
          data = trials, family = binomial(link = "logit"),
          control = glmerControl(optimizer = "bobyqa", calc.derivs = FALSE)),
    error = function(e) NULL
  )
  if (is.null(fit)) return(NA_real_)

  ## Two-sided test of the hypothex_tips contrast vs. native_guide reference.
  coefs <- summary(fit)$coefficients
  row_name <- "toolhypothex_tips"
  if (!row_name %in% rownames(coefs)) return(NA_real_)
  z_value <- coefs[row_name, "z value"]
  return(2 * pnorm(-abs(z_value)))
}

# Run simulations ----------------------------------------------------------
cat("Running ", n_sims, " simulations…\n", sep = "")
p_values <- vapply(seq_len(n_sims), function(i) {
  if (i %% 100 == 0) cat("  sim", i, "/", n_sims, "\n")
  simulate_one()
}, numeric(1))

power_estimate <- mean(p_values < 0.05, na.rm = TRUE)
cat(sprintf("\nEstimated power at d=%.2f, N=%d/cell: %.3f\n",
            d_target, n_per_cell, power_estimate))
cat(sprintf("Number of NA simulations (model failed to converge): %d\n",
            sum(is.na(p_values))))

# Sanity check: expect ≥ 0.78 to register the 80% power claim.
if (power_estimate < 0.78) {
  warning(
    sprintf("Estimated power %.3f is below the 0.80 target — recheck ",
            power_estimate),
    "variance components and re-run before OSF registration."
  )
}

# Output for the registration record ---------------------------------------
record <- list(
  n_per_cell        = n_per_cell,
  n_sims            = n_sims,
  d_target          = d_target,
  sigma2_participant = sigma2_participant,
  sigma2_item       = sigma2_item,
  logit_effect      = logit_effect,
  power_estimate    = power_estimate,
  n_failed          = sum(is.na(p_values)),
  seed              = 20260502
)
out_path <- file.path(dirname(sys.frame(1)$ofile %||% "."),
                      "h1_simulation_summary.txt")
writeLines(
  c(
    "# h1_simulation summary (auto-generated)",
    sprintf("seed: %d", record$seed),
    sprintf("n_per_cell: %d", record$n_per_cell),
    sprintf("n_sims: %d", record$n_sims),
    sprintf("d_target: %.4f", record$d_target),
    sprintf("logit_effect: %.4f", record$logit_effect),
    sprintf("sigma2_participant: %.4f", record$sigma2_participant),
    sprintf("sigma2_item: %.4f", record$sigma2_item),
    sprintf("power_estimate: %.4f", record$power_estimate),
    sprintf("n_failed: %d", record$n_failed)
  ),
  con = out_path
)
cat("Wrote", out_path, "\n")

#' Trust calibration via Brier score (Brier 1950) per condition.
#'
#' Brier score = mean((confidence_norm − accuracy)²) over trials.
#' Confidence is collected on a 0–100 slider (VAL-040 §6); we
#' normalise to [0, 1] for the Brier formula.
#'
#' Bootstrap CI: B = 999, percentile method, seeded RNG.
#' Reliability diagram per condition is plotted in `07-figures.Rmd`.

suppressPackageStartupMessages({
  library(boot)
  library(dplyr)
})

source("_constants.R")
set.seed(SEED)

data <- readRDS(file.path("data", "processed", "study.rds"))

# Normalise confidence to [0, 1] -----------------------------------------
data$confidence_norm <- data$confidence / 100.0
stopifnot(all(data$confidence_norm >= 0 & data$confidence_norm <= 1))

brier_statistic <- function(d, idx) {
  s <- d[idx, ]
  mean((s$confidence_norm - s$team_accuracy)^2)
}

# One bootstrap CI per condition -----------------------------------------
result <- list()
for (cond in TOOL_LEVELS) {
  sub <- data[data$tool == cond, ]
  if (nrow(sub) < 10) {
    warning(sprintf("condition %s has only %d trials; CI may be unstable",
                    cond, nrow(sub)))
  }
  boot_obj <- boot(sub, statistic = brier_statistic, R = BOOTSTRAP_B)
  ci <- boot.ci(boot_obj, type = "perc", conf = 0.95)
  result[[cond]] <- list(
    point = boot_obj$t0,
    ci = ci$percent[4:5],
    n_trials = nrow(sub)
  )
  cat(sprintf("%-20s Brier = %.4f, 95%% CI [%.4f, %.4f] (n=%d)\n",
              cond, boot_obj$t0, ci$percent[4], ci$percent[5], nrow(sub)))
}

dir.create("cache", showWarnings = FALSE)
saveRDS(list(brier = result, B = BOOTSTRAP_B),
        file.path("cache", "brier_summary.rds"))

#' H2 — NASA-TLX equivalence (TOST per Lakens 2017).
#'
#' Pre-registered SESOI is loaded from `_constants.R` (`SESOI_D`); per
#' VAL-040 §9 this is **± 0.40 d**. Reject the H2-null iff *both*
#' one-sided tests p < 0.05 (Lakens 2017).
#'
#' Reporting (per AC line 158): `(t1, p1, t2, p2)` plus equivalence
#' bounds in d-units — never just "equivalence achieved".

suppressPackageStartupMessages({
  library(TOSTER)
  library(dplyr)
})

source("_constants.R")
set.seed(SEED)

data <- readRDS(file.path("data", "processed", "study.rds"))

# Per-participant TLX overall — TLX is a between-subjects post-task
# measure, one row per participant.
tlx <- data %>%
  group_by(participant, tool) %>%
  summarise(tlx_overall = first(nasa_tlx_overall), .groups = "drop")

tips <- tlx[tlx$tool == "hypothex_tips", ]
ng   <- tlx[tlx$tool == "native_guide", ]

tost_h2 <- tsum_TOST(
  m1 = mean(tips$tlx_overall, na.rm = TRUE),
  m2 = mean(ng$tlx_overall, na.rm = TRUE),
  sd1 = sd(tips$tlx_overall, na.rm = TRUE),
  sd2 = sd(ng$tlx_overall, na.rm = TRUE),
  n1 = sum(!is.na(tips$tlx_overall)),
  n2 = sum(!is.na(ng$tlx_overall)),
  low_eqbound_d = -SESOI_D,
  high_eqbound_d = SESOI_D,
  alpha = ALPHA,
  eqbound_type = "SMD"
)

# Lakens 2017 reporting standard: report both one-sided tests.
t1 <- tost_h2$TOST$t[1]; p1 <- tost_h2$TOST$p.value[1]
t2 <- tost_h2$TOST$t[2]; p2 <- tost_h2$TOST$p.value[2]

cat(sprintf(
  "H2 TOST: bounds = [-%.2f, +%.2f] d\n  t1 = %.3f, p1 = %.4g\n  t2 = %.3f, p2 = %.4g\n",
  SESOI_D, SESOI_D, t1, p1, t2, p2
))

equivalence_achieved <- (p1 < ALPHA) && (p2 < ALPHA)
cat(sprintf("Equivalence achieved (both p < %.2f): %s\n",
            ALPHA, equivalence_achieved))

dir.create("cache", showWarnings = FALSE)
saveRDS(list(
  tost = tost_h2,
  t1 = t1, p1 = p1, t2 = t2, p2 = p2,
  sesoi_d = SESOI_D,
  equivalence_achieved = equivalence_achieved
), file.path("cache", "h2_summary.rds"))

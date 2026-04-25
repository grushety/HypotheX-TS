# VAL-041 — Analysis pipeline (lme4 + brms + TOST + Brier)

**Status:** [ ] Done
**Depends on:** VAL-040 (pre-registration locked); collected study data in `study/data/raw/`

---

## Goal

Implement the **complete pre-registered analysis pipeline** for the HypotheX-TS user study, locked to the formulas and thresholds specified in VAL-040 §9 and §10. Produces all paper figures and tables. Pipeline is fully reproducible from raw data with seeded RNG and pinned package versions.

**Why:** The point of pre-registration (VAL-040) is to constrain the analysis. The pipeline must implement *exactly* the locked formulas — not subtly different ones. Reviewers can re-run the pipeline against the deposited data and reproduce every reported number. Any deviation from VAL-040 must be logged in `study/deviations.md`.

**How it fits:** R + Python notebook system in `study/analysis/` running on a Docker image with pinned package versions (`renv` lockfile + `pyproject.toml`). Outputs: figures in `study/figures/`, tables in `study/tables/`, raw model fits cached in `study/cache/`. CI runs the pipeline end-to-end on a synthetic dataset of the same schema.

---

## Methodological references (for `methodology-auditor`)

Same as VAL-040 plus:
- Bates, Mächler, Bolker, Walker, **"Fitting Linear Mixed-Effects Models Using lme4,"** *Journal of Statistical Software* 67(1):1–48 (2015), DOI 10.18637/jss.v067.i01.
- Bürkner, **"brms: An R Package for Bayesian Multilevel Models Using Stan,"** *Journal of Statistical Software* 80(1):1–28 (2017), DOI 10.18637/jss.v080.i01.
- Brier, **"Verification of forecasts expressed in terms of probability,"** *Monthly Weather Review* 78:1–3 (1950) (canonical Brier score formula).
- Kruschke, **"Bayesian Estimation Supersedes the t Test,"** *J. Experimental Psychology: General* 142:573–603 (2013) (ROPE methodology).
- Lakens, Scheel, Isager, **"Equivalence Testing for Psychological Research: A Tutorial,"** *Advances in Methods and Practices in Psychological Science* 1:259–269 (2018), DOI 10.1177/2515245918770963 (TOST tutorial; complements Lakens 2017).
- Westfall, Kenny, Judd, **"Statistical Power and Optimal Design,"** *J. Experimental Psychology: General* 143:2020–2045 (2014) (mixed-effects d).

---

## Pipeline structure

```
study/
├── data/
│   ├── raw/                          # exported from study platform; immutable
│   ├── processed/                    # cleaned, joined, with exclusions applied
│   └── README.md                     # data dictionary matching VAL-040 §7-§8
├── analysis/
│   ├── 00-make-processed-data.R      # apply pre-registered exclusions
│   ├── 01-primary-h1-glmer.Rmd       # H1: glmer logit-mixed-effects on accuracy
│   ├── 02-primary-h2-tost.R          # H2: TLX equivalence (TOSTER package)
│   ├── 03-secondary-h3-h4-glmer.Rmd  # H3, H4: same lmer family, BH q=0.10
│   ├── 04-bayesian-companion.Rmd     # brms with Normal(0,1) priors, ROPE=±0.1d
│   ├── 05-trust-calibration-brier.R  # Brier score with bootstrap CI
│   ├── 06-exploratory.Rmd            # H5 + correlations + per-shape + tip-modality
│   ├── 07-figures.Rmd                # all paper figures
│   └── 08-tables.Rmd                 # all paper tables (LaTeX export)
├── cache/                            # cached model fits (gitignored)
├── figures/
├── tables/
├── deviations.md                     # any deviations from VAL-040
├── renv.lock                         # pinned R packages
├── pyproject.toml                    # pinned Python packages (for plotting only)
└── Dockerfile                        # exact runtime
```

---

## Pseudocode (key analyses)

### 01 — H1 primary analysis
```r
# study/analysis/01-primary-h1-glmer.Rmd
library(lme4); library(emmeans); library(parameters)
set.seed(42)
data <- readRDS("data/processed/study.rds")

# Exact formula from VAL-040 §9 (LOCKED)
fit_h1 <- glmer(
  accuracy ~ tool * difficulty + trial_index + (1 + tool | participant_id) + (1 | item_id),
  family = binomial(link = "logit"),
  data = data,
  control = glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 2e5))
)

# Westfall-Kenny-Judd 2014 d with 95% profile CI
d_h1 <- effectsize::cohens_d(fit_h1, ci = 0.95, ci_method = "profile")

# Holm correction across H1, H3, H4 family
p_holm <- p.adjust(c(p_h1, p_h3, p_h4), method = "holm")
```

### 02 — H2 equivalence (TOST)
```r
# study/analysis/02-primary-h2-tost.R
library(TOSTER)
set.seed(42)

# TLX overall, between-conditions
tost_h2 <- tsum_TOST(
  m1 = mean(data$tlx_overall[data$tool == "hypothex-ts"]),
  m2 = mean(data$tlx_overall[data$tool == "native-guide"]),
  sd1 = sd(data$tlx_overall[data$tool == "hypothex-ts"]),
  sd2 = sd(data$tlx_overall[data$tool == "native-guide"]),
  n1 = sum(data$tool == "hypothex-ts"),
  n2 = sum(data$tool == "native-guide"),
  low_eqbound_d = -0.40,           # SESOI from VAL-040 (LOCKED)
  high_eqbound_d = 0.40,
  alpha = 0.05
)
# Reject H2-null iff both one-sided tests p < 0.05
```

### 04 — Bayesian companion
```r
# study/analysis/04-bayesian-companion.Rmd
library(brms)
set.seed(42)

priors <- c(
  prior(normal(0, 1), class = "b"),     # standardised effects
  prior(student_t(3, 0, 2.5), class = "Intercept"),
  prior(student_t(3, 0, 2.5), class = "sd"),
  prior(lkj(2), class = "cor")
)

fit_bayes <- brm(
  accuracy ~ tool * difficulty + trial_index + (1 + tool | participant_id) + (1 | item_id),
  family = bernoulli(),
  prior = priors,
  data = data, chains = 4, iter = 4000, warmup = 1000,
  control = list(adapt_delta = 0.95), seed = 42
)

# Posterior probability outside ROPE = ±0.1 d (Kruschke 2013)
post_b <- posterior::as_draws_df(fit_bayes)$b_toolhypothex_ts
prob_outside_rope <- mean(abs(post_b) > 0.1)
```

### 05 — Trust calibration (Brier)
```r
# study/analysis/05-trust-calibration-brier.R
library(boot)
set.seed(42)

brier <- function(d, idx) {
  s <- d[idx, ]
  mean((s$confidence_norm - s$accuracy)^2)
}

per_condition_brier <- data %>%
  group_by(tool) %>%
  summarise(
    point  = brier(cur_data(), seq_len(n())),
    ci     = list(boot.ci(boot(cur_data(), brier, R = 999), type = "perc"))
  )
```

---

## Acceptance Criteria

- [ ] All 9 analysis files in `study/analysis/` exist and run end-to-end with `make analyse` taking ≤ 30 min on a CI runner
- [ ] **Every formula in `01-primary-h1-glmer.Rmd` matches VAL-040 §9 character-for-character.** Snapshot test compares the formula string in the Rmd source to a canonical string stored in `study/preregistration.md`
- [ ] **All thresholds (SESOI, ROPE, α, BH q, Holm family members) are loaded from a single `study/analysis/_constants.R` file** that is generated from VAL-040 — not duplicated literals across files
- [ ] **Pre-registered exclusions applied in `00-make-processed-data.R`** with audit log: count of excluded participants per criterion. Final N reported per condition with ≤ 5 % attrition tolerance flagged for paper discussion
- [ ] All NHST p-values reported alongside effect sizes with 95 % CIs (no bare p-values)
- [ ] **TOST result reported as `(t1, p1, t2, p2)` plus equivalence bounds in d-units**, not just "equivalence achieved" (Lakens 2017 reporting standard)
- [ ] Bayesian companion reports: posterior mean, 95 % credible interval, posterior probability outside ROPE, R-hat ≤ 1.01 for all parameters, ESS ≥ 1000 for all bulk and tail
- [ ] Brier score reported per condition with bootstrap 95 % CI (B = 999); reliability diagram plotted
- [ ] All figures in `study/figures/` are PDF + PNG, deterministic under seed; all tables in `study/tables/` are LaTeX (`booktabs`)
- [ ] `renv::snapshot()` lockfile committed; CI uses pinned versions; reproducibility verified by running pipeline twice and diffing outputs (allowing ≤ 1e-9 numerical jitter on continuous outputs)
- [ ] `study/cache/` gitignored but cached model fits reproducible from raw data
- [ ] **Synthetic-data CI test:** `study/data/synthetic.rds` with 300 fake participants and known ground truth; pipeline runs end-to-end and recovers known effects within Monte-Carlo error
- [ ] `study/deviations.md` updated for any deviation from VAL-040; each deviation includes timestamp, reason, methodological consequence
- [ ] **Paper figure 1 = Figure of effects per H1/H2/H3/H4 with effect size + CI + Bayes posterior overlaid** (Kay 2016 design)
- [ ] Output ZIP `study/replication-package.zip` containing data, analysis scripts, lockfile, Dockerfile — for paper supplement

## Definition of Done
- [ ] Run `methodology-auditor` agent with paper refs above. Confirm:
  - Every formula matches VAL-040 §9 verbatim (snapshot test passes)
  - Effect sizes are Westfall-Kenny-Judd 2014 d for mixed effects (NOT Cohen's d on raw means)
  - TOST is two-tailed (Lakens 2017) — both `t1, p1` and `t2, p2` reported
  - ROPE for Bayesian companion = ± 0.1 d as locked, not data-derived
  - Brier score formula = `mean((p − y)^2)` with reliability diagram
  - Bootstrap CIs use B = 999 (not 1000 — for two-sided 95 % CI rounding)
  - All p-values reported alongside effect sizes
  - Reproducibility test with diff tolerance is in CI
- [ ] Run `code-reviewer` agent — no blocking issues; pinned versions, seeded RNG everywhere, gitignored cache
- [ ] Replication package ZIP builds in CI
- [ ] `git commit -m "VAL-041: pre-registered analysis pipeline (lme4 + brms + TOST + Brier)"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---

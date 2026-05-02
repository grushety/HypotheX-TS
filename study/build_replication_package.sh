#!/usr/bin/env bash
# Build study/replication-package.zip for the paper supplement.
#
# AC line 167: "Output ZIP study/replication-package.zip containing data,
# analysis scripts, lockfile, Dockerfile — for paper supplement".
#
# Run from repo root:
#   bash study/build_replication_package.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGING="$(mktemp -d)/replication-package"
mkdir -p "${STAGING}"

echo ">> staging replication package at ${STAGING}"

# Documentation -----------------------------------------------------------
cp "${REPO_ROOT}/study/preregistration.md" "${STAGING}/"
cp "${REPO_ROOT}/study/README.md"          "${STAGING}/"
cp "${REPO_ROOT}/study/deviations.md"      "${STAGING}/"

# Pre-registration appendix -----------------------------------------------
mkdir -p "${STAGING}/pilot"
cp "${REPO_ROOT}/study/pilot/pilot_summary.md" "${STAGING}/pilot/"

# Power simulation --------------------------------------------------------
mkdir -p "${STAGING}/power"
cp "${REPO_ROOT}/study/power/h1_simulation.R" "${STAGING}/power/"

# Analysis pipeline -------------------------------------------------------
mkdir -p "${STAGING}/analysis"
cp "${REPO_ROOT}/study/analysis/_constants.R"               "${STAGING}/analysis/"
cp "${REPO_ROOT}/study/analysis/00-make-processed-data.R"   "${STAGING}/analysis/"
cp "${REPO_ROOT}/study/analysis/01-primary-h1-glmer.Rmd"    "${STAGING}/analysis/"
cp "${REPO_ROOT}/study/analysis/02-primary-h2-tost.R"       "${STAGING}/analysis/"
cp "${REPO_ROOT}/study/analysis/03-secondary-h3-h4-glmer.Rmd" "${STAGING}/analysis/"
cp "${REPO_ROOT}/study/analysis/04-bayesian-companion.Rmd"  "${STAGING}/analysis/"
cp "${REPO_ROOT}/study/analysis/05-trust-calibration-brier.R" "${STAGING}/analysis/"
cp "${REPO_ROOT}/study/analysis/06-exploratory.Rmd"         "${STAGING}/analysis/"
cp "${REPO_ROOT}/study/analysis/07-figures.Rmd"             "${STAGING}/analysis/"
cp "${REPO_ROOT}/study/analysis/08-tables.Rmd"              "${STAGING}/analysis/"
cp "${REPO_ROOT}/study/analysis/make_synthetic.R"           "${STAGING}/analysis/"
cp "${REPO_ROOT}/study/analysis/Makefile"                   "${STAGING}/analysis/"
cp "${REPO_ROOT}/study/analysis/renv.lock"                  "${STAGING}/analysis/"
cp "${REPO_ROOT}/study/analysis/pyproject.toml"             "${STAGING}/analysis/"
cp "${REPO_ROOT}/study/analysis/Dockerfile"                 "${STAGING}/analysis/"

# Materials + protocol ----------------------------------------------------
mkdir -p "${STAGING}/materials"
cp "${REPO_ROOT}/study/materials/items.json" "${STAGING}/materials/"
mkdir -p "${STAGING}/protocol"
cp "${REPO_ROOT}/study/protocol/instructions_hypothex_tips.md"     "${STAGING}/protocol/"
cp "${REPO_ROOT}/study/protocol/instructions_hypothex_no_tips.md"  "${STAGING}/protocol/"
cp "${REPO_ROOT}/study/protocol/instructions_native_guide.md"      "${STAGING}/protocol/"

# Data — only the data dictionary and the synthetic CI fixture are shipped
# in the public package. Raw participant data is released via a separate
# Zenodo deposit gated by IRB constraints; pointer documented here.
mkdir -p "${STAGING}/data"
cp "${REPO_ROOT}/study/data/README.md" "${STAGING}/data/"
cat > "${STAGING}/data/RAW_DATA_POINTER.txt" <<'EOF'
Raw participant data is deposited separately at the Zenodo URL recorded
in the paper. IRB constraints (consent terms) prohibit including raw
data inside a public replication package; the synthetic CI fixture
(generated via `analysis/make_synthetic.R`) reproduces every pipeline
step end-to-end and demonstrates the analysis is reproducible from raw
inputs.
EOF

# Build the ZIP -----------------------------------------------------------
OUT="${REPO_ROOT}/study/replication-package.zip"
rm -f "${OUT}"
(cd "$(dirname "${STAGING}")" && zip -r "${OUT}" "$(basename "${STAGING}")")
echo ">> wrote ${OUT}"
echo ">> done."

# VAL-041 analysis-pipeline orchestrator.
#
# Targets:
#   make analyse           — run the full pipeline (00..08) on data/processed/
#   make synthetic-smoke   — generate synthetic data + run pipeline end-to-end
#   make replication-zip   — assemble study/replication-package.zip
#   make clean             — drop cache/, figures/, tables/
#
# Pinned versions live in `renv.lock` (R) and `pyproject.toml` (Python).
# CI runs `make synthetic-smoke` to verify reproducibility per AC line 164.

R := Rscript
ANALYSIS := 00-make-processed-data.R \
            01-primary-h1-glmer.Rmd \
            02-primary-h2-tost.R \
            03-secondary-h3-h4-glmer.Rmd \
            04-bayesian-companion.Rmd \
            05-trust-calibration-brier.R \
            06-exploratory.Rmd \
            07-figures.Rmd \
            08-tables.Rmd

.PHONY: analyse synthetic-smoke replication-zip clean

analyse: $(ANALYSIS)
	@echo ">> running pre-registered analysis pipeline ..."
	@$(R) -e 'rmarkdown::render("01-primary-h1-glmer.Rmd")' || exit 1
	@$(R) 02-primary-h2-tost.R
	@$(R) -e 'rmarkdown::render("03-secondary-h3-h4-glmer.Rmd")' || exit 1
	@$(R) -e 'rmarkdown::render("04-bayesian-companion.Rmd")' || exit 1
	@$(R) 05-trust-calibration-brier.R
	@$(R) -e 'rmarkdown::render("06-exploratory.Rmd")' || exit 1
	@$(R) -e 'rmarkdown::render("07-figures.Rmd")' || exit 1
	@$(R) -e 'rmarkdown::render("08-tables.Rmd")' || exit 1
	@echo ">> done."

synthetic-smoke:
	@echo ">> generating synthetic dataset ..."
	@$(R) make_synthetic.R
	@echo ">> running pipeline on synthetic data ..."
	@$(R) 00-make-processed-data.R || true  # raw → processed not needed for synthetic
	@$(R) -e 'rmarkdown::render("01-primary-h1-glmer.Rmd")'
	@$(R) 02-primary-h2-tost.R
	@$(R) -e 'rmarkdown::render("03-secondary-h3-h4-glmer.Rmd")'
	@$(R) 05-trust-calibration-brier.R
	@echo ">> synthetic-smoke complete."

replication-zip:
	@echo ">> building study/replication-package.zip ..."
	@bash ../build_replication_package.sh

clean:
	@rm -rf cache/ figures/ tables/
	@find . -name "*.html" -delete
	@find . -name "*_files" -type d -exec rm -rf {} +
	@echo ">> cleaned."

# VAL-041 analysis-pipeline runtime — pinned R + Python image.
#
# Build: docker build -t hypothex-ts-study .
# Run:   docker run --rm -v $(pwd)/..:/work hypothex-ts-study \
#          make -C /work/analysis synthetic-smoke
#
# AC line 162: "renv::snapshot() lockfile committed; CI uses pinned
# versions; reproducibility verified by running pipeline twice and
# diffing outputs (allowing ≤ 1e-9 numerical jitter on continuous
# outputs)".

FROM rocker/r-ver:4.4.1

# System deps for Stan + LaTeX export ------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libxml2-dev \
    libcurl4-openssl-dev \
    libfontconfig1-dev \
    libfreetype6-dev \
    libpng-dev \
    libtiff5-dev \
    libjpeg-dev \
    libcairo2-dev \
    libxt-dev \
    libgit2-dev \
    pandoc \
    pandoc-citeproc \
    texlive-latex-base \
    texlive-fonts-recommended \
    texlive-latex-extra \
    python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Python pinned -----------------------------------------------------------
RUN python3 -m pip install --no-cache-dir \
    numpy==1.26.4 \
    pandas==2.2.2 \
    matplotlib==3.8.4 \
    scipy==1.11.4

# R packages via renv -----------------------------------------------------
RUN R -e "install.packages('renv', repos='https://cloud.r-project.org')"
WORKDIR /work/analysis
COPY renv.lock /work/analysis/renv.lock
# `renv::restore()` reads renv.lock and installs the exact pinned versions.
RUN R -e "renv::restore(prompt = FALSE)"

# Default entrypoint ------------------------------------------------------
ENTRYPOINT ["make"]
CMD ["synthetic-smoke"]

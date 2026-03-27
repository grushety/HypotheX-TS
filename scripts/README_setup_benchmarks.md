# Benchmark Setup Script

`scripts/setup_benchmarks.py` prepares a local benchmark workspace for HypotheX-TS.

It creates the expected `benchmarks/` layout, downloads the canonical UCR/UEA aeon-format archives, exports selected datasets as normalized NumPy arrays, writes metadata/manifests, and optionally clones the upstream model repositories for FCN, MLP, and InceptionTime.

## Usage

```bash
python scripts/setup_benchmarks.py --datasets all
python scripts/setup_benchmarks.py --datasets GunPoint,ECG200
```

## Common Options

- `--root <path>`: override the default output root (`<project>/benchmarks`)
- `--datasets all|<comma,list>`: choose which datasets to prepare
- `--skip-model-repos`: skip cloning `hfawaz/dl-4-tsc` and `hfawaz/InceptionTime`
- `--force-redownload`: redownload archives and rebuild processed dataset exports
- `--export-format npy`: only supported export format for now

## Notes

- The script is idempotent and skips completed steps unless `--force-redownload` is used.
- Original ZIP downloads are stored under `benchmarks/raw/downloads/`.
- Extracted archive contents are stored under `benchmarks/raw/archives/ucr_uea/`.
- Dataset-level `raw/` folders receive copies of the relevant train/test `.ts` files.
- If `aeon` is unavailable, the script falls back to direct archive downloads and an internal `.ts` parser.

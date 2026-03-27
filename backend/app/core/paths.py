from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent
INSTANCE_DIR = BACKEND_DIR / "instance"
BENCHMARK_ROOT = PROJECT_ROOT / "benchmarks"

"""Offline trainer for PPCEF coefficient flows (VAL-033).

One ``CoefficientFlow`` is trained per ``(domain_pack, decomposition_method)``
pair. The trained flow + standardisation is persisted as a ``.pt`` +
sidecar ``.json`` under ``models/ppcef/{pack}_{method}.pt``.

Usage (with project Python active, from repo root):

    python backend/scripts/train_ppcef.py \\
        --pack hydrology --method ETM \\
        --train-vectors-path data/vectors_hydrology_etm.npy \\
        [--epochs 200] [--seed 0] [--output models/ppcef/hydrology_ETM.pt]

The training-vector matrix is a 2-D ``(N, dim)`` numpy array of encoded
coefficient vectors (see ``encode_blob_to_vector``); the *caller* is
responsible for fitting blobs across the corpus and stacking their
encoded vectors.

Reference: Wielopolski et al. ECAI 2024, §4 (training protocol).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Iterable

import numpy as np

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_BACKEND_DIR = _REPO_ROOT / "backend"
sys.path.insert(0, str(_BACKEND_DIR))

from app.services.validation.ppcef import (  # noqa: E402
    DEFAULT_BATCH_SIZE,
    DEFAULT_HIDDEN_DIM,
    DEFAULT_LR,
    DEFAULT_N_EPOCHS,
    DEFAULT_N_LAYERS,
    DEFAULT_VAL_FRAC,
    METHOD_NSF,
    METHOD_REALNVP,
    CoefficientFlow,
)


def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", required=True, help="Domain pack identifier (e.g. hydrology, seismo-geodesy).")
    parser.add_argument("--method", required=True, help="Decomposition method (e.g. ETM, STL, MSTL).")
    parser.add_argument("--train-vectors-path", required=True,
                        help="Path to the training-vector .npy file (2-D, shape (N, dim)).")
    parser.add_argument("--output", default=None,
                        help="Output .pt path; defaults to models/ppcef/{pack}_{method}.pt.")
    parser.add_argument("--flow-method", default=None, choices=(METHOD_REALNVP, METHOD_NSF),
                        help="Flow architecture; default auto-selects RealNVP for dim < 4, NSF otherwise.")
    parser.add_argument("--epochs", type=int, default=DEFAULT_N_EPOCHS)
    parser.add_argument("--lr", type=float, default=DEFAULT_LR)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--n-layers", type=int, default=DEFAULT_N_LAYERS)
    parser.add_argument("--hidden-dim", type=int, default=DEFAULT_HIDDEN_DIM)
    parser.add_argument("--val-frac", type=float, default=DEFAULT_VAL_FRAC)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv)

    vectors_path = pathlib.Path(args.train_vectors_path)
    if not vectors_path.exists():
        print(f"train_ppcef: training-vectors path {vectors_path} does not exist", file=sys.stderr)
        return 1

    theta = np.load(vectors_path)
    if theta.ndim != 2:
        print(f"train_ppcef: expected 2-D training matrix; got shape {theta.shape}", file=sys.stderr)
        return 1
    n, dim = theta.shape
    print(f"Training PPCEF flow: pack={args.pack!r} method={args.method!r} N={n} dim={dim}")

    flow = CoefficientFlow(
        dim=dim,
        n_layers=args.n_layers,
        hidden_dim=args.hidden_dim,
        method=args.flow_method,
        seed=args.seed,
    )
    print(f"  flow_method={flow.method!r} layers={flow.n_layers} hidden={flow.hidden_dim}")

    summary = flow.fit(
        theta,
        n_epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch_size,
        val_frac=args.val_frac,
        verbose=args.verbose,
    )
    print(f"  best_val_loss={summary['best_val_loss']:.4f} best_epoch={summary['best_epoch']}")
    if summary["early_stopped_epoch"] is not None:
        print(f"  early stopped at epoch {summary['early_stopped_epoch']}")

    out_path = (
        pathlib.Path(args.output) if args.output is not None
        else _REPO_ROOT / "models" / "ppcef" / f"{args.pack}_{args.method}.pt"
    )
    flow.save(out_path)
    print(f"  wrote {out_path}")
    print(json.dumps({
        "pack": args.pack,
        "method": args.method,
        "flow_method": flow.method,
        "dim": dim,
        "n_train": n,
        "best_val_loss": summary["best_val_loss"],
        "train_log_p_5th": flow.train_log_p_5th,
        "train_log_p_50th": flow.train_log_p_50th,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

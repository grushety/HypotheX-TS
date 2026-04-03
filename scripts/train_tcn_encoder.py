#!/usr/bin/env python3
"""Train the 1D-TCN segment encoder on benchmark datasets (SEG-003).

Builds pseudo-labeled training segments from benchmark training splits via the
boundary proposer plus the six default support templates, then trains the
TcnSegmentEncoder with prototypical classification loss and saves the checkpoint.

Usage:
    python scripts/train_tcn_encoder.py [--epochs N] [--lr LR] [--embedding-dim D]

The app runs without a checkpoint (heuristic fallback).  A checkpoint is needed
to activate the TCN encoder path in encode_segment().

Loss: L_cls = -sum(log p(y_s | s))  [Snell et al., NeurIPS 2017, Eq. 2]

Source:
  Snell, J., Swersky, K., & Zemel, R. (2017). Prototypical Networks for
  Few-shot Learning. NeurIPS. https://arxiv.org/abs/1703.05175
"""

from __future__ import annotations

import argparse
import pathlib
import sys

_SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent

# Make backend/app importable without installing as a package.
sys.path.insert(0, str(_PROJECT_ROOT / "backend"))

import numpy as np
import torch
import torch.nn.functional as F

from app.services.datasets import DatasetRegistry
from app.services.suggestion.boundary_proposal import BoundaryProposerConfig, propose_boundaries
from app.services.suggestion.prototype_classifier import build_default_support_segments
from app.services.suggestion.segment_encoder import SegmentEncoderConfig, build_feature_matrix
from app.services.suggestion.tcn_encoder import (
    TcnEncoderConfig,
    TcnSegmentEncoder,
    _build_tcn_model,
    save_tcn_encoder_checkpoint,
)

_CHECKPOINT_PATH = _PROJECT_ROOT / "benchmarks" / "models" / "tcn_encoder" / "encoder.pt"

# Minimum number of time steps required to include a proposed segment.
_MIN_SEGMENT_LENGTH = 8


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def extract_training_segments(
    registry: DatasetRegistry,
    encoder_config: SegmentEncoderConfig,
    *,
    min_length: int = _MIN_SEGMENT_LENGTH,
) -> list[np.ndarray]:
    """Extract augmented feature matrices from all univariate training splits.

    Applies ``propose_boundaries`` to each training series and converts every
    resulting segment into an X_feat matrix via ``build_feature_matrix``.
    Only univariate datasets (n_channels == 1) are used; their feature matrices
    have shape (5, T), matching ``TcnEncoderConfig.in_channels == 5``.

    Args:
        registry:       Initialised DatasetRegistry.
        encoder_config: Config forwarded to build_feature_matrix.
        min_length:     Segments shorter than this are dropped.

    Returns:
        List of np.ndarray, each of shape (5, T_i).
    """
    bp_config = BoundaryProposerConfig()
    segments: list[np.ndarray] = []

    for summary in registry.list_datasets():
        if summary.n_channels != 1:
            continue  # skip multivariate — in_channels mismatch with default TCN
        dataset = registry.load_dataset(summary.name)
        n_train = dataset.train_series.shape[0]

        for i in range(n_train):
            series = dataset.train_series[i, 0, :]  # (T,)
            proposal = propose_boundaries(series.tolist(), bp_config)

            for seg in proposal.provisionalSegments:
                seg_values = series[seg.startIndex : seg.endIndex + 1].tolist()
                if len(seg_values) < min_length:
                    continue
                x_feat = build_feature_matrix(seg_values, encoder_config)
                segments.append(x_feat)

    return segments


def build_support_feature_matrices(
    encoder_config: SegmentEncoderConfig,
) -> tuple[list[np.ndarray], list[str]]:
    """Return (X_feat_list, label_list) for the six default support templates.

    The label order is the canonical class ordering used throughout training.
    """
    support = build_default_support_segments()
    x_feats: list[np.ndarray] = []
    labels: list[str] = []
    for seg in support:
        x_feats.append(build_feature_matrix(list(seg.values), encoder_config))
        labels.append(seg.label)
    return x_feats, labels


# ---------------------------------------------------------------------------
# Tensor helpers
# ---------------------------------------------------------------------------


def resample_feat(x_feat: np.ndarray, target_length: int) -> torch.Tensor:
    """Linearly resample (d' × T) feature matrix to (1, d', target_length).

    Mirrors the resampling in TcnSegmentEncoder.encode() so training and
    inference see the same input distribution.
    """
    d_prime, T = x_feat.shape
    src = np.linspace(0.0, 1.0, T)
    tgt = np.linspace(0.0, 1.0, target_length)
    resampled = np.vstack([np.interp(tgt, src, row) for row in x_feat]).astype(np.float32)
    return torch.from_numpy(resampled).unsqueeze(0)  # (1, d', target_length)


def compute_prototypes(
    model: torch.nn.Module,
    x_feats: list[np.ndarray],
    resample_length: int,
) -> torch.Tensor:
    """Encode the support feature matrices and return a stacked prototype matrix.

    Args:
        model:           TCN model in eval mode.
        x_feats:         One feature matrix per class.
        resample_length: TCN input length.

    Returns:
        Tensor of shape (n_classes, embedding_dim), each row L2-normalised.
    """
    embeddings: list[torch.Tensor] = []
    with torch.no_grad():
        for x_feat in x_feats:
            t = resample_feat(x_feat, resample_length)
            embeddings.append(model(t).squeeze(0))
    return torch.stack(embeddings, dim=0)


def assign_pseudo_labels(
    model: torch.nn.Module,
    x_feats: list[np.ndarray],
    prototypes: torch.Tensor,
    resample_length: int,
) -> list[int]:
    """Return the index of the nearest prototype for each segment (argmax cosine sim).

    Pseudo-labels are computed once before training to provide a stable
    supervision signal. Because both embeddings and prototypes are L2-
    normalised, dot-product equals cosine similarity.
    """
    indices: list[int] = []
    with torch.no_grad():
        for x_feat in x_feats:
            t = resample_feat(x_feat, resample_length)
            emb = model(t).squeeze(0)
            sims = torch.mv(prototypes, emb)
            indices.append(int(torch.argmax(sims).item()))
    return indices


# ---------------------------------------------------------------------------
# Training and evaluation
# ---------------------------------------------------------------------------


def train_epoch(
    model: torch.nn.Module,
    optimizer: torch.optim.Optimizer,
    support_feats: list[np.ndarray],
    support_label_indices: list[int],
    query_feats: list[np.ndarray],
    pseudo_labels: list[int],
    resample_length: int,
    temperature: float = 0.2,
    batch_size: int = 32,
) -> float:
    """Run one training epoch and return the mean cross-entropy loss.

    Prototypes are computed once at the start of the epoch from the current
    encoder weights (under torch.no_grad).  Gradients flow only through the
    query and support embeddings computed in each batch, not through the
    epoch-start prototypes.

    Loss (per batch):
        L_cls = -sum_i log p(y_i | s_i)
              = cross_entropy(sims / temperature, labels)

    Source: Snell et al. 2017, Eq. 2.
    """
    # Compute epoch-start prototypes (detached — no gradients).
    model.eval()
    with torch.no_grad():
        prototypes = compute_prototypes(model, support_feats, resample_length)

    model.train()
    all_feats = support_feats + query_feats
    all_labels = support_label_indices + pseudo_labels
    perm = np.random.permutation(len(all_feats))

    total_loss = 0.0
    n_batches = 0

    for start in range(0, len(perm), batch_size):
        batch_idx = perm[start : start + batch_size]
        embeddings = [model(resample_feat(all_feats[i], resample_length)).squeeze(0) for i in batch_idx]
        emb_batch = torch.stack(embeddings, dim=0)                          # (B, d)
        label_batch = torch.tensor([all_labels[i] for i in batch_idx], dtype=torch.long)
        sims = torch.mm(emb_batch, prototypes.T) / temperature              # (B, n_classes)
        loss = F.cross_entropy(sims, label_batch)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        total_loss += float(loss.item())
        n_batches += 1

    return total_loss / max(n_batches, 1)


def evaluate(
    model: torch.nn.Module,
    val_feats: list[np.ndarray],
    val_labels: list[int],
    support_feats: list[np.ndarray],
    resample_length: int,
    temperature: float = 0.2,
) -> float:
    """Return accuracy of the model on the validation set vs. pseudo-labels."""
    model.eval()
    with torch.no_grad():
        prototypes = compute_prototypes(model, support_feats, resample_length)
        correct = 0
        for x_feat, label in zip(val_feats, val_labels):
            emb = model(resample_feat(x_feat, resample_length)).squeeze(0)
            sims = torch.mv(prototypes, emb) / temperature
            pred = int(torch.argmax(sims).item())
            correct += int(pred == label)
    return correct / max(len(val_labels), 1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train the 1D-TCN segment encoder on benchmark datasets.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--epochs", type=int, default=50, help="Training epochs")
    parser.add_argument("--lr", type=float, default=1e-3, help="Adam learning rate")
    parser.add_argument("--embedding-dim", type=int, default=64, help="Embedding dimension")
    args = parser.parse_args()

    encoder_config = SegmentEncoderConfig()
    tcn_config = TcnEncoderConfig(embedding_dim=args.embedding_dim)

    print("Loading dataset registry …")
    registry = DatasetRegistry()

    print("Building support feature matrices …")
    support_feats, support_labels = build_support_feature_matrices(encoder_config)
    n_classes = len(support_labels)
    support_label_indices = list(range(n_classes))
    print(f"  {n_classes} semantic classes: {support_labels}")

    print("Extracting segments from benchmark training splits …")
    all_query_feats = extract_training_segments(registry, encoder_config)
    print(f"  {len(all_query_feats)} query segments extracted")

    rng = np.random.default_rng(42)
    perm = rng.permutation(len(all_query_feats))
    split = max(1, int(len(perm) * 0.8))
    train_idx, val_idx = perm[:split], perm[split:]
    train_query_feats = [all_query_feats[i] for i in train_idx]
    val_query_feats = [all_query_feats[i] for i in val_idx]
    print(f"  Train query: {len(train_query_feats)},  Val query: {len(val_query_feats)}")

    model = _build_tcn_model(tcn_config)

    print("Computing initial pseudo-labels …")
    model.eval()
    init_prototypes = compute_prototypes(model, support_feats, tcn_config.resample_length)
    train_pseudo = assign_pseudo_labels(model, train_query_feats, init_prototypes, tcn_config.resample_length)
    val_pseudo = assign_pseudo_labels(model, val_query_feats, init_prototypes, tcn_config.resample_length)

    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    log_every = max(1, args.epochs // 10)

    print(f"\nTraining  epochs={args.epochs}  lr={args.lr}  embedding_dim={args.embedding_dim}\n")
    for epoch in range(1, args.epochs + 1):
        mean_loss = train_epoch(
            model=model,
            optimizer=optimizer,
            support_feats=support_feats,
            support_label_indices=support_label_indices,
            query_feats=train_query_feats,
            pseudo_labels=train_pseudo,
            resample_length=tcn_config.resample_length,
        )
        if epoch % log_every == 0 or epoch == 1:
            print(f"  epoch {epoch:4d}/{args.epochs}  loss={mean_loss:.4f}")

    val_acc = evaluate(
        model=model,
        val_feats=val_query_feats,
        val_labels=val_pseudo,
        support_feats=support_feats,
        resample_length=tcn_config.resample_length,
    )
    print(f"\nFinal val accuracy (vs. pseudo-labels): {val_acc:.1%}")

    # Freeze and save.
    for param in model.parameters():
        param.requires_grad_(False)
    model.eval()
    encoder = TcnSegmentEncoder(model, tcn_config)
    dest = save_tcn_encoder_checkpoint(encoder, _CHECKPOINT_PATH)
    print(f"Checkpoint saved: {dest}")


if __name__ == "__main__":
    main()

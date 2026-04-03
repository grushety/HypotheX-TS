"""1D-TCN segment encoder for HypotheX-TS (SEG-002).

Provides a small frozen Temporal Convolutional Network that encodes the
augmented feature matrix produced by build_feature_matrix() into an L2-
normalised embedding vector.

The model is loaded once from a checkpoint file via load_tcn_encoder() which
is decorated with @functools.lru_cache so it executes only on first call.
When torch is not installed or the checkpoint is absent/unreadable the
function returns None and encode_segment() falls back silently to the
heuristic encoder.

Architecture (< 50k parameters):
  Input  : X_feat (d' × T) from build_feature_matrix, resampled to resample_length
  Layer 1: CausalConv1d(in_channels, 32, kernel=3, dilation=1) + ReLU
  Layer 2: CausalConv1d(32,          64, kernel=3, dilation=2) + ReLU
  Layer 3: CausalConv1d(64,          64, kernel=3, dilation=4) + ReLU
  Global average pool  →  Linear(64, embedding_dim)  →  L2 normalise

Source: Bai et al., "An Empirical Evaluation of Generic Convolutional and
Recurrent Networks for Sequence Modeling", arXiv 1803.01271, 2018.
Embedding contract follows Snell et al., "Prototypical Networks for Few-shot
Learning", NeurIPS 2017.
"""

from __future__ import annotations

import functools
import logging
import pathlib
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)

# Resolved relative to this file: backend/app/services/suggestion/ → project root
_CHECKPOINT_PATH: pathlib.Path = (
    pathlib.Path(__file__).parents[4] / "benchmarks" / "models" / "tcn_encoder" / "encoder.pt"
)


@dataclass(frozen=True)
class TcnEncoderConfig:
    """Architecture hyper-parameters for the 1D-TCN encoder.

    All fields are serialised into the checkpoint so that the correct network
    can be reconstructed on load without relying on a separate config file.

    Attributes:
        embedding_dim:   Dimension of the output embedding vector.
        resample_length: Input is resampled to this fixed length before the
                         forward pass (matches the length used during training).
        channels:        Output channel counts for the three causal conv layers.
                         len(channels) must equal the number of dilation stages.
        kernel_size:     Kernel width shared across all conv layers.
        in_channels:     Number of input channels (= d' from build_feature_matrix).
                         Must match the checkpoint the encoder was trained on.
    """

    embedding_dim: int = 64
    resample_length: int = 32
    channels: tuple[int, ...] = (32, 64, 64)
    kernel_size: int = 3
    in_channels: int = 5  # d' for 1-channel signal with include_missingness_mask=True

    def to_dict(self) -> dict:
        return {
            "embedding_dim": self.embedding_dim,
            "resample_length": self.resample_length,
            "channels": list(self.channels),
            "kernel_size": self.kernel_size,
            "in_channels": self.in_channels,
        }

    @classmethod
    def from_dict(cls, d: dict) -> TcnEncoderConfig:
        return cls(
            embedding_dim=int(d["embedding_dim"]),
            resample_length=int(d["resample_length"]),
            channels=tuple(int(c) for c in d["channels"]),
            kernel_size=int(d["kernel_size"]),
            in_channels=int(d["in_channels"]),
        )


def _build_tcn_model(config: TcnEncoderConfig):
    """Instantiate the PyTorch TCN model for the given config.

    Requires torch to be installed.  Called only from TcnSegmentEncoder and
    save_tcn_encoder_checkpoint() — never called at module import time.

    Source: causal convolution padding scheme from Bai et al. 2018 (§2.1).
    """
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    class _CausalConv1d(nn.Module):
        """Left-pad then conv — output at time t sees only positions ≤ t.

        Eq. (left-pad size) = (kernel_size − 1) × dilation   [Bai et al. 2018].
        """

        def __init__(self, in_ch: int, out_ch: int, kernel: int, dilation: int) -> None:
            super().__init__()
            self._left_pad = (kernel - 1) * dilation
            self.conv = nn.Conv1d(in_ch, out_ch, kernel, dilation=dilation, padding=0)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.conv(F.pad(x, (self._left_pad, 0)))

    class _TcnModel(nn.Module):
        """Three-layer causal TCN with global average pool and linear projection.

        Architecture spec from SEG-002 ticket; embedding contract from
        Snell et al. 2017 (L2-normalised prototype distance).
        """

        def __init__(self, cfg: TcnEncoderConfig) -> None:
            super().__init__()
            dilations = [1, 2, 4]
            channel_seq = [cfg.in_channels] + list(cfg.channels)
            layers: list[nn.Module] = []
            for i, (in_ch, out_ch) in enumerate(zip(channel_seq, channel_seq[1:])):
                layers.append(_CausalConv1d(in_ch, out_ch, cfg.kernel_size, dilations[i]))
                layers.append(nn.ReLU())
            self.convs = nn.Sequential(*layers)
            self.proj = nn.Linear(channel_seq[-1], cfg.embedding_dim)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            h = self.convs(x).mean(dim=-1)   # global avg pool: (B, C_last)
            h = self.proj(h)                 # (B, embedding_dim)
            norm = h.norm(dim=-1, keepdim=True).clamp(min=1e-8)
            return h / norm                  # L2-normalised

    return _TcnModel(config)


class TcnSegmentEncoder:
    """Frozen 1D-TCN segment encoder.

    Wraps a PyTorch _TcnModel whose weights are fixed at construction time
    (eval mode, requires_grad=False).  Inference always runs under
    torch.no_grad() to avoid gradient accumulation.

    Source: architecture — Bai et al. 2018; embedding contract — Snell et al.
    2017.
    """

    def __init__(self, model, config: TcnEncoderConfig) -> None:
        self._model = model
        self._config = config
        self._model.eval()
        for param in self._model.parameters():
            param.requires_grad_(False)

    @property
    def config(self) -> TcnEncoderConfig:
        return self._config

    def encode(self, x_feat: np.ndarray) -> np.ndarray:
        """Encode a feature matrix into an L2-normalised embedding vector.

        The feature matrix is linearly resampled to config.resample_length
        along the time axis before being passed through the network.

        Args:
            x_feat: Shape (d', T).  d' must equal config.in_channels.

        Returns:
            np.ndarray of shape (embedding_dim,), dtype float64, L2-norm ≈ 1.

        Raises:
            ValueError: If x_feat.shape[0] != config.in_channels.
        """
        import torch

        d_prime, T = x_feat.shape
        if d_prime != self._config.in_channels:
            raise ValueError(
                f"TcnSegmentEncoder expected {self._config.in_channels} input channels, "
                f"got {d_prime}."
            )

        src = np.linspace(0.0, 1.0, T)
        tgt = np.linspace(0.0, 1.0, self._config.resample_length)
        resampled = np.vstack([np.interp(tgt, src, row) for row in x_feat]).astype(np.float32)

        tensor = torch.from_numpy(resampled).unsqueeze(0)  # (1, d', resample_length)
        with torch.no_grad():
            embedding = self._model(tensor)  # (1, embedding_dim)
        return embedding.squeeze(0).numpy().astype(np.float64)


@functools.lru_cache(maxsize=1)
def load_tcn_encoder() -> TcnSegmentEncoder | None:
    """Return a frozen TcnSegmentEncoder loaded from the checkpoint, or None.

    Cached after the first call — the checkpoint is read at most once per
    process.  All failure modes (torch absent, file missing, corrupt weights)
    are caught and logged at DEBUG level; callers receive None and must fall
    back to the heuristic encoder.

    Checkpoint format (saved by save_tcn_encoder_checkpoint):
      {
        "config": <TcnEncoderConfig.to_dict()>,
        "state_dict": <model.state_dict()>,
      }

    Checkpoint path: benchmarks/models/tcn_encoder/encoder.pt
    (resolved relative to the project root from this file's location)
    """
    try:
        import torch
    except ImportError:
        logger.debug("torch is not installed; TCN encoder unavailable.")
        return None

    if not _CHECKPOINT_PATH.exists():
        logger.debug(
            "TCN encoder checkpoint not found at %s; using heuristic encoder.",
            _CHECKPOINT_PATH,
        )
        return None

    try:
        checkpoint = torch.load(str(_CHECKPOINT_PATH), map_location="cpu", weights_only=True)
        config = TcnEncoderConfig.from_dict(checkpoint["config"])
        model = _build_tcn_model(config)
        model.load_state_dict(checkpoint["state_dict"])
        logger.debug("TCN encoder loaded from %s.", _CHECKPOINT_PATH)
        return TcnSegmentEncoder(model, config)
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "TCN encoder checkpoint failed to load (%s); using heuristic encoder.", exc
        )
        return None


def save_tcn_encoder_checkpoint(
    encoder: TcnSegmentEncoder,
    path: pathlib.Path | str | None = None,
) -> pathlib.Path:
    """Persist a TcnSegmentEncoder to disk.

    Creates the parent directory if it does not exist.  The saved file can
    be loaded by load_tcn_encoder().

    Args:
        encoder: A TcnSegmentEncoder instance (typically after training).
        path:    Destination path.  Defaults to the standard checkpoint path.

    Returns:
        The resolved pathlib.Path of the saved file.
    """
    import torch

    dest = pathlib.Path(path) if path is not None else _CHECKPOINT_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = {
        "config": encoder.config.to_dict(),
        "state_dict": encoder._model.state_dict(),
    }
    torch.save(checkpoint, str(dest))
    return dest

# -*- coding: utf-8 -*-
"""PINN components for shallow-water flood prediction.

The module is optional at runtime: importing it does not require torch, but
training/inference classes are only usable when torch is installed.
"""

from __future__ import annotations

from typing import Dict, Iterable

try:
    import torch
    from torch import nn
except Exception:  # pragma: no cover - optional research dependency
    torch = None
    nn = None


class FourierFeatures(nn.Module if nn is not None else object):
    """Encode coordinates with random Fourier features to reduce spectral bias."""

    def __init__(self, input_dim: int, num_frequencies: int = 32, sigma: float = 10.0):
        if torch is None or nn is None:
            raise ImportError("FourierFeatures requires torch.")
        super().__init__()
        self.input_dim = int(input_dim)
        self.num_frequencies = int(num_frequencies)
        projection = torch.randn(self.input_dim, self.num_frequencies) * float(sigma)
        self.register_buffer("projection", projection)

    @property
    def output_dim(self) -> int:
        return self.input_dim + self.input_dim * self.num_frequencies * 2

    def forward(self, coords):
        projected = coords.unsqueeze(-1) * self.projection
        encoded = torch.cat([torch.sin(projected), torch.cos(projected)], dim=-1)
        return torch.cat([coords, encoded.flatten(start_dim=1)], dim=1)


class PINNSWENetwork(nn.Module if nn is not None else object):
    """MLP predicting h, u, v from x, y, t with Fourier feature encoding."""

    def __init__(
        self,
        input_dim: int = 3,
        hidden_dim: int = 128,
        hidden_layers: int = 6,
        num_frequencies: int = 32,
        fourier_sigma: float = 10.0,
    ):
        if torch is None or nn is None:
            raise ImportError("PINNSWENetwork requires torch.")
        super().__init__()
        self.encoder = FourierFeatures(input_dim=input_dim, num_frequencies=num_frequencies, sigma=fourier_sigma)

        layers = []
        in_features = self.encoder.output_dim
        for _ in range(hidden_layers):
            layers.append(nn.Linear(in_features, hidden_dim))
            layers.append(nn.SiLU())
            in_features = hidden_dim
        layers.append(nn.Linear(in_features, 3))
        self.net = nn.Sequential(*layers)

    def forward(self, coords) -> Dict[str, object]:
        raw = self.net(self.encoder(coords))
        # Softplus keeps predicted depth non-negative while u/v remain signed.
        h = torch.nn.functional.softplus(raw[:, 0:1])
        return {"h": h, "u": raw[:, 1:2], "v": raw[:, 2:3]}


class NTKAdaptiveLossBalancer:
    """Lightweight adaptive weighting for data, PDE, and boundary losses.

    Full NTK computation is expensive for routine iterations. This class uses
    the same practical goal: keep loss terms on comparable influence scales by
    inversely weighting their detached magnitudes with exponential smoothing.
    """

    def __init__(self, loss_names: Iterable[str], momentum: float = 0.9, eps: float = 1e-8):
        self.loss_names = list(loss_names)
        self.momentum = float(momentum)
        self.eps = float(eps)
        self.weights = {name: 1.0 for name in self.loss_names}

    def update(self, losses: Dict[str, object]) -> Dict[str, float]:
        if torch is None:
            raise ImportError("NTKAdaptiveLossBalancer requires torch losses.")

        magnitudes = {}
        for name in self.loss_names:
            loss = losses[name]
            magnitudes[name] = float(torch.clamp(loss.detach().abs(), min=self.eps).cpu())

        inverse = {name: 1.0 / value for name, value in magnitudes.items()}
        mean_inverse = sum(inverse.values()) / max(len(inverse), 1)
        target = {name: value / max(mean_inverse, self.eps) for name, value in inverse.items()}

        for name in self.loss_names:
            self.weights[name] = self.momentum * self.weights[name] + (1.0 - self.momentum) * target[name]

        return dict(self.weights)

    def weighted_sum(self, losses: Dict[str, object]):
        weights = self.update(losses)
        total = None
        for name, loss in losses.items():
            weighted = loss * weights.get(name, 1.0)
            total = weighted if total is None else total + weighted
        return total

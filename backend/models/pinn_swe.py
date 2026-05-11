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


def _resolve_device(device: str):
    if torch is None:
        raise ImportError("PINN dry run requires torch.")
    if device == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device == "cuda" and not torch.cuda.is_available():
        return torch.device("cpu")
    return torch.device(device)


def _grad(values, coords):
    return torch.autograd.grad(
        values,
        coords,
        grad_outputs=torch.ones_like(values),
        create_graph=True,
        retain_graph=True,
    )[0]


def compute_swe_residuals(model: PINNSWENetwork, coords, gravity: float = 9.81) -> Dict[str, object]:
    """Compute differentiable shallow-water residuals on x, y, t collocation points."""
    prediction = model(coords)
    h = prediction["h"]
    u = prediction["u"]
    v = prediction["v"]

    h_grad = _grad(h, coords)
    u_grad = _grad(u, coords)
    v_grad = _grad(v, coords)
    hu_grad = _grad(h * u, coords)
    hv_grad = _grad(h * v, coords)

    h_x, h_y, h_t = h_grad[:, 0:1], h_grad[:, 1:2], h_grad[:, 2:3]
    u_x, u_y, u_t = u_grad[:, 0:1], u_grad[:, 1:2], u_grad[:, 2:3]
    v_x, v_y, v_t = v_grad[:, 0:1], v_grad[:, 1:2], v_grad[:, 2:3]

    continuity = h_t + hu_grad[:, 0:1] + hv_grad[:, 1:2]
    momentum_x = u_t + u * u_x + v * u_y + float(gravity) * h_x
    momentum_y = v_t + u * v_x + v * v_y + float(gravity) * h_y

    return {
        "continuity": continuity,
        "momentum_x": momentum_x,
        "momentum_y": momentum_y,
    }


def run_pinn_dry_run(
    num_points: int = 64,
    hidden_dim: int = 64,
    hidden_layers: int = 3,
    num_frequencies: int = 16,
    device: str = "auto",
) -> Dict:
    """Run one no-optimizer PINN smoke pass and expose finite diagnostics."""
    if torch is None or nn is None:
        raise ImportError("PINN dry run requires torch.")

    resolved_device = _resolve_device(device)
    safe_points = max(4, min(int(num_points), 4096))
    torch.manual_seed(42)

    coords = torch.rand((safe_points, 3), dtype=torch.float32, device=resolved_device, requires_grad=True)
    model = PINNSWENetwork(
        input_dim=3,
        hidden_dim=int(hidden_dim),
        hidden_layers=int(hidden_layers),
        num_frequencies=int(num_frequencies),
    ).to(resolved_device)

    prediction = model(coords)
    residuals = compute_swe_residuals(model, coords)
    pde_loss = sum(torch.mean(value * value) for value in residuals.values())
    data_loss = torch.mean((prediction["h"] - 0.25) ** 2) + torch.mean(prediction["u"] ** 2) + torch.mean(prediction["v"] ** 2)
    bc_loss = torch.mean((prediction["u"][:2] ** 2) + (prediction["v"][:2] ** 2))

    balancer = NTKAdaptiveLossBalancer(["data", "pde", "bc"])
    losses = {"data": data_loss, "pde": pde_loss, "bc": bc_loss}
    total = balancer.weighted_sum(losses)

    return {
        "status": "ok",
        "device": str(resolved_device),
        "collocation_points": safe_points,
        "network": {
            "hidden_dim": int(hidden_dim),
            "hidden_layers": int(hidden_layers),
            "fourier_frequencies": int(num_frequencies),
        },
        "losses": {
            "data": round(float(data_loss.detach().cpu()), 8),
            "pde": round(float(pde_loss.detach().cpu()), 8),
            "bc": round(float(bc_loss.detach().cpu()), 8),
            "total": round(float(total.detach().cpu()), 8),
        },
        "adaptive_weights": {name: round(float(value), 6) for name, value in balancer.weights.items()},
        "residual_rmse": {
            name: round(float(torch.sqrt(torch.mean(value * value)).detach().cpu()), 8)
            for name, value in residuals.items()
        },
    }

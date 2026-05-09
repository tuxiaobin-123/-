# -*- coding: utf-8 -*-
"""Optional Numba kernels for the NumPy SWE fallback path."""

from __future__ import annotations

try:
    from numba import njit
except Exception:  # pragma: no cover - optional acceleration dependency
    njit = None


if njit is not None:

    @njit(cache=True)
    def _sanitize_numpy_state_kernel(h, u, v, max_depth, max_velocity):
        rows, cols = h.shape
        for i in range(rows):
            for j in range(cols):
                depth = h[i, j]
                if depth != depth or depth < 0.001:
                    h[i, j] = 0.0
                    u[i, j] = 0.0
                    v[i, j] = 0.0
                    continue

                if depth > max_depth:
                    h[i, j] = max_depth

                vel_u = u[i, j]
                vel_v = v[i, j]
                if vel_u != vel_u:
                    vel_u = 0.0
                if vel_v != vel_v:
                    vel_v = 0.0

                speed = (vel_u * vel_u + vel_v * vel_v) ** 0.5
                if speed > max_velocity:
                    scale = max_velocity / (speed + 1e-10)
                    vel_u *= scale
                    vel_v *= scale

                u[i, j] = vel_u
                v[i, j] = vel_v


def sanitize_numpy_state_inplace(h, u, v, max_depth: float, max_velocity: float) -> bool:
    """Return True when the optional Numba kernel handled sanitization."""
    if njit is None:
        return False

    _sanitize_numpy_state_kernel(h, u, v, float(max_depth), float(max_velocity))
    return True

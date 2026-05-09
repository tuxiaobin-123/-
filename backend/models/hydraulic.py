# -*- coding: utf-8 -*-
"""
Simplified shallow-water-equation hydraulic model.

The model now supports a basic dam/reservoir scene:
- upstream reservoir pool initialization
- dam crest ridge with gate section
- configurable gate release
- downstream control water level boundary
"""

from typing import Dict, List

import numpy as np

from models.dem_cache import load_dem_grid_cache
from models.numba_kernels import sanitize_numpy_state_inplace

try:
    import torch
except Exception:  # pragma: no cover - optional acceleration dependency
    torch = None


def scalar_to_float(value) -> float:
    """Read a scalar from NumPy or Torch tensors without leaking tensor types into routers."""
    if hasattr(value, "detach"):
        return float(value.detach().cpu().item())
    return float(value)


class SWEModel:
    """A lightweight 2D shallow-water prototype for flood warning workflows."""

    def __init__(self, rows: int, cols: int, dx: float, dy: float, dam_config: Dict | None = None):
        self.rows = rows
        self.cols = cols
        self.dx = dx
        self.dy = dy
        self.g = 9.81
        self.dam_config = dam_config or {}
        self.engine_name = "numpy_swe_runtime"

        self.raw_dem: np.ndarray | None = None
        self.dem = self._init_dem()
        self.h = np.zeros((rows, cols), dtype=np.float32)
        self.u = np.zeros((rows, cols), dtype=np.float32)
        self.v = np.zeros((rows, cols), dtype=np.float32)
        self.time_step = 0
        self.total_time = 0.0

        self._init_water()
        self.baseline_h = self.h.copy()

    def _dam_row(self) -> int:
        return int(np.clip(self.dam_config.get("dam_row", 9), 2, self.rows - 4))

    def _gate_slice(self) -> slice:
        start = int(np.clip(self.dam_config.get("gate_start_col", int(self.cols * 0.35)), 1, self.cols - 2))
        end = int(np.clip(self.dam_config.get("gate_end_col", int(self.cols * 0.65)), start + 1, self.cols - 1))
        return slice(start, end)

    def _init_dem(self) -> np.ndarray:
        if self.dam_config.get("case_id") == "oroville_dam":
            return self._init_oroville_dem()

        # Try to load from pre-generated DEM grid (e.g. Sanggan River)
        cache_path = self.dam_config.get("dem_grid_path")
        if cache_path:
            cached_dem = load_dem_grid_cache(cache_path, self.rows, self.cols)
            if cached_dem is not None:
                self.raw_dem = cached_dem.copy()
                return self._apply_sanggan_hydraulic_features(cached_dem)

        dem = np.zeros((self.rows, self.cols), dtype=np.float32)
        dam_row = self._dam_row()
        gate_slice = self._gate_slice()
        crest = float(self.dam_config.get("crest_elevation_m", 42.0))

        for i in range(self.rows):
            for j in range(self.cols):
                if i < dam_row:
                    reservoir_depth_bias = (dam_row - i) * 0.7
                    side_bias = abs(j - self.cols / 2.0) / (self.cols / 2.0)
                    dem[i, j] = 27.5 + side_bias * 6 + reservoir_depth_bias * 0.45
                else:
                    downstream_drop = (i - dam_row) * 0.85
                    side_bias = abs(j - self.cols / 2.0) / (self.cols / 2.0)
                    dem[i, j] = 18.0 + downstream_drop + side_bias * 4.5

        dam_body_start = max(0, dam_row - 1)
        dam_body_end = min(self.rows, dam_row + 1)
        dem[dam_body_start:dam_body_end, :] = np.maximum(dem[dam_body_start:dam_body_end, :], crest)
        dem[dam_body_start:dam_body_end, gate_slice] = crest - 6.0

        noise = np.random.normal(0, 0.15, (self.rows, self.cols))
        dem += noise.astype(np.float32)
        return np.clip(dem, 0, 100)

    def _init_oroville_dem(self) -> np.ndarray:
        """Build a DEM-derived local terrain from USGS 3DEP control points.

        The public 3DEP point-query service is too slow to call for every grid
        cell at app startup, so the case config stores sampled control points.
        We interpolate those points locally and then impose the engineered dam
        crest and river channel constraints needed by the warning model.
        """

        cache_path = self.dam_config.get("dem_grid_path")
        cached_dem = load_dem_grid_cache(cache_path, self.rows, self.cols) if cache_path else None
        if cached_dem is not None:
            self.raw_dem = cached_dem.copy()
            return self._apply_oroville_hydraulic_features(cached_dem)

        raw_dem = self._build_oroville_control_point_dem()
        self.raw_dem = raw_dem.copy()
        return self._apply_oroville_hydraulic_features(raw_dem)

    def _build_oroville_control_point_dem(self) -> np.ndarray:
        control_points = self.dam_config.get("dem_control_points", [])
        dam_row = self._dam_row()
        gate_slice = self._gate_slice()
        dam_lat = float(self.dam_config.get("dam_lat", 39.537193))
        dam_lng = float(self.dam_config.get("dam_lng", -121.485565))

        base_lat = dam_lat + dam_row * 0.0055
        base_lng = dam_lng - ((gate_slice.start + gate_slice.stop) / 2.0) * 0.0065
        grid_dy = 0.0055
        grid_dx = 0.0065

        anchors: list[tuple[float, float, float]] = []
        for point in control_points:
            row = (base_lat - float(point["lat"])) / grid_dy
            col = (float(point["lng"]) - base_lng) / grid_dx
            anchors.append((row, col, float(point["elevation_m"])))

        if not anchors:
            return np.full((self.rows, self.cols), 52.0, dtype=np.float32)

        dem = np.zeros((self.rows, self.cols), dtype=np.float32)
        for row in range(self.rows):
            for col in range(self.cols):
                weighted_value = 0.0
                total_weight = 0.0
                for anchor_row, anchor_col, elevation in anchors:
                    distance = float(np.hypot(row - anchor_row, col - anchor_col))
                    weight = 1.0 / max(distance**2, 0.35)
                    weighted_value += elevation * weight
                    total_weight += weight
                dem[row, col] = weighted_value / max(total_weight, 1e-6)

        return dem.astype(np.float32)

    def _apply_oroville_hydraulic_features(self, source_dem: np.ndarray) -> np.ndarray:
        dem = source_dem.astype(np.float32).copy()
        dam_row = self._dam_row()
        gate_slice = self._gate_slice()
        crest = float(self.dam_config.get("crest_elevation_m", 281.0))

        # Carve a Feather River corridor from the dam toward Oroville and
        # Thermalito so released water has a physical path instead of spreading
        # uniformly across the whole DEM.
        river_center_cols = np.interp(
            np.arange(self.rows),
            [dam_row, 14, 19, self.rows - 1],
            [gate_slice.start + 1, 19, 8, 5],
        )
        for row in range(dam_row, self.rows):
            center_col = river_center_cols[row]
            for col in range(self.cols):
                distance = abs(col - center_col)
                if distance <= 2.0:
                    dem[row, col] -= (2.0 - distance) * 5.5
                elif distance <= 5.0:
                    dem[row, col] -= (5.0 - distance) * 1.2

        # Keep the reservoir side smoother and lower than surrounding ridges so
        # the upstream pool behaves like Lake Oroville instead of a mountain.
        for row in range(0, dam_row):
            for col in range(max(0, gate_slice.start - 7), self.cols):
                lake_bias = max(0.0, 1.0 - row / max(dam_row, 1))
                dem[row, col] = min(dem[row, col], 220.0 + lake_bias * 28.0 + abs(col - gate_slice.start) * 1.8)

        dam_body_start = max(0, dam_row - 1)
        dam_body_end = min(self.rows, dam_row + 1)
        dem[dam_body_start:dam_body_end, :] = np.maximum(dem[dam_body_start:dam_body_end, :], crest)
        dem[dam_body_start:dam_body_end, gate_slice] = min(crest - 22.0, float(np.mean(dem[dam_body_start:dam_body_end, gate_slice]) + 4.0))

        return np.clip(dem, 28.0, 620.0).astype(np.float32)

    def _apply_sanggan_hydraulic_features(self, source_dem: np.ndarray) -> np.ndarray:
        """Impose dam crest and river channel constraints on the Sanggan River DEM."""
        dem = source_dem.astype(np.float32).copy()
        dam_row = self._dam_row()
        gate_slice = self._gate_slice()
        crest = float(self.dam_config.get("crest_elevation_m", 1068.0))

        # Carve the main Sanggan River channel downstream of the dam
        river_center = self.cols // 2
        for row in range(dam_row, self.rows):
            for col in range(self.cols):
                dist = abs(col - river_center)
                if dist <= 2:
                    dem[row, col] -= (2.0 - dist) * 4.0
                elif dist <= 5:
                    dem[row, col] -= (5.0 - dist) * 0.8

        # Enforce dam crest
        dam_body_start = max(0, dam_row - 1)
        dam_body_end = min(self.rows, dam_row + 1)
        dem[dam_body_start:dam_body_end, :] = np.maximum(
            dem[dam_body_start:dam_body_end, :], crest
        )
        dem[dam_body_start:dam_body_end, gate_slice] = crest - 8.0

        return np.clip(dem, 990.0, 1340.0).astype(np.float32)

    def _init_water(self) -> None:
        dam_row = self._dam_row()
        reservoir_level = float(self.dam_config.get("initial_reservoir_level_m", 38.8))

        upstream_surface = np.maximum(reservoir_level - self.dem[:dam_row, :], 0)
        self.h[:dam_row, :] = upstream_surface.astype(np.float32)

        downstream_stage = float(self.dam_config.get("downstream_control_level_m", 18.5))
        downstream_surface = np.maximum(downstream_stage - self.dem[dam_row:, :], 0)
        self.h[dam_row:, :] = np.maximum(self.h[dam_row:, :], downstream_surface.astype(np.float32) * 0.18)

    def _apply_dam_boundary(self, dt: float, gate_release: float, downstream_stage: float) -> None:
        dam_row = self._dam_row()
        gate_slice = self._gate_slice()
        gate_width_m = max((gate_slice.stop - gate_slice.start) * self.dx, self.dx)

        if gate_release > 0:
            release_depth = (gate_release * dt) / max(gate_width_m * self.dy, 1.0)
            release_band = slice(dam_row, min(self.rows, dam_row + 2))
            self.h[release_band, gate_slice] += release_depth

        downstream_target = np.maximum(downstream_stage - self.dem[-2:, :], 0)
        self.h[-2:, :] = np.maximum(self.h[-2:, :], downstream_target.astype(np.float32))

    def step(
        self,
        dt: float,
        rainfall_rate: float = 0.0,
        upstream_inflow: float = 0.0,
        gate_release: float = 0.0,
        downstream_stage: float = 18.5,
    ) -> None:
        h_old = self.h.copy()
        u_old = self.u.copy()
        v_old = self.v.copy()

        self.h[:, :] += rainfall_rate * dt

        if upstream_inflow > 0:
            dam_row = self._dam_row()
            upstream_band = slice(0, max(2, min(dam_row, 4)))
            inflow_width = self.cols * self.dx
            inflow_depth = (upstream_inflow * dt) / max(inflow_width * self.dy, 1.0)
            self.h[upstream_band, :] += inflow_depth

        self._apply_dam_boundary(dt, gate_release, downstream_stage)

        h_surface = self.dem + self.h

        dh_dx = np.zeros_like(h_surface)
        dh_dx[:, :-1] = (h_surface[:, 1:] - h_surface[:, :-1]) / self.dx
        dh_dx[:, -1] = dh_dx[:, -2]

        dh_dy = np.zeros_like(h_surface)
        dh_dy[:-1, :] = (h_surface[1:, :] - h_surface[:-1, :]) / self.dy
        dh_dy[-1, :] = dh_dy[-2, :]

        ax = -self.g * dh_dx
        ay = -self.g * dh_dy

        manning_c = 0.03
        vel_mag = np.sqrt(u_old**2 + v_old**2) + 1e-6
        h_safe = np.maximum(h_old, 0.01)
        friction_coeff = (manning_c**2 * self.g) / (h_safe ** (1 / 3))
        fx = -friction_coeff * u_old * vel_mag
        fy = -friction_coeff * v_old * vel_mag

        small_vel_mask = vel_mag < 1e-5
        fx[small_vel_mask] = 0
        fy[small_vel_mask] = 0

        self.u = u_old + (ax + fx) * dt
        self.v = v_old + (ay + fy) * dt

        max_velocity = 3.0
        new_vel_mag = np.sqrt(self.u**2 + self.v**2)
        exceed = new_vel_mag > max_velocity
        if np.any(exceed):
            scale = max_velocity / (new_vel_mag[exceed] + 1e-10)
            self.u[exceed] *= scale
            self.v[exceed] *= scale

        flux_x = h_old * self.u
        flux_y = h_old * self.v

        dhu_dx = np.zeros_like(h_old)
        dhu_dy = np.zeros_like(h_old)

        dhu_dx[:, 1:-1] = (flux_x[:, 2:] - flux_x[:, :-2]) / (2 * self.dx)
        dhu_dx[:, 0] = (flux_x[:, 1] - flux_x[:, 0]) / self.dx
        dhu_dx[:, -1] = (flux_x[:, -1] - flux_x[:, -2]) / self.dx

        dhu_dy[1:-1, :] = (flux_y[2:, :] - flux_y[:-2, :]) / (2 * self.dy)
        dhu_dy[0, :] = (flux_y[1, :] - flux_y[0, :]) / self.dy
        dhu_dy[-1, :] = (flux_y[-1, :] - flux_y[-2, :]) / self.dy

        self.h = h_old - (dhu_dx + dhu_dy) * dt

        # Keep this warning-oriented prototype numerically bounded. When Numba
        # is installed this hot cleanup path is JIT-compiled; otherwise the
        # vectorized NumPy fallback keeps default installs lightweight.
        sanitized_by_numba = sanitize_numpy_state_inplace(self.h, self.u, self.v, max_depth=320.0, max_velocity=3.0)
        if not sanitized_by_numba:
            min_depth = 0.001
            dry_mask = self.h < min_depth
            self.h[dry_mask] = 0
            self.u[dry_mask] = 0
            self.v[dry_mask] = 0
            self.h = np.clip(self.h, 0, 320)
            self.u = np.nan_to_num(self.u, nan=0.0, posinf=0.0, neginf=0.0)
            self.v = np.nan_to_num(self.v, nan=0.0, posinf=0.0, neginf=0.0)

        self.time_step += 1
        self.total_time += dt

    def get_state(self) -> Dict[str, np.ndarray]:
        return {
            "h": self.h.copy(),
            "u": self.u.copy(),
            "v": self.v.copy(),
            "dem": self.dem.copy(),
            "water_surface": self.dem + self.h,
        }

    def get_flood_grid(self, base_lat: float, base_lng: float, dx_deg: float, dy_deg: float) -> List[Dict]:
        grid: List[Dict] = []
        for i in range(self.rows):
            for j in range(self.cols):
                lat = base_lat - i * dy_deg
                lng = base_lng + j * dx_deg
                excess_depth = max(float(self.h[i, j] - self.baseline_h[i, j]), 0.0)
                vel_mag = np.sqrt(self.u[i, j] ** 2 + self.v[i, j] ** 2)
                # Reservoir pool water upstream of the dam is normal operating
                # storage, not downstream flood inundation.
                flooded = excess_depth > 0.01 and i >= self._dam_row()

                grid.append(
                    {
                        "lat": float(lat),
                        "lng": float(lng),
                        "depth": float(excess_depth),
                        "velocity_u": float(self.u[i, j]),
                        "velocity_v": float(self.v[i, j]),
                        "velocity_mag": float(vel_mag),
                        "dem": float(self.dem[i, j]),
                        "water_surface": float(self.dem[i, j] + self.h[i, j]),
                        "flooded": bool(flooded),
                    }
                )

        return grid

    def reset(self) -> None:
        self.h = np.zeros((self.rows, self.cols), dtype=np.float32)
        self.u = np.zeros((self.rows, self.cols), dtype=np.float32)
        self.v = np.zeros((self.rows, self.cols), dtype=np.float32)
        self.time_step = 0
        self.total_time = 0.0
        self.dem = self._init_dem()
        self._init_water()
        self.baseline_h = self.h.copy()


class TensorSWEModel:
    """Torch tensor SWE baseline with CFL time step and RK2 integration.

    This class is intentionally separate from the UI-facing SWEModel. It gives
    the project a measurable numerical baseline before swapping the runtime
    model onto CUDA.
    """

    def __init__(self, rows: int, cols: int, dx: float, dy: float, dam_config: Dict | None = None, device: str = "auto"):
        if torch is None:
            raise ImportError("TensorSWEModel requires torch. Install torch or use SWEModel.")

        self.rows = rows
        self.cols = cols
        self.dx = float(dx)
        self.dy = float(dy)
        self.g = 9.81
        self.dam_config = dam_config or {}
        self.device = self._resolve_device(device)
        self.engine_name = f"torch_tensor_{self.device.type}"
        self.dtype = torch.float32

        self.dem = self._init_dem()
        self.h = torch.zeros((rows, cols), dtype=self.dtype, device=self.device)
        self.u = torch.zeros((rows, cols), dtype=self.dtype, device=self.device)
        self.v = torch.zeros((rows, cols), dtype=self.dtype, device=self.device)
        self.time_step = 0
        self.total_time = 0.0

        self._init_water()
        self.baseline_h = self.h.clone()

    def _resolve_device(self, device: str):
        if device == "auto":
            return torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if device == "cuda" and not torch.cuda.is_available():
            return torch.device("cpu")
        return torch.device(device)

    def _dam_row(self) -> int:
        return int(np.clip(self.dam_config.get("dam_row", max(2, self.rows // 3)), 2, self.rows - 4))

    def _gate_slice(self) -> slice:
        start = int(np.clip(self.dam_config.get("gate_start_col", int(self.cols * 0.4)), 1, self.cols - 2))
        end = int(np.clip(self.dam_config.get("gate_end_col", int(self.cols * 0.6)), start + 1, self.cols - 1))
        return slice(start, end)

    def _init_dem(self):
        row_axis = torch.arange(self.rows, dtype=self.dtype, device=self.device).view(-1, 1)
        col_axis = torch.arange(self.cols, dtype=self.dtype, device=self.device).view(1, -1)
        dam_row = self._dam_row()
        gate_slice = self._gate_slice()
        crest = float(self.dam_config.get("crest_elevation_m", 42.0))

        side_bias = torch.abs(col_axis - (self.cols - 1) / 2.0) / max((self.cols - 1) / 2.0, 1.0)
        downstream_slope = torch.clamp(row_axis - dam_row, min=0.0) * 0.18
        upstream_basin = torch.clamp(dam_row - row_axis, min=0.0) * 0.08
        dem = 18.0 + downstream_slope + side_bias * 3.2 + upstream_basin

        river_center = (self.cols - 1) / 2.0 + torch.clamp(row_axis - dam_row, min=0.0) * 0.08
        river_distance = torch.abs(col_axis - river_center)
        dem = dem - torch.clamp(3.0 - river_distance, min=0.0) * 0.34

        dam_body_start = max(0, dam_row - 1)
        dam_body_end = min(self.rows, dam_row + 1)
        dem[dam_body_start:dam_body_end, :] = torch.maximum(
            dem[dam_body_start:dam_body_end, :],
            torch.tensor(crest, dtype=self.dtype, device=self.device),
        )
        dem[dam_body_start:dam_body_end, gate_slice] = crest - 4.5

        return torch.clamp(dem, min=0.0).to(dtype=self.dtype)

    def _init_water(self) -> None:
        dam_row = self._dam_row()
        reservoir_level = float(self.dam_config.get("initial_reservoir_level_m", 38.0))
        downstream_stage = float(self.dam_config.get("downstream_control_level_m", 18.5))

        self.h[:dam_row, :] = torch.clamp(reservoir_level - self.dem[:dam_row, :], min=0.0)
        self.h[dam_row:, :] = torch.clamp(downstream_stage - self.dem[dam_row:, :], min=0.0) * 0.15

    def _apply_external_forcing(
        self,
        h,
        dt: float,
        rainfall_rate: float,
        upstream_inflow: float,
        gate_release: float,
        downstream_stage: float,
    ):
        h_next = h.clone()
        dam_row = self._dam_row()
        gate_slice = self._gate_slice()

        if rainfall_rate > 0:
            h_next = h_next + float(rainfall_rate) * dt

        if upstream_inflow > 0:
            upstream_band = slice(0, max(2, min(dam_row, 4)))
            inflow_depth = (float(upstream_inflow) * dt) / max(self.cols * self.dx * self.dy, 1.0)
            h_next[upstream_band, :] = h_next[upstream_band, :] + inflow_depth

        if gate_release > 0:
            gate_width = max((gate_slice.stop - gate_slice.start) * self.dx, self.dx)
            release_depth = (float(gate_release) * dt) / max(gate_width * self.dy, 1.0)
            release_band = slice(dam_row, min(self.rows, dam_row + 2))
            h_next[release_band, gate_slice] = h_next[release_band, gate_slice] + release_depth

        downstream_target = torch.clamp(float(downstream_stage) - self.dem[-2:, :], min=0.0)
        h_next[-2:, :] = torch.maximum(h_next[-2:, :], downstream_target)
        return h_next

    def _gradient_x(self, values):
        grad = torch.zeros_like(values)
        grad[:, 1:-1] = (values[:, 2:] - values[:, :-2]) / (2.0 * self.dx)
        grad[:, 0] = (values[:, 1] - values[:, 0]) / self.dx
        grad[:, -1] = (values[:, -1] - values[:, -2]) / self.dx
        return grad

    def _gradient_y(self, values):
        grad = torch.zeros_like(values)
        grad[1:-1, :] = (values[2:, :] - values[:-2, :]) / (2.0 * self.dy)
        grad[0, :] = (values[1, :] - values[0, :]) / self.dy
        grad[-1, :] = (values[-1, :] - values[-2, :]) / self.dy
        return grad

    def _rhs(self, h, u, v):
        h_safe = torch.clamp(h, min=1e-4)
        surface = self.dem + h

        flux_x = h * u
        flux_y = h * v
        dh_dt = -(self._gradient_x(flux_x) + self._gradient_y(flux_y))

        velocity_mag = torch.sqrt(u * u + v * v + 1e-8)
        manning_n = float(self.dam_config.get("manning_n", 0.03))
        friction = (manning_n**2 * self.g) / torch.pow(h_safe, 1.0 / 3.0)
        du_dt = -self.g * self._gradient_x(surface) - friction * u * velocity_mag
        dv_dt = -self.g * self._gradient_y(surface) - friction * v * velocity_mag

        dry = h <= 1e-4
        du_dt = torch.where(dry, torch.zeros_like(du_dt), du_dt)
        dv_dt = torch.where(dry, torch.zeros_like(dv_dt), dv_dt)
        return dh_dt, du_dt, dv_dt

    def _sanitize_state(self) -> None:
        min_depth = 0.0
        max_depth = float(self.dam_config.get("max_depth_m", 320.0))
        max_velocity = float(self.dam_config.get("max_velocity_ms", 6.0))

        self.h = torch.nan_to_num(torch.clamp(self.h, min=min_depth, max=max_depth), nan=0.0, posinf=max_depth, neginf=0.0)
        self.u = torch.nan_to_num(self.u, nan=0.0, posinf=0.0, neginf=0.0)
        self.v = torch.nan_to_num(self.v, nan=0.0, posinf=0.0, neginf=0.0)

        velocity_mag = torch.sqrt(self.u * self.u + self.v * self.v + 1e-8)
        scale = torch.clamp(max_velocity / torch.clamp(velocity_mag, min=1e-6), max=1.0)
        self.u = self.u * scale
        self.v = self.v * scale

        dry = self.h <= 1e-4
        self.u = torch.where(dry, torch.zeros_like(self.u), self.u)
        self.v = torch.where(dry, torch.zeros_like(self.v), self.v)

    def compute_dt(self, cfl: float = 0.4) -> float:
        h_safe = torch.clamp(self.h, min=1e-4)
        wave_speed = torch.sqrt(self.g * h_safe)
        max_speed_x = torch.max(torch.abs(self.u) + wave_speed)
        max_speed_y = torch.max(torch.abs(self.v) + wave_speed)
        dt_x = self.dx / torch.clamp(max_speed_x, min=1e-6)
        dt_y = self.dy / torch.clamp(max_speed_y, min=1e-6)
        dt = float(cfl) * float(torch.minimum(dt_x, dt_y).detach().cpu())
        return max(dt, 1e-6)

    def step_rk2(
        self,
        dt: float | None = None,
        rainfall_rate: float = 0.0,
        upstream_inflow: float = 0.0,
        gate_release: float = 0.0,
        downstream_stage: float = 18.5,
    ) -> None:
        step_dt = float(dt if dt is not None else self.compute_dt())
        h0 = self._apply_external_forcing(self.h, step_dt, rainfall_rate, upstream_inflow, gate_release, downstream_stage)
        u0 = self.u.clone()
        v0 = self.v.clone()

        dh1, du1, dv1 = self._rhs(h0, u0, v0)
        h1 = h0 + step_dt * dh1
        u1 = u0 + step_dt * du1
        v1 = v0 + step_dt * dv1

        dh2, du2, dv2 = self._rhs(h1, u1, v1)
        self.h = 0.5 * (h0 + h1 + step_dt * dh2)
        self.u = 0.5 * (u0 + u1 + step_dt * du2)
        self.v = 0.5 * (v0 + v1 + step_dt * dv2)
        self._sanitize_state()

        self.time_step += 1
        self.total_time += step_dt

    def step(self, *args, **kwargs) -> None:
        self.step_rk2(*args, **kwargs)

    def get_state(self) -> Dict[str, np.ndarray]:
        h = self.h.detach().cpu().numpy().astype(np.float32, copy=True)
        u = self.u.detach().cpu().numpy().astype(np.float32, copy=True)
        v = self.v.detach().cpu().numpy().astype(np.float32, copy=True)
        dem = self.dem.detach().cpu().numpy().astype(np.float32, copy=True)
        return {
            "h": h,
            "u": u,
            "v": v,
            "dem": dem,
            "water_surface": dem + h,
        }

    def get_flood_grid(self, base_lat: float, base_lng: float, dx_deg: float, dy_deg: float) -> List[Dict]:
        state = self.get_state()
        h = state["h"]
        u = state["u"]
        v = state["v"]
        dem = state["dem"]
        baseline_h = self.baseline_h.detach().cpu().numpy().astype(np.float32, copy=False)

        grid: List[Dict] = []
        dam_row = self._dam_row()
        for i in range(self.rows):
            for j in range(self.cols):
                lat = base_lat - i * dy_deg
                lng = base_lng + j * dx_deg
                excess_depth = max(float(h[i, j] - baseline_h[i, j]), 0.0)
                vel_mag = float(np.sqrt(u[i, j] ** 2 + v[i, j] ** 2))
                flooded = excess_depth > 0.01 and i >= dam_row

                grid.append(
                    {
                        "lat": float(lat),
                        "lng": float(lng),
                        "depth": float(excess_depth),
                        "velocity_u": float(u[i, j]),
                        "velocity_v": float(v[i, j]),
                        "velocity_mag": vel_mag,
                        "dem": float(dem[i, j]),
                        "water_surface": float(dem[i, j] + h[i, j]),
                        "flooded": bool(flooded),
                    }
                )

        return grid

    def reset(self) -> None:
        self.h = torch.zeros((self.rows, self.cols), dtype=self.dtype, device=self.device)
        self.u = torch.zeros((self.rows, self.cols), dtype=self.dtype, device=self.device)
        self.v = torch.zeros((self.rows, self.cols), dtype=self.dtype, device=self.device)
        self.time_step = 0
        self.total_time = 0.0
        self.dem = self._init_dem()
        self._init_water()
        self.baseline_h = self.h.clone()

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


class SWEModel:
    """A lightweight 2D shallow-water prototype for flood warning workflows."""

    def __init__(self, rows: int, cols: int, dx: float, dy: float, dam_config: Dict | None = None):
        self.rows = rows
        self.cols = cols
        self.dx = dx
        self.dy = dy
        self.g = 9.81
        self.dam_config = dam_config or {}

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

        min_depth = 0.001
        dry_mask = self.h < min_depth
        self.h[dry_mask] = 0
        self.u[dry_mask] = 0
        self.v[dry_mask] = 0
        # Keep this warning-oriented prototype numerically bounded. Without a
        # full CFL-controlled solver, extreme scenario inputs can otherwise
        # produce non-physical depths that make the UI and risk logic unusable.
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

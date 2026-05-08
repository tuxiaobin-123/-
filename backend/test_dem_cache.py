# -*- coding: utf-8 -*-
"""
DEM cache behavior tests for the dam case model.
"""

import tempfile
from pathlib import Path

import numpy as np

from models.dem_cache import load_dem_grid_cache
from models.hydraulic import SWEModel


def test_load_dem_grid_cache_returns_expected_matrix() -> None:
    tmp_dir = tempfile.TemporaryDirectory()
    cache_path = Path(tmp_dir.name) / "dem_cache.json"
    cache_path.write_text(
        """
        {
          "case_id": "oroville_dam",
          "rows": 2,
          "cols": 3,
          "base_lat": 39.59,
          "base_lng": -121.67,
          "dx_deg": 0.0065,
          "dy_deg": 0.0055,
          "elevation_m": [[101.0, 102.5, 103.0], [98.0, 99.5, 100.0]]
        }
        """,
        encoding="utf-8",
    )

    dem = load_dem_grid_cache(cache_path, rows=2, cols=3)

    assert dem.shape == (2, 3)
    assert dem.dtype == np.float32
    assert float(dem[0, 1]) == 102.5


def test_load_dem_grid_cache_supports_legacy_point_records() -> None:
    tmp_dir = tempfile.TemporaryDirectory()
    cache_path = Path(tmp_dir.name) / "legacy_dem_cache.json"
    cache_path.write_text(
        """
        [
          {"row": 0, "col": 0, "elevation_m": 101.0},
          {"row": 0, "col": 1, "elevation_m": 102.5},
          {"row": 1, "col": 0, "elevation_m": 98.0},
          {"row": 1, "col": 1, "elevation_m": 99.5}
        ]
        """,
        encoding="utf-8",
    )

    dem = load_dem_grid_cache(cache_path, rows=2, cols=2)

    assert dem.shape == (2, 2)
    assert dem.dtype == np.float32
    assert float(dem[1, 0]) == 98.0


def test_swe_model_prefers_valid_dem_cache() -> None:
    tmp_dir = tempfile.TemporaryDirectory()
    cache_path = Path(tmp_dir.name) / "oroville_dem_cache.json"
    cached_dem = np.linspace(60.0, 140.0, 30 * 40, dtype=np.float32).reshape(30, 40)
    cache_path.write_text(
        """
        {
          "case_id": "oroville_dam",
          "rows": 30,
          "cols": 40,
          "base_lat": 39.59,
          "base_lng": -121.67,
          "dx_deg": 0.0065,
          "dy_deg": 0.0055,
          "elevation_m": %s
        }
        """
        % cached_dem.tolist(),
        encoding="utf-8",
    )

    model = SWEModel(
        rows=30,
        cols=40,
        dx=721.5,
        dy=610.5,
        dam_config={
            "case_id": "oroville_dam",
            "dem_grid_path": str(cache_path),
            "dam_row": 10,
            "gate_start_col": 25,
            "gate_end_col": 32,
            "crest_elevation_m": 281.0,
            "initial_reservoir_level_m": 266.0,
            "downstream_control_level_m": 52.0,
        },
    )

    assert np.allclose(model.raw_dem, cached_dem)
    assert np.any(model.dem != cached_dem)


if __name__ == "__main__":
    test_load_dem_grid_cache_returns_expected_matrix()
    test_swe_model_prefers_valid_dem_cache()
    print("DEM cache tests passed")

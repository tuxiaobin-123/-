# -*- coding: utf-8 -*-
"""
DEM grid cache helpers.

The cache format is intentionally plain JSON so this Windows project can load a
local DEM raster without adding GDAL/rasterio as a deployment dependency.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def _resolve_cache_path(cache_path: str | Path) -> Path:
    path = Path(cache_path)
    if path.exists() or path.is_absolute():
        return path

    backend_dir = Path(__file__).resolve().parents[1]
    repo_dir = backend_dir.parent
    for candidate in (backend_dir / path, repo_dir / path):
        if candidate.exists():
            return candidate

    return path


def load_dem_grid_cache(cache_path: str | Path, rows: int, cols: int) -> np.ndarray | None:
    """Load a cached DEM grid if it exists and matches the requested shape."""

    path = _resolve_cache_path(cache_path)
    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    if int(payload.get("rows", -1)) != rows or int(payload.get("cols", -1)) != cols:
        return None

    elevation = np.asarray(payload.get("elevation_m", []), dtype=np.float32)
    if elevation.shape != (rows, cols):
        return None

    if not np.isfinite(elevation).all():
        return None

    return elevation

# -*- coding: utf-8 -*-
"""
Build the local Oroville DEM grid cache.

This writes a complete 30 x 40 raster cache used by the hydraulic model at
startup. The current cache is generated from the stored USGS 3DEP EPQS control
points, then saved as a dense grid so runtime model initialization no longer
depends on sparse point interpolation.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import BASE_LAT, BASE_LNG, DAM_CONFIG, GRID_COLS, GRID_DX, GRID_DY, GRID_ROWS  # noqa: E402
from models.hydraulic import SWEModel  # noqa: E402


def build_cache_payload() -> dict:
    dam_config = {**DAM_CONFIG}
    dam_config.pop("dem_grid_path", None)

    model = SWEModel(
        rows=GRID_ROWS,
        cols=GRID_COLS,
        dx=GRID_DX * 111000,
        dy=GRID_DY * 111000,
        dam_config=dam_config,
    )

    raw_dem = model.raw_dem if model.raw_dem is not None else model.dem

    return {
        "case_id": DAM_CONFIG["case_id"],
        "name": DAM_CONFIG["name"],
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "source": "USGS 3DEP EPQS control points interpolated into local raster cache",
        "rows": GRID_ROWS,
        "cols": GRID_COLS,
        "base_lat": BASE_LAT,
        "base_lng": BASE_LNG,
        "dx_deg": GRID_DX,
        "dy_deg": GRID_DY,
        "elevation_unit": "m",
        "elevation_m": raw_dem.round(3).tolist(),
    }


def main() -> None:
    output_path = ROOT_DIR / DAM_CONFIG["dem_grid_path"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_cache_payload()
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote DEM cache: {output_path}")
    print(f"Grid: {payload['rows']} x {payload['cols']}")


if __name__ == "__main__":
    main()

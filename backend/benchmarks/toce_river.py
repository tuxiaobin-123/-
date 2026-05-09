# -*- coding: utf-8 -*-
"""Toce River dam-break benchmark scoring utilities.

Expected CSV columns:
- station_id
- observed_peak_depth_m
- simulated_peak_depth_m
- mike21_peak_depth_m
- observed_arrival_s
- simulated_arrival_s
- mike21_arrival_s
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Dict, Iterable, List


DEPTH_COLUMNS = ("observed_peak_depth_m", "simulated_peak_depth_m", "mike21_peak_depth_m")
ARRIVAL_COLUMNS = ("observed_arrival_s", "simulated_arrival_s", "mike21_arrival_s")


def _rmse(pairs: Iterable[tuple[float, float]]) -> float:
    errors = [(predicted - observed) ** 2 for observed, predicted in pairs]
    if not errors:
        return 0.0
    return math.sqrt(sum(errors) / len(errors))


def load_toce_comparison_csv(path: str | Path) -> List[Dict[str, float | str]]:
    rows: List[Dict[str, float | str]] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"station_id", *DEPTH_COLUMNS, *ARRIVAL_COLUMNS}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing Toce benchmark columns: {sorted(missing)}")

        for row in reader:
            rows.append(
                {
                    "station_id": row["station_id"],
                    "observed_peak_depth_m": float(row["observed_peak_depth_m"]),
                    "simulated_peak_depth_m": float(row["simulated_peak_depth_m"]),
                    "mike21_peak_depth_m": float(row["mike21_peak_depth_m"]),
                    "observed_arrival_s": float(row["observed_arrival_s"]),
                    "simulated_arrival_s": float(row["simulated_arrival_s"]),
                    "mike21_arrival_s": float(row["mike21_arrival_s"]),
                }
            )
    return rows


def score_toce_benchmark(rows: List[Dict[str, float | str]]) -> Dict:
    depth_model_pairs = [
        (float(row["observed_peak_depth_m"]), float(row["simulated_peak_depth_m"]))
        for row in rows
    ]
    depth_mike21_pairs = [
        (float(row["observed_peak_depth_m"]), float(row["mike21_peak_depth_m"]))
        for row in rows
    ]
    arrival_model_pairs = [
        (float(row["observed_arrival_s"]), float(row["simulated_arrival_s"]))
        for row in rows
    ]
    arrival_mike21_pairs = [
        (float(row["observed_arrival_s"]), float(row["mike21_arrival_s"]))
        for row in rows
    ]

    return {
        "benchmark": "Toce River dam-break",
        "station_count": len(rows),
        "metrics": {
            "peak_depth_rmse_m": {
                "this_model": round(_rmse(depth_model_pairs), 4),
                "mike21": round(_rmse(depth_mike21_pairs), 4),
            },
            "arrival_time_rmse_s": {
                "this_model": round(_rmse(arrival_model_pairs), 4),
                "mike21": round(_rmse(arrival_mike21_pairs), 4),
            },
        },
        "rows": rows,
    }


def score_toce_csv(path: str | Path) -> Dict:
    return score_toce_benchmark(load_toce_comparison_csv(path))

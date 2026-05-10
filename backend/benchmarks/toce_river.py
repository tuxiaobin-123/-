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
import io
import math
from pathlib import Path
from typing import Dict, Iterable, List


DEPTH_COLUMNS = ("observed_peak_depth_m", "simulated_peak_depth_m", "mike21_peak_depth_m")
ARRIVAL_COLUMNS = ("observed_arrival_s", "simulated_arrival_s", "mike21_arrival_s")
REQUIRED_COLUMNS = ("station_id", *DEPTH_COLUMNS, *ARRIVAL_COLUMNS)


def _rmse(pairs: Iterable[tuple[float, float]]) -> float:
    errors = [(predicted - observed) ** 2 for observed, predicted in pairs]
    if not errors:
        return 0.0
    return math.sqrt(sum(errors) / len(errors))


def _parse_toce_rows(reader: csv.DictReader) -> List[Dict[str, float | str]]:
    rows: List[Dict[str, float | str]] = []
    missing = set(REQUIRED_COLUMNS).difference(reader.fieldnames or [])
    if missing:
        raise ValueError(f"Missing Toce benchmark columns: {sorted(missing)}")

    for row in reader:
        if not row.get("station_id"):
            continue
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

    if not rows:
        raise ValueError("Toce benchmark CSV does not contain any data rows.")

    return rows


def load_toce_comparison_csv(path: str | Path) -> List[Dict[str, float | str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return _parse_toce_rows(reader)


def load_toce_comparison_text(csv_text: str) -> List[Dict[str, float | str]]:
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    return _parse_toce_rows(reader)


def write_toce_comparison_csv(rows: List[Dict[str, float | str]], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(REQUIRED_COLUMNS))
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row[column] for column in REQUIRED_COLUMNS})


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

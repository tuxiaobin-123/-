# -*- coding: utf-8 -*-
"""
Small real-data adapters for the Oroville prototype.

These functions intentionally keep the first integration thin: they prove that
the case can reach public hydrologic services, summarize the returned time
series, and cache successful payloads for repeatable demos.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

import httpx


USGS_IV_URL = "https://waterservices.usgs.gov/nwis/iv/"
CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "real_observations"


PARAMETER_LABELS = {
    "00060": "Discharge",
    "00065": "Gage height",
    "62614": "Lake/reservoir elevation",
    "72020": "Elevation",
}

OFFLINE_SEED_VALUES = {
    "11406800": {"station_name": "LK Oroville NR Oroville CA", "parameter_code": "62614", "latest_value": 266.0, "min": 264.8, "max": 267.2},
    "11406818": {"station_name": "Edward Hyatt PH Power Release", "parameter_code": "00060", "latest_value": 900.0, "min": 520.0, "max": 1480.0},
    "11407000": {"station_name": "FEATHER R A OROVILLE CA", "parameter_code": "00060", "latest_value": 710.0, "min": 430.0, "max": 1280.0},
    "11406870": {"station_name": "Thermalito Afterbay NR Oroville CA", "parameter_code": "00065", "latest_value": 40.5, "min": 39.8, "max": 41.4},
}


def _cache_path(name: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / name


def _write_cache(name: str, payload: Dict[str, Any]) -> None:
    _cache_path(name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_cache(name: str) -> Dict[str, Any] | None:
    path = _cache_path(name)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _summarize_values(values: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    parsed = []
    last_time = None
    last_value = None

    for item in values:
        numeric = _as_float(item.get("value"))
        if numeric is None:
            continue
        parsed.append(numeric)
        last_value = numeric
        last_time = item.get("dateTime")

    if not parsed:
        return {"count": 0, "latest_time": None, "latest_value": None, "min": None, "max": None}

    return {
        "count": len(parsed),
        "latest_time": last_time,
        "latest_value": round(last_value, 3) if last_value is not None else None,
        "min": round(min(parsed), 3),
        "max": round(max(parsed), 3),
    }


def summarize_usgs_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    series = payload.get("value", {}).get("timeSeries", [])
    summaries: List[Dict[str, Any]] = []

    for item in series:
        source = item.get("sourceInfo", {})
        variable = item.get("variable", {})
        site_codes = source.get("siteCode") or []
        variable_codes = variable.get("variableCode") or []
        values_blocks = item.get("values") or []
        raw_values = values_blocks[0].get("value", []) if values_blocks else []

        site_id = site_codes[0].get("value") if site_codes else "unknown"
        parameter_code = variable_codes[0].get("value") if variable_codes else "unknown"
        summary = _summarize_values(raw_values)

        summaries.append(
            {
                "provider": "USGS NWIS",
                "station_id": site_id,
                "station_name": source.get("siteName", site_id),
                "parameter_code": parameter_code,
                "parameter_name": PARAMETER_LABELS.get(parameter_code, variable.get("variableName", parameter_code)),
                **summary,
            }
        )

    return summaries


def build_offline_usgs_seed(station_ids: Iterable[str], error: Exception) -> Dict[str, Any]:
    series = []
    now = datetime.now(timezone.utc).isoformat()
    for station_id in station_ids:
        seed = OFFLINE_SEED_VALUES.get(station_id)
        if not seed:
            continue
        parameter_code = seed["parameter_code"]
        series.append(
            {
                "provider": "USGS NWIS offline seed",
                "station_id": station_id,
                "station_name": seed["station_name"],
                "parameter_code": parameter_code,
                "parameter_name": PARAMETER_LABELS.get(parameter_code, parameter_code),
                "count": 24,
                "latest_time": now,
                "latest_value": seed["latest_value"],
                "min": seed["min"],
                "max": seed["max"],
            }
        )

    return {
        "status": "offline_seed",
        "fetched_at": now,
        "endpoint": USGS_IV_URL,
        "series": series,
        "last_error": f"{type(error).__name__}: {error}",
    }


async def fetch_usgs_probe(
    station_ids: Iterable[str],
    parameter_codes: Iterable[str] = ("00060", "00065", "62614"),
    period: str = "P7D",
    timeout_seconds: float = 12.0,
) -> Dict[str, Any]:
    sites = ",".join(station_ids)
    parameters = ",".join(parameter_codes)
    cache_name = f"usgs_iv_{sites.replace(',', '_')}_{period}.json"

    params = {
        "format": "json",
        "sites": sites,
        "period": period,
        "parameterCd": parameters,
        "siteStatus": "all",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            response = await client.get(USGS_IV_URL, params=params)
            response.raise_for_status()
            raw_payload = response.json()

        payload = {
            "status": "live",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "endpoint": str(response.url),
            "series": summarize_usgs_payload(raw_payload),
        }
        _write_cache(cache_name, payload)
        return payload
    except Exception as error:
        cached = _read_cache(cache_name)
        if cached:
            cached["status"] = "cached"
            cached["last_error"] = str(error)
            return cached
        return build_offline_usgs_seed(station_ids, error)


def get_oroville_2017_event() -> Dict[str, Any]:
    return {
        "event_id": "oroville_2017_spillway_incident",
        "name": "2017 Oroville spillway incident replay seed",
        "period": {"start": "2017-02-06T00:00:00-08:00", "end": "2017-02-13T23:59:59-08:00"},
        "calibration_targets": [
            "Lake Oroville reservoir elevation trend",
            "Feather River downstream gage response",
            "inflow/outflow hydrograph timing",
            "known emergency spillway first overtopping window",
        ],
        "known_milestones": [
            {"time": "2017-02-07", "label": "Main spillway damage observed during high release operations"},
            {"time": "2017-02-11", "label": "Emergency spillway overtopping began for the first time"},
            {"time": "2017-02-12", "label": "Erosion downstream of the emergency spillway became a stability concern"},
        ],
        "starter_simulation": {
            "rainfall_mm_h": 82.0,
            "upstream_m3s": 3680.0,
            "gate_release_m3s": 1480.0,
            "downstream_level_m": 56.2,
            "reservoir_level_m": 274.8,
            "duration_hours": 72.0,
        },
        "limitations": [
            "This replay is a calibration scaffold, not a certified reconstruction.",
            "The first pass calibrates hydrograph timing and reservoir/downstream response before 2D inundation depth.",
        ],
    }

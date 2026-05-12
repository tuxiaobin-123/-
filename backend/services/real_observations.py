# -*- coding: utf-8 -*-
"""
Small real-data adapters for dam-case prototypes.

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

DATA_SOURCE_REGISTRY = {
    "usgs_nwis_iv": {
        "provider": "USGS NWIS Instantaneous Values",
        "endpoint": USGS_IV_URL,
        "role": "reservoir, release, downstream gage, and stage forcing observations",
    },
    "dem_grid_cache": {
        "provider": "Local dam-case DEM grid cache",
        "role": "terrain base for the shallow-water grid before GeoTIFF import",
    },
    "oroville_2017": {
        "provider": "Oroville 2017 replay seed",
        "role": "historical calibration scaffold for hydrograph timing and warning milestones",
    },
    "sanggan_1996": {
        "provider": "Sanggan River Huairen 1996 historical flood seed",
        "role": "historical replay scaffold for Huairen flood warning calibration",
    },
}

OFFLINE_SEED_VALUES = {
    "11406800": {"station_name": "LK Oroville NR Oroville CA", "parameter_code": "62614", "latest_value": 266.0, "min": 264.8, "max": 267.2},
    "11406818": {"station_name": "Edward Hyatt PH Power Release", "parameter_code": "00060", "latest_value": 900.0, "min": 520.0, "max": 1480.0},
    "11407000": {"station_name": "FEATHER R A OROVILLE CA", "parameter_code": "00060", "latest_value": 710.0, "min": 430.0, "max": 1280.0},
    "11406870": {"station_name": "Thermalito Afterbay NR Oroville CA", "parameter_code": "00065", "latest_value": 40.5, "min": 39.8, "max": 41.4},
}

SANGGAN_SEED_VALUES = {
    "sgr_upstream": {"station_name": "桑干河上游入境站（应县-怀仁）", "parameter_code": "00060", "latest_value": 420.0, "min": 120.0, "max": 842.0},
    "sgr_huairen_main": {"station_name": "桑干河怀仁主站", "parameter_code": "00065", "latest_value": 1038.2, "min": 1035.0, "max": 1068.0},
    "sgr_south_tributary": {"station_name": "恢河支流汇入口", "parameter_code": "00060", "latest_value": 160.0, "min": 45.0, "max": 320.0},
    "sgr_downstream": {"station_name": "桑干河下游出境站（怀仁-山阴）", "parameter_code": "00065", "latest_value": 1018.0, "min": 1015.5, "max": 1032.0},
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
        "source": DATA_SOURCE_REGISTRY["usgs_nwis_iv"],
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
            "source": DATA_SOURCE_REGISTRY["usgs_nwis_iv"],
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


async def fetch_sanggan_probe(station_ids: Iterable[str]) -> Dict[str, Any]:
    """Return transparent local historical seeds for the Sanggan Huairen case."""
    now = datetime.now(timezone.utc).isoformat()
    series = []
    for station_id in station_ids:
        seed = SANGGAN_SEED_VALUES.get(station_id)
        if not seed:
            continue
        parameter_code = seed["parameter_code"]
        series.append(
            {
                "provider": "Sanggan River historical seed",
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
        "status": "historical_seed",
        "fetched_at": now,
        "endpoint": "local://sanggan-1996-huairen-historical-seed",
        "source": DATA_SOURCE_REGISTRY["sanggan_1996"],
        "series": series,
    }


def _clamp_score(value: float) -> int:
    return int(max(0, min(100, round(value))))


def _quality_grade(score: int) -> str:
    if score >= 80:
        return "trusted"
    if score >= 55:
        return "usable_with_review"
    if score >= 30:
        return "demo_only"
    return "blocked"


def _decision_status(grade: str) -> str:
    if grade == "trusted":
        return "auto_advisory_allowed"
    if grade in {"usable_with_review", "demo_only"}:
        return "human_review_required"
    return "blocked"


def build_data_quality_report(usgs_probe: Dict[str, Any], dem_status: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    """Score whether the current data chain is fit for operational-looking decisions."""
    usgs_status = usgs_probe.get("status", "unavailable")
    series = usgs_probe.get("series") or []
    sample_count = sum(int(item.get("count") or 0) for item in series)
    station_count = len({item.get("station_id") for item in series if item.get("station_id")})
    calibration_targets = event.get("calibration_targets") or []
    known_milestones = event.get("known_milestones") or []

    status_scores = {"live": 45, "cached": 32, "historical_seed": 28, "offline_seed": 18, "unavailable": 0}
    status_score = status_scores.get(usgs_status, 0)
    if usgs_status == "live":
        observation_score = min(25, sample_count / max(station_count * 24, 1) * 18)
    elif usgs_status == "cached":
        observation_score = min(20, sample_count / max(station_count * 24, 1) * 14)
    elif usgs_status == "historical_seed":
        observation_score = min(16, sample_count / max(station_count * 24, 1) * 12)
    elif usgs_status == "offline_seed":
        observation_score = 8 if series else 0
    else:
        observation_score = 0

    dem_score = 15 if dem_status.get("status") in {"cached", "loaded", "ready"} and dem_status.get("path") else 5
    event_score = 6 if calibration_targets else 0
    if known_milestones:
        event_score += 4
    provenance_score = 5 if usgs_probe.get("endpoint") and DATA_SOURCE_REGISTRY.get("usgs_nwis_iv") else 0

    checks = [
        {
            "name": "USGS观测连通性",
            "status": usgs_status,
            "score": _clamp_score(status_score),
            "evidence": f"{station_count} stations, {sample_count} samples",
        },
        {
            "name": "时序完整度",
            "status": "sufficient" if observation_score >= 18 else "limited",
            "score": _clamp_score(observation_score),
            "evidence": "live/cached data uses sample count; historical/offline seeds are capped for safety",
        },
        {
            "name": "DEM地形缓存",
            "status": dem_status.get("status", "unknown"),
            "score": _clamp_score(dem_score),
            "evidence": dem_status.get("path") or "DEM path missing",
        },
        {
            "name": "历史事件校准",
            "status": "available" if event_score else "missing",
            "score": _clamp_score(event_score),
            "evidence": f"{len(calibration_targets)} targets, {len(known_milestones)} milestones",
        },
        {
            "name": "来源可追溯",
            "status": "traceable" if provenance_score else "missing",
            "score": _clamp_score(provenance_score),
            "evidence": usgs_probe.get("endpoint") or "no endpoint recorded",
        },
    ]
    score = _clamp_score(sum(item["score"] for item in checks))
    grade = _quality_grade(score)

    return {
        "score": score,
        "grade": grade,
        "decision_status": _decision_status(grade),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "evidence_refs": [
            {
                "label": "Observation time series endpoint",
                "value": usgs_probe.get("endpoint", USGS_IV_URL),
                "provider": DATA_SOURCE_REGISTRY["usgs_nwis_iv"]["provider"],
            },
            {
                "label": "DEM grid cache",
                "value": dem_status.get("path") or "not configured",
                "provider": DATA_SOURCE_REGISTRY["dem_grid_cache"]["provider"],
            },
            {
                "label": "Historical replay event",
                "value": event.get("event_id", "unknown"),
                "provider": DATA_SOURCE_REGISTRY["sanggan_1996"]["provider"]
                if str(event.get("event_id", "")).startswith("sanggan_")
                else DATA_SOURCE_REGISTRY["oroville_2017"]["provider"],
            },
        ],
    }


def build_agent_evidence_chain(usgs_probe: Dict[str, Any], quality_report: Dict[str, Any], event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Explain which evidence each agent consumes and produces."""
    status = usgs_probe.get("status", "unavailable")
    grade = quality_report.get("grade", "blocked")
    score = int(quality_report.get("score") or 0)
    confidence = round(max(0.2, min(0.95, score / 100)), 2)
    audit_status = "review_required" if quality_report.get("decision_status") != "auto_advisory_allowed" else "auditable"
    calibration_text = f"{len(event.get('calibration_targets') or [])} calibration targets"

    return [
        {
            "agent": "communication",
            "input_evidence": ["user instruction", f"data quality grade={grade}", f"USGS status={status}"],
            "output_evidence": ["intent route", "target agent list", "human-review flag"],
            "confidence": confidence,
            "audit_status": audit_status,
        },
        {
            "agent": "simulation",
            "input_evidence": ["DEM grid cache", "rainfall boundary", "gate release boundary", "downstream control level"],
            "output_evidence": ["water depth grid", "velocity field", "flood extent"],
            "confidence": round(max(0.25, confidence - 0.04), 2),
            "audit_status": audit_status,
        },
        {
            "agent": "risk",
            "input_evidence": [f"USGS observation mode={status}", "simulation grid", "affected objects"],
            "output_evidence": ["risk probability band", "uncertainty label", "warning level"],
            "confidence": round(max(0.2, confidence - 0.08), 2),
            "audit_status": audit_status,
        },
        {
            "agent": "dispatch",
            "input_evidence": ["risk map", "shelter/resource points", "blocked/high-risk cells"],
            "output_evidence": ["A* route candidate", "ant-colony route alternative", "resource dispatch suggestion"],
            "confidence": round(max(0.2, confidence - 0.1), 2),
            "audit_status": audit_status,
        },
        {
            "agent": "evaluation",
            "input_evidence": ["dispatch plan", f"quality score={score}", calibration_text],
            "output_evidence": ["plan score", "replan decision", "explainable report skeleton"],
            "confidence": round(max(0.2, confidence - 0.06), 2),
            "audit_status": audit_status,
        },
    ]


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


def get_sanggan_1996_event() -> Dict[str, Any]:
    return {
        "event_id": "sanggan_1996_huairen_flood",
        "name": "1996 桑干河怀仁段历史洪水回放种子",
        "period": {"start": "1996-08-04T06:00:00+08:00", "end": "1996-08-07T23:59:59+08:00"},
        "calibration_targets": [
            "怀仁主站水位过程线",
            "上游入境洪峰流量",
            "恢河支流汇入时段",
            "桑干河大桥断面超警窗口",
        ],
        "known_milestones": [
            {"time": "1996-08-04", "label": "上游持续强降雨，入境流量开始快速抬升"},
            {"time": "1996-08-05", "label": "怀仁主站接近警戒水位，低洼区进入重点巡查"},
            {"time": "1996-08-06", "label": "洪峰过境，桑干河大桥与市区低洼点承压"},
        ],
        "starter_simulation": {
            "rainfall_mm_h": 78.0,
            "upstream_m3s": 842.0,
            "gate_release_m3s": 120.0,
            "downstream_level_m": 1032.0,
            "reservoir_level_m": 1058.0,
            "duration_hours": 48.0,
        },
        "limitations": [
            "This replay is a local historical scaffold, not a certified hydrologic reconstruction.",
            "The first pass aligns water-level trend, peak timing, and downstream warning objects before full 2D calibration.",
        ],
    }

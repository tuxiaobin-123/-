# -*- coding: utf-8 -*-
"""
Sensor data API routes.

Realtime sensor values are now sampled from the current SWE dam model when
available, instead of being generated independently from the simulation.
"""

from datetime import datetime, timedelta
from typing import Dict, List

import numpy as np
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from config import BASE_LAT, BASE_LNG, GRID_DX, GRID_DY, SENSOR_STATIONS

router = APIRouter(prefix="/api/sensors", tags=["sensors"])


class SensorReading(BaseModel):
    station_id: str
    name: str
    lat: float
    lng: float
    water_level: float
    rainfall: float
    flow_rate: float
    battery: float
    signal_quality: float
    last_update: str


class RealtimeSensorResponse(BaseModel):
    timestamp: str
    stations: List[SensorReading]


class StationInfo(BaseModel):
    station_id: str
    name: str
    lat: float
    lng: float
    type: str


class StationsListResponse(BaseModel):
    total_stations: int
    stations: List[StationInfo]


class HistoricalReading(BaseModel):
    timestamp: str
    water_level: float
    rainfall: float
    flow_rate: float
    battery: float


class StationHistoryResponse(BaseModel):
    station_id: str
    station_name: str
    hours: int
    readings: List[HistoricalReading]


def _station_grid_index(station_id: str, model) -> tuple[int, int]:
    station = SENSOR_STATIONS[station_id]
    row = int(round((BASE_LAT - station["lat"]) / GRID_DY))
    col = int(round((station["lng"] - BASE_LNG) / GRID_DX))
    row = int(np.clip(row, 0, model.rows - 1))
    col = int(np.clip(col, 0, model.cols - 1))
    return row, col


def _station_sampling_kernel(station_id: str) -> list[tuple[int, int, float]]:
    kernels = {
        "usgs_11406800": [(-2, 0, 1.6), (-1, 0, 1.4), (0, 0, 1.2), (1, 0, 0.7), (0, 1, 0.6), (0, -1, 0.6)],
        "usgs_11407000": [(-1, 0, 1.1), (0, 0, 1.4), (1, 0, 1.6), (2, 0, 1.2), (0, 1, 0.7), (0, -1, 0.7)],
        "usgs_11406870": [(0, 0, 1.4), (-1, 1, 1.0), (1, 1, 1.0), (0, 1, 0.9), (1, 0, 0.8), (-1, 0, 0.8)],
    }
    return kernels.get(
        station_id,
        [(0, 0, 1.5), (-1, 0, 1.0), (1, 0, 1.0), (0, -1, 0.9), (0, 1, 0.9), (-1, -1, 0.6), (1, 1, 0.6)],
    )


def _weighted_model_sample(model, row: int, col: int, station_id: str) -> tuple[float, float]:
    kernels = _station_sampling_kernel(station_id)
    weighted_level = 0.0
    weighted_flow = 0.0
    total_weight = 0.0

    for row_offset, col_offset, weight in kernels:
        sample_row = int(np.clip(row + row_offset, 0, model.rows - 1))
        sample_col = int(np.clip(col + col_offset, 0, model.cols - 1))
        local_level = float(model.dem[sample_row, sample_col] + model.h[sample_row, sample_col])
        local_flow = float(np.sqrt(model.u[sample_row, sample_col] ** 2 + model.v[sample_row, sample_col] ** 2))

        weighted_level += local_level * weight
        weighted_flow += local_flow * weight
        total_weight += weight

    if total_weight <= 0:
        return float(model.dem[row, col] + model.h[row, col]), float(np.sqrt(model.u[row, col] ** 2 + model.v[row, col] ** 2))

    return weighted_level / total_weight, weighted_flow / total_weight


def _sample_model_sensor_reading(station_id: str, request: Request) -> SensorReading | None:
    model = getattr(request.app.state, "swe_model", None)
    if model is None:
        return None

    station_info = SENSOR_STATIONS[station_id]
    row, col = _station_grid_index(station_id, model)

    water_level, flow_rate = _weighted_model_sample(model, row, col, station_id)

    request_rainfall = 0.0
    flood_module = getattr(request.app.state, "flood_router_state", None)
    if flood_module is not None:
        request_rainfall = float(getattr(flood_module, "rainfall_rate", 0.0))

    # 桑干河各站水力特性偏差（上游来流多、支流汇入、市区段、下游出境）
    station_bias = {
        "sgr_upstream":        {"level": 0.30, "flow": 0.08, "rain": 0.85},
        "sgr_huairen_main":    {"level": 0.05, "flow": 0.18, "rain": 1.0},
        "sgr_south_tributary": {"level": -0.20, "flow": 0.35, "rain": 1.15},
        "sgr_downstream":      {"level": -0.40, "flow": 0.22, "rain": 0.90},
    }.get(station_id, {"level": 0.0, "flow": 0.0, "rain": 1.0})

    water_level = max(0.0, water_level + station_bias["level"])
    flow_rate = max(0.0, flow_rate + station_bias["flow"])
    rainfall = max(0.0, request_rainfall * station_bias["rain"])

    # 桑干河各站合理水位范围（m，绝对高程）
    level_limits = {
        "sgr_upstream":        (1045.0, 1075.0),
        "sgr_huairen_main":    (1030.0, 1060.0),
        "sgr_south_tributary": (1022.0, 1048.0),
        "sgr_downstream":      (1008.0, 1030.0),
    }.get(station_id, (1010.0, 1070.0))

    if not np.isfinite(water_level):
        water_level = level_limits[0]
    if not np.isfinite(flow_rate):
        flow_rate = 0.0

    water_level = float(np.clip(water_level, level_limits[0], level_limits[1]))
    flow_rate = float(np.clip(flow_rate, 0.0, 8.0))

    battery = float(np.clip(97 - (datetime.now().hour / 24.0 * 4) + np.random.normal(0, 0.8), 20, 100))
    signal_quality = float(np.clip(90 - flow_rate * 2 + np.random.normal(0, 4), 25, 100))

    return SensorReading(
        station_id=station_id,
        name=station_info["name"],
        lat=station_info["lat"],
        lng=station_info["lng"],
        water_level=round(water_level, 2),
        rainfall=round(rainfall, 2),
        flow_rate=round(flow_rate, 3),
        battery=round(battery, 1),
        signal_quality=round(signal_quality, 1),
        last_update=datetime.now().isoformat(),
    )


def _generate_fallback_sensor_reading(station_id: str) -> SensorReading:
    station_info = SENSOR_STATIONS[station_id]
    # 桑干河各站正常水位（绝对高程，m）
    base_levels = {
        "sgr_upstream":        1058.0,
        "sgr_huairen_main":    1042.0,
        "sgr_south_tributary": 1033.0,
        "sgr_downstream":      1016.0,
    }
    base_level = base_levels.get(station_id, 1035.0)
    now = datetime.now()
    hours_since_midnight = now.hour + now.minute / 60.0
    trend = np.sin(hours_since_midnight / 6.0) * 0.8
    water_level = float(np.clip(base_level + trend + np.random.normal(0, 0.15), 0, 15))
    rainfall = float(np.random.exponential(25) if np.random.rand() > 0.7 else 0)
    flow_rate = float(np.clip(0.8 + water_level * 0.06 + np.random.normal(0, 0.05), 0, 8))
    battery = float(np.clip(95 - (hours_since_midnight / 24 * 5) + np.random.normal(0, 2), 10, 100))
    signal_quality = float(np.clip(75 + np.random.normal(0, 10), 20, 100))

    return SensorReading(
        station_id=station_id,
        name=station_info["name"],
        lat=station_info["lat"],
        lng=station_info["lng"],
        water_level=round(water_level, 2),
        rainfall=round(rainfall, 2),
        flow_rate=round(flow_rate, 3),
        battery=round(battery, 1),
        signal_quality=round(signal_quality, 1),
        last_update=datetime.now().isoformat(),
    )


def generate_sensor_reading(station_id: str, request: Request | None = None) -> SensorReading:
    if station_id not in SENSOR_STATIONS:
        raise ValueError(f"Unknown station_id: {station_id}")

    if request is not None:
        model_reading = _sample_model_sensor_reading(station_id, request)
        if model_reading is not None:
            return model_reading

    return _generate_fallback_sensor_reading(station_id)


@router.get("/realtime", response_model=RealtimeSensorResponse)
async def get_realtime_sensors(request: Request) -> RealtimeSensorResponse:
    readings = [generate_sensor_reading(station_id, request) for station_id in SENSOR_STATIONS]
    return RealtimeSensorResponse(timestamp=datetime.now().isoformat(), stations=readings)


@router.get("/stations", response_model=StationsListResponse)
async def get_all_stations() -> StationsListResponse:
    stations = [
        StationInfo(
            station_id=station_id,
            name=info["name"],
            lat=info["lat"],
            lng=info["lng"],
            type=info["type"],
        )
        for station_id, info in SENSOR_STATIONS.items()
    ]
    return StationsListResponse(total_stations=len(stations), stations=stations)


@router.get("/realtime/{station_id}", response_model=SensorReading)
async def get_station_realtime(station_id: str, request: Request) -> SensorReading:
    if station_id not in SENSOR_STATIONS:
        raise HTTPException(status_code=404, detail=f"Station {station_id} not found")
    return generate_sensor_reading(station_id, request)


@router.get("/history/{station_id}", response_model=StationHistoryResponse)
async def get_station_history(station_id: str, request: Request, hours: int = 48) -> StationHistoryResponse:
    if station_id not in SENSOR_STATIONS:
        raise HTTPException(status_code=404, detail=f"Station {station_id} not found")

    if hours < 1 or hours > 720:
        raise HTTPException(status_code=400, detail="Hours must be between 1 and 720")

    station_info = SENSOR_STATIONS[station_id]
    readings: List[HistoricalReading] = []
    now = datetime.now()

    # Prefer model-driven history recorded by the flood router when available.
    flood_module = getattr(request.app.state, "flood_router_state", None)
    flood_history = getattr(flood_module, "history", []) if flood_module is not None else []
    station_entries = [entry for entry in flood_history if entry["station_id"] == station_id]

    if station_entries:
        readings = [
            HistoricalReading(
                timestamp=entry["timestamp"],
                water_level=entry["water_level"],
                rainfall=entry["rainfall"],
                flow_rate=entry["flow_rate"],
                battery=92.0,
            )
            for entry in station_entries[-hours:]
        ]
    else:
        base_level = {
            "sgr_upstream":        1058.0,
            "sgr_huairen_main":    1042.0,
            "sgr_south_tributary": 1033.0,
            "sgr_downstream":      1016.0,
        }.get(station_id, 1035.0)

        for i in range(hours):
            timestamp = now - timedelta(hours=hours - i - 1)
            hours_since_midnight = timestamp.hour + timestamp.minute / 60.0
            trend = np.sin(hours_since_midnight / 6.0) * 0.8
            water_level = float(np.clip(base_level + trend + np.random.normal(0, 0.15), base_level - 5, base_level + 8))
            rainfall = float(np.random.exponential(20) if np.random.rand() > 0.75 else 0)
            flow_rate = float(np.clip(0.8 + water_level * 0.06 + np.random.normal(0, 0.05), 0, 8))
            battery = float(np.clip(95 - (i / hours * 10) + np.random.normal(0, 1), 20, 100))

            readings.append(
                HistoricalReading(
                    timestamp=timestamp.isoformat(),
                    water_level=round(water_level, 2),
                    rainfall=round(rainfall, 2),
                    flow_rate=round(flow_rate, 3),
                    battery=round(battery, 1),
                )
            )

    return StationHistoryResponse(
        station_id=station_id,
        station_name=station_info["name"],
        hours=hours,
        readings=readings,
    )


@router.get("/stats/{station_id}")
async def get_station_statistics(station_id: str, request: Request, hours: int = 48) -> Dict:
    if station_id not in SENSOR_STATIONS:
        raise HTTPException(status_code=404, detail=f"Station {station_id} not found")

    history = await get_station_history(station_id, request, hours)
    levels = [reading.water_level for reading in history.readings]
    rainfalls = [reading.rainfall for reading in history.readings]

    return {
        "station_id": station_id,
        "station_name": history.station_name,
        "statistics": {
            "water_level": {
                "min": float(np.min(levels)),
                "max": float(np.max(levels)),
                "mean": float(np.mean(levels)),
                "std": float(np.std(levels)),
            },
            "rainfall": {
                "total": float(np.sum(rainfalls)),
                "max_hourly": float(np.max(rainfalls)),
                "mean_hourly": float(np.mean(rainfalls)),
            },
            "hours": hours,
        },
    }

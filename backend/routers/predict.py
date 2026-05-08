# -*- coding: utf-8 -*-
"""
Prediction APIs backed by the current dam-centered simulation state.

The previous version generated random history and random rainfall. This router
now derives its inputs from the active SWE model and the flood router's runtime
history so that the prediction panels react to the same system the map uses.
"""

from datetime import datetime, timedelta
from typing import Dict, List

import numpy as np
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from config import BASE_LAT, BASE_LNG, DAM_CONFIG, GRID_DX, GRID_DY, SENSOR_STATIONS
from routers import flood
from services.weather import get_rainfall_forecast

router = APIRouter(prefix="/api/predict", tags=["predict"])


class PredictionPoint(BaseModel):
    timestamp: str
    predicted_level: float
    confidence_upper: float
    confidence_lower: float


class FloodPredictionResponse(BaseModel):
    station_id: str
    prediction_type: str
    forecast_hours: int
    points: List[PredictionPoint]
    statistics: Dict
    generated_at: str


class RiskTrendPoint(BaseModel):
    timestamp: str
    risk_level: str
    risk_score: float
    description: str


class RiskTrendResponse(BaseModel):
    forecast_hours: int
    trend_points: List[RiskTrendPoint]
    overall_trend: str


class ScenarioPredictionRequest(BaseModel):
    scenario_type: str
    duration_hours: float = 6.0
    intensity: float = 1.0


class ScenarioPredictionResponse(BaseModel):
    scenario_type: str
    duration_hours: float
    prediction_points: List[Dict]
    maximum_water_level: float
    warning_issued: bool
    recommendation: str


def _get_model(request: Request):
    model = getattr(request.app.state, "swe_model", None)
    if model is None:
        model = flood.build_swe_model()
        request.app.state.swe_model = model
    return model


def _station_grid_index(station_id: str, model) -> tuple[int, int]:
    station = SENSOR_STATIONS[station_id]
    row = int(round((BASE_LAT - station["lat"]) / GRID_DY))
    col = int(round((station["lng"] - BASE_LNG) / GRID_DX))
    row = int(np.clip(row, 0, model.rows - 1))
    col = int(np.clip(col, 0, model.cols - 1))
    return row, col


def _current_station_level(station_id: str, request: Request) -> float:
    model = _get_model(request)
    row, col = _station_grid_index(station_id, model)
    return float(model.dem[row, col] + model.h[row, col])


def _station_history(station_id: str, request: Request, lookback: int = 24) -> tuple[np.ndarray, np.ndarray]:
    station_entries = [entry for entry in flood.sim_state.history if entry["station_id"] == station_id]
    station_entries = station_entries[-lookback:]

    if station_entries:
        levels = np.array([float(entry["water_level"]) for entry in station_entries], dtype=float)
        rainfall = np.array([float(entry["rainfall"]) for entry in station_entries], dtype=float)
        return levels, rainfall

    current_level = _current_station_level(station_id, request)
    baseline = np.linspace(current_level - 0.4, current_level, num=min(lookback, 8))
    levels = np.clip(baseline, 0.0, None)
    rainfall = np.full(levels.shape[0], float(flood.sim_state.rainfall_rate), dtype=float)
    return levels, rainfall


def _station_response_weight(station_id: str) -> float:
    return {
        "upstream": 1.2,
        "urban_a": 1.0,
        "urban_b": 1.05,
        "downstream": 0.86,
        "tributary": 0.96,
    }.get(station_id, 1.0)


def _forecast_rainfall_series(hours: int, scenario_multiplier: float = 1.0) -> np.ndarray:
    current_rainfall = float(flood.sim_state.rainfall_rate)
    if hours <= 0:
        return np.array([], dtype=float)

    if current_rainfall <= 0.0:
        return np.zeros(hours, dtype=float)

    decay = np.exp(-np.arange(hours, dtype=float) / 5.0)
    return current_rainfall * scenario_multiplier * decay


def _predict_levels(
    station_id: str,
    request: Request,
    hours: int,
    rainfall_override: np.ndarray | None = None,
    inflow_scale: float = 1.0,
    release_scale: float = 1.0,
) -> Dict:
    history_levels, _history_rainfall = _station_history(station_id, request, lookback=24)
    current_level = float(history_levels[-1])
    history_window = history_levels[-min(len(history_levels), 6) :]
    recent_slope = float(np.mean(np.diff(history_window))) if len(history_window) >= 2 else 0.0

    rainfall_series = rainfall_override if rainfall_override is not None else _forecast_rainfall_series(hours)
    response_weight = _station_response_weight(station_id)

    upstream_inflow = float(flood.sim_state.upstream_inflow) * inflow_scale
    gate_release = float(flood.sim_state.gate_release) * release_scale
    downstream_level = float(flood.sim_state.downstream_level)
    reservoir_level = float(flood.sim_state.reservoir_level)

    inflow_imbalance = (upstream_inflow - gate_release) / max(float(DAM_CONFIG["max_release_m3s"]), 1.0)
    reservoir_pressure = max(reservoir_level - float(DAM_CONFIG["normal_reservoir_level_m"]), -2.0) * 0.08
    downstream_pressure = max(downstream_level - float(DAM_CONFIG["downstream_control_level_m"]), 0.0) * 0.06

    predictions: List[float] = []
    confidence_upper: List[float] = []
    confidence_lower: List[float] = []
    risk_trend: List[str] = []

    level = current_level
    for hour_index in range(hours):
        rainfall_push = float(rainfall_series[hour_index]) / 60.0 * 0.32 * response_weight
        inertia = recent_slope * max(0.18, np.exp(-hour_index / 5.5))
        hydraulic_push = inflow_imbalance * 0.68 * response_weight + reservoir_pressure + downstream_pressure
        drainage_relief = max(gate_release - upstream_inflow, 0.0) / max(float(DAM_CONFIG["max_release_m3s"]), 1.0) * 0.42

        delta = inertia + rainfall_push + hydraulic_push - drainage_relief
        delta = float(np.clip(delta, -0.85, 1.05))
        level = float(np.clip(level + delta, 0.0, 60.0))

        uncertainty = 0.22 + rainfall_push * 0.35 + abs(delta) * 0.16
        predictions.append(level)
        confidence_upper.append(level + uncertainty)
        confidence_lower.append(max(0.0, level - uncertainty * 0.75))
        risk_trend.append(water_level_to_risk_level(level))

    timestamps = [(datetime.now() + timedelta(hours=index + 1)).isoformat() for index in range(hours)]

    return {
        "timestamps": timestamps,
        "predicted_levels": predictions,
        "confidence_upper": confidence_upper,
        "confidence_lower": confidence_lower,
        "risk_trend": risk_trend,
        "avg_prediction": float(np.mean(predictions)) if predictions else current_level,
        "max_prediction": float(np.max(predictions)) if predictions else current_level,
        "min_prediction": float(np.min(predictions)) if predictions else current_level,
    }


def water_level_to_risk_level(water_level: float) -> str:
    if water_level < 20.0:
        return "low"
    if water_level < 30.0:
        return "medium"
    if water_level < 38.0:
        return "high"
    return "critical"


def _risk_description(risk_level: str) -> str:
    descriptions = {
        "low": "维持监测，坝区总体可控。",
        "medium": "关注库区和近坝断面变化，准备预警升级。",
        "high": "重点区域风险持续抬升，建议提前调度与疏散准备。",
        "critical": "坝区及下游风险极高，建议立即执行应急处置。",
    }
    return descriptions[risk_level]


@router.get("/flood", response_model=FloodPredictionResponse)
async def get_flood_prediction(request: Request, station_id: str = "sgr_huairen_main", hours: int = 24) -> FloodPredictionResponse:
    if station_id not in SENSOR_STATIONS:
        raise HTTPException(status_code=400, detail=f"Invalid station_id. Must be one of {list(SENSOR_STATIONS)}")
    if hours < 1 or hours > 24:
        raise HTTPException(status_code=400, detail="Hours must be between 1 and 24")

    # 优先使用和风天气真实降雨预报
    weather = await get_rainfall_forecast(hours=hours)
    real_rainfall = np.array(weather["forecast"], dtype=float)
    rainfall_override = real_rainfall if len(real_rainfall) == hours else None

    prediction = _predict_levels(
        station_id=station_id,
        request=request,
        hours=hours,
        rainfall_override=rainfall_override,
    )
    points = [
        PredictionPoint(
            timestamp=prediction["timestamps"][index],
            predicted_level=float(prediction["predicted_levels"][index]),
            confidence_upper=float(prediction["confidence_upper"][index]),
            confidence_lower=float(prediction["confidence_lower"][index]),
        )
        for index in range(hours)
    ]

    return FloodPredictionResponse(
        station_id=station_id,
        prediction_type="simulation_state_projection",
        forecast_hours=hours,
        points=points,
        statistics={
            "avg_prediction": prediction["avg_prediction"],
            "max_prediction": prediction["max_prediction"],
            "min_prediction": prediction["min_prediction"],
            "risk_trend": prediction["risk_trend"],
            "rainfall_source": weather["source"],     # "qweather" 或 "simulated"
            "rainfall_total_mm": weather["total_mm"],
            "rainfall_peak_mm": weather["peak_mm"],
            "source": "dam_state_and_station_history",
        },
        generated_at=datetime.now().isoformat(),
    )


@router.get("/weather", summary="获取桑干河流域实时降雨预报")
async def get_weather_forecast():
    """返回和风天气降雨预报（或统计模拟后备），供前端展示数据来源。"""
    return await get_rainfall_forecast(hours=24)


@router.get("/risk-trend", response_model=RiskTrendResponse)
async def get_risk_trend(request: Request, station_id: str = "urban_a", hours: int = 12) -> RiskTrendResponse:
    if station_id not in SENSOR_STATIONS:
        raise HTTPException(status_code=400, detail=f"Invalid station_id. Must be one of {list(SENSOR_STATIONS)}")
    if hours < 1 or hours > 24:
        raise HTTPException(status_code=400, detail="Hours must be between 1 and 24")

    prediction = _predict_levels(station_id=station_id, request=request, hours=hours)
    trend_points = []
    for index in range(hours):
        level = float(prediction["predicted_levels"][index])
        risk_level = prediction["risk_trend"][index]
        trend_points.append(
            RiskTrendPoint(
                timestamp=prediction["timestamps"][index],
                risk_level=risk_level,
                risk_score=float(np.clip(level / 45.0 * 100.0, 0.0, 100.0)),
                description=_risk_description(risk_level),
            )
        )

    overall_trend = "stable"
    if prediction["predicted_levels"][-1] > prediction["predicted_levels"][0] + 0.4:
        overall_trend = "worsening"
    elif prediction["predicted_levels"][-1] < prediction["predicted_levels"][0] - 0.4:
        overall_trend = "improving"

    return RiskTrendResponse(forecast_hours=hours, trend_points=trend_points, overall_trend=overall_trend)


@router.post("/scenario", response_model=ScenarioPredictionResponse)
async def predict_scenario(request_data: ScenarioPredictionRequest, request: Request) -> ScenarioPredictionResponse:
    if request_data.scenario_type not in {"heavy_rain", "continuous_rain", "dam_failure"}:
        raise HTTPException(status_code=400, detail="Invalid scenario_type")

    hours = max(1, min(int(request_data.duration_hours), 24))
    scenario_multiplier = 1.0
    inflow_scale = 1.0
    release_scale = 1.0

    if request_data.scenario_type == "heavy_rain":
        scenario_multiplier = 1.8 * request_data.intensity
        inflow_scale = 1.15
    elif request_data.scenario_type == "continuous_rain":
        scenario_multiplier = 1.35 * request_data.intensity
        inflow_scale = 1.08
    else:
        scenario_multiplier = 2.1 * request_data.intensity
        inflow_scale = 1.35
        release_scale = 0.85

    rainfall_series = _forecast_rainfall_series(hours, scenario_multiplier=scenario_multiplier)
    if request_data.scenario_type == "dam_failure":
        rainfall_series = rainfall_series + np.linspace(30.0, 8.0, num=hours)

    prediction = _predict_levels(
        station_id="sgr_downstream",
        request=request,
        hours=hours,
        rainfall_override=rainfall_series,
        inflow_scale=inflow_scale,
        release_scale=release_scale,
    )

    prediction_points = [
        {
            "timestamp": prediction["timestamps"][index],
            "hour": index + 1,
            "predicted_level": float(prediction["predicted_levels"][index]),
            "rainfall": float(rainfall_series[index]),
        }
        for index in range(hours)
    ]
    max_level = float(max(prediction["predicted_levels"], default=0.0))
    # 桑干河怀仁段水位阈值
    if max_level < 1022.0:
        recommendation = "维持巡检，继续观察坝区和下游断面。"
    elif max_level < 1035.0:
        recommendation = "启动预警值守，准备重点点位转移。"
    elif max_level < 1050.0:
        recommendation = "建议提前执行下游怀仁市区和桑干河大桥区域人员转移和交通管制。"
    else:
        recommendation = "立即执行最高级应急响应，优先保护怀仁人民医院、学校等关键点位。"

    return ScenarioPredictionResponse(
        scenario_type=request_data.scenario_type,
        duration_hours=request_data.duration_hours,
        prediction_points=prediction_points,
        maximum_water_level=max_level,
        warning_issued=max_level >= 30.0,
        recommendation=recommendation,
    )


@router.get("/ensemble")
async def get_ensemble_prediction(request: Request, station_id: str = "urban_a", hours: int = 24) -> Dict:
    if station_id not in SENSOR_STATIONS:
        raise HTTPException(status_code=400, detail=f"Invalid station_id. Must be one of {list(SENSOR_STATIONS)}")
    if hours < 1 or hours > 24:
        raise HTTPException(status_code=400, detail="Hours must be between 1 and 24")

    projections = [
        _predict_levels(station_id, request, hours, inflow_scale=1.0, release_scale=1.0),
        _predict_levels(station_id, request, hours, inflow_scale=1.08, release_scale=0.94),
        _predict_levels(station_id, request, hours, inflow_scale=0.94, release_scale=1.08),
    ]
    predictions_array = np.array([projection["predicted_levels"] for projection in projections], dtype=float)
    mean_prediction = np.mean(predictions_array, axis=0)
    std_prediction = np.std(predictions_array, axis=0)

    points = []
    for index in range(hours):
        points.append(
            {
                "timestamp": projections[0]["timestamps"][index],
                "ensemble_mean": float(mean_prediction[index]),
                "ensemble_std": float(std_prediction[index]),
                "upper_95": float(mean_prediction[index] + 1.96 * std_prediction[index]),
                "lower_05": float(max(0.0, mean_prediction[index] - 1.96 * std_prediction[index])),
            }
        )

    return {
        "prediction_type": "simulation_ensemble",
        "forecast_hours": hours,
        "points": points,
        "generated_at": datetime.now().isoformat(),
    }


@router.get("/breach", summary="溃坝情景模拟 — 级联风险推演")
async def simulate_dam_breach(
    request: Request,
    breach_width_m: float = 50.0,
    reservoir_level_m: float = 1055.0,
    hours: int = 12,
) -> Dict:
    """
    桑干河怀仁段水库溃坝情景专项推演。

    基于简化物理模型：
      1. 溃口流量 Q(t) = Cd × B × sqrt(2g) × H(t)^1.5（堰流公式）
      2. 洪峰传播：Muskingum 线性演算（K=2h, X=0.3）
      3. 下游水位响应：Manning 公式反算

    参数：
      breach_width_m:    溃口宽度（m），默认 50m（部分溃坝）
      reservoir_level_m: 溃坝时库水位（m），默认 1055m（接近校核洪水位）
      hours:             推演时长（1-24 h）
    """
    hours = max(1, min(hours, 24))
    g = 9.81
    Cd = 0.61
    B = min(max(breach_width_m, 10.0), 300.0)

    dam_crest = float(DAM_CONFIG["crest_elevation_m"])
    downstream_base = float(DAM_CONFIG["downstream_control_level_m"])

    timestamps = [(datetime.now() + timedelta(hours=h)).isoformat() for h in range(1, hours + 1)]
    t_arr = np.arange(1, hours + 1, dtype=float)

    H0 = max(reservoir_level_m - (dam_crest - 20.0), 0.1)
    drain_rate = 0.25
    H_t = H0 * np.exp(-drain_rate * t_arr)
    Q_t = Cd * B * np.sqrt(2 * g) * np.maximum(H_t, 0) ** 1.5

    # Muskingum 洪峰演算
    K, X_mk = 2.0, 0.3
    dt = 1.0
    C0 = (dt - 2 * K * X_mk) / (2 * K * (1 - X_mk) + dt)
    C1 = (dt + 2 * K * X_mk) / (2 * K * (1 - X_mk) + dt)
    C2 = (2 * K * (1 - X_mk) - dt) / (2 * K * (1 - X_mk) + dt)

    Q_routed = np.zeros(hours)
    Q_routed[0] = Q_t[0]
    for i in range(1, hours):
        Q_routed[i] = C0 * Q_t[i] + C1 * Q_t[i - 1] + C2 * Q_routed[i - 1]

    B_river, n_mann, S0 = 120.0, 0.04, 0.0005
    def q_to_depth(Q: float) -> float:
        if Q <= 0:
            return 0.0
        return (Q * n_mann / (B_river * S0 ** 0.5)) ** 0.6

    depth_t = np.array([q_to_depth(q) for q in Q_routed])
    wl_t = downstream_base + depth_t

    def level_to_risk(wl: float) -> str:
        if wl < 1022: return "low"
        if wl < 1032: return "medium"
        if wl < 1045: return "high"
        return "critical"

    points = [
        {
            "hour": int(t_arr[i]),
            "timestamp": timestamps[i],
            "breach_discharge_m3s": round(float(Q_t[i]), 1),
            "routed_discharge_m3s": round(float(Q_routed[i]), 1),
            "downstream_depth_m": round(float(depth_t[i]), 2),
            "downstream_level_m": round(float(wl_t[i]), 2),
            "risk_level": level_to_risk(float(wl_t[i])),
        }
        for i in range(hours)
    ]

    peak_q = float(np.max(Q_t))
    peak_wl = float(np.max(wl_t))
    t_peak = int(np.argmax(Q_t)) + 1

    cascade_events = []
    if peak_wl >= 1022:
        cascade_events.append({"hour": t_peak, "event": "桑干河大桥漫水，S322省道中断"})
    if peak_wl >= 1032:
        cascade_events.append({"hour": t_peak + 1, "event": "怀仁市区低洼地带进水，安置区启动"})
    if peak_wl >= 1045:
        cascade_events.append({"hour": t_peak + 2, "event": "怀仁人民医院受威胁，触发最高响应"})

    return {
        "scenario": "dam_breach",
        "breach_width_m": B,
        "initial_reservoir_level_m": reservoir_level_m,
        "peak_discharge_m3s": round(peak_q, 1),
        "peak_downstream_level_m": round(peak_wl, 2),
        "time_to_peak_hours": t_peak,
        "cascade_events": cascade_events,
        "points": points,
        "recommendation": (
            "立即启动溃坝应急预案，疏散桑干河两岸怀仁市区全部居民，封闭S322省道，通知山阴县做好下游接收准备。"
            if peak_wl >= 1032 else
            "下游河滩地及低洼村庄立即预警，桑干河大桥实施交通管制。"
        ),
        "generated_at": datetime.now().isoformat(),
    }

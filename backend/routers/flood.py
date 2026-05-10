# -*- coding: utf-8 -*-
"""
Flood simulation API routes.

This router now serves the actual SWE model state instead of returning
synthetic flood-grid points.
"""

import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

import numpy as np
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from config import (
    BASE_LAT,
    BASE_LNG,
    DAM_CONFIG,
    GRID_COLS,
    GRID_DX,
    GRID_DY,
    GRID_ROWS,
    KEY_POINTS,
    SENSOR_STATIONS,
    SIMULATION_DT,
)
from models.hydraulic import SWEModel, TensorSWEModel, scalar_to_float, torch
from benchmarks.toce_river import REQUIRED_COLUMNS, load_toce_comparison_text, score_toce_csv, write_toce_comparison_csv
from services.real_observations import fetch_usgs_probe, get_oroville_2017_event

router = APIRouter(prefix="/api/flood", tags=["flood"])


def resolve_solver_engine(dam_config: Dict | None = None) -> tuple[str, str, str]:
    """Return requested engine, selected engine, and a human-readable runtime note."""
    dam_config = dam_config or {}
    requested = str(
        dam_config.get("solver_engine")
        or os.getenv("SWE_SOLVER_ENGINE")
        or "auto"
    ).lower()
    requested_device = str(dam_config.get("solver_device") or os.getenv("SWE_SOLVER_DEVICE") or "auto")

    if requested not in {"auto", "torch", "cuda", "cpu", "numpy"}:
        requested = "auto"

    torch_ready = torch is not None
    if requested in {"torch", "cuda", "cpu"} or (requested == "auto" and torch_ready):
        if TensorSWEModel is not None and torch_ready:
            if requested == "cuda":
                requested_device = "cuda"
            elif requested == "cpu":
                requested_device = "cpu"
            selected = "torch_tensor_runtime"
            return requested_device, selected, "Torch tensor SWE runtime is selected; CUDA is used when available."

        return requested_device, "numpy_swe_runtime", "Torch is not installed in this backend runtime; falling back to NumPy SWE."

    return requested_device, "numpy_swe_runtime", "NumPy SWE runtime is selected explicitly or by fallback."


def build_model_capability_profile() -> Dict:
    """Expose implementation evidence for the project's three core innovations."""
    _, selected_engine, runtime_note = resolve_solver_engine(DAM_CONFIG)
    dam_boundary = {
        "upstream_reservoir_level_m": float(DAM_CONFIG["initial_reservoir_level_m"]),
        "upstream_inflow_m3s": "runtime_parameter",
        "gate_release_m3s": float(DAM_CONFIG["default_release_m3s"]),
        "downstream_control_level_m": float(DAM_CONFIG["downstream_control_level_m"]),
        "dam_crest_elevation_m": float(DAM_CONFIG["crest_elevation_m"]),
        "gate_columns": [int(DAM_CONFIG["gate_start_col"]), int(DAM_CONFIG["gate_end_col"])],
    }

    return {
        "focus": "dam_centered_flood_warning",
        "title": "Physics-informed dam flood digital twin",
        "model_runtime": {
            "current_engine": selected_engine,
            "baseline_solver": "2D shallow-water prototype with DEM, rainfall, inflow, gate release, and downstream stage",
            "accelerated_candidate": "TensorSWEModel with Torch tensors, CFL time step, and RK2 integration",
            "ai_prediction": "station-level prediction API and risk trend coupling",
            "runtime_note": runtime_note,
        },
        "innovation_points": {
            "physics_ai_fusion": {
                "label": "Physics model + AI prediction",
                "evidence": [
                    "SWEModel computes DEM-based water depth, velocity, and water surface.",
                    "Prediction API feeds forecast levels and risk trend into the dashboard.",
                    "Risk assessment consumes hydraulic grid output instead of static map decoration.",
                ],
            },
            "dam_boundary_conditions": {
                "label": "Dam-centered boundary conditions",
                "evidence": [
                    "Upstream reservoir level and inflow are explicit simulation inputs.",
                    "Gate release is injected through the configured dam gate slice.",
                    "Downstream control water level is applied as a boundary stage.",
                    "Dam crest and gate opening are encoded in the DEM features.",
                ],
            },
            "monitor_simulate_warn_respond_loop": {
                "label": "Monitor-simulate-warn-respond loop",
                "evidence": [
                    "Sensor snapshots update station water level, rainfall, and flow.",
                    "Simulation produces flood grid, risk zones, and affected key objects.",
                    "Early warning API returns warning level, message, area, and population.",
                    "Evacuation routes and PDF report export close the response loop.",
                ],
            },
        },
        "boundary_conditions": dam_boundary,
        "decision_loop": [
            "monitor_sensor_state",
            "simulate_hydraulic_grid",
            "evaluate_risk_objects",
            "recommend_evacuation_routes",
            "export_command_report",
        ],
        "case_evidence": {
            "case_id": DAM_CONFIG.get("case_id", "custom"),
            "dam_name": DAM_CONFIG["name"],
            "river": DAM_CONFIG.get("river"),
            "sensor_count": len(SENSOR_STATIONS),
            "key_object_count": len(KEY_POINTS),
            "data_sources": DAM_CONFIG.get("data_sources", []),
        },
    }


class SimulationState:
    """Mutable simulation runtime state."""

    def __init__(self) -> None:
        self.is_running = False
        self.current_time_step = 0
        self.total_steps = 0
        self.rainfall_rate = 0.0
        self.upstream_inflow = 0.0
        self.gate_release = float(DAM_CONFIG["default_release_m3s"])
        self.downstream_level = float(DAM_CONFIG["downstream_control_level_m"])
        self.reservoir_level = float(DAM_CONFIG["initial_reservoir_level_m"])
        self.start_time: datetime | None = None
        self.last_advance_time: datetime | None = None
        self.history: List[Dict] = []

    def reset(self) -> None:
        self.is_running = False
        self.current_time_step = 0
        self.total_steps = 0
        self.rainfall_rate = 0.0
        self.upstream_inflow = 0.0
        self.gate_release = float(DAM_CONFIG["default_release_m3s"])
        self.downstream_level = float(DAM_CONFIG["downstream_control_level_m"])
        self.reservoir_level = float(DAM_CONFIG["initial_reservoir_level_m"])
        self.start_time = None
        self.last_advance_time = None
        self.history = []


sim_state = SimulationState()


def build_swe_model(overrides: Dict | None = None):
    dx_m = GRID_DX * 111000
    dy_m = GRID_DY * 111000
    dam_config = {**DAM_CONFIG, **(overrides or {})}
    requested_device, selected_engine, _ = resolve_solver_engine(dam_config)

    if selected_engine == "torch_tensor_runtime" and TensorSWEModel is not None:
        try:
            return TensorSWEModel(
                rows=GRID_ROWS,
                cols=GRID_COLS,
                dx=dx_m,
                dy=dy_m,
                dam_config=dam_config,
                device=requested_device,
            )
        except Exception:
            # Keep the warning platform usable if the optional acceleration path
            # is not available in the current Python runtime.
            pass

    return SWEModel(rows=GRID_ROWS, cols=GRID_COLS, dx=dx_m, dy=dy_m, dam_config=dam_config)


def get_model(request: Request) -> SWEModel:
    model = getattr(request.app.state, "swe_model", None)
    if model is None:
        model = build_swe_model()
        request.app.state.swe_model = model
    return model


def rainfall_mm_h_to_mps(rainfall_mm_h: float) -> float:
    return rainfall_mm_h / 1000.0 / 3600.0


def compute_grid_statistics(points: List[Dict]) -> Dict:
    flooded_points = [point for point in points if point["flooded"]]
    flooded_count = len(flooded_points)
    max_depth = max((point["depth"] for point in flooded_points), default=0.0)
    total_depth = sum(point["depth"] for point in flooded_points)

    return {
        "total_points": len(points),
        "flooded_points": flooded_count,
        "max_depth": round(max_depth, 2),
        "avg_depth": round(total_depth / max(flooded_count, 1), 2),
        "flooded_area_km2": round(flooded_count * (GRID_DX * 111) * (GRID_DY * 111), 2),
    }


def station_grid_index(station_id: str, model: SWEModel) -> tuple[int, int]:
    station = SENSOR_STATIONS[station_id]
    row = int(round((BASE_LAT - station["lat"]) / GRID_DY))
    col = int(round((station["lng"] - BASE_LNG) / GRID_DX))
    row = int(np.clip(row, 0, model.rows - 1))
    col = int(np.clip(col, 0, model.cols - 1))
    return row, col


def build_station_snapshot(model: SWEModel, station_id: str) -> Dict:
    row, col = station_grid_index(station_id, model)

    depth = scalar_to_float(model.h[row, col])
    velocity_u = scalar_to_float(model.u[row, col])
    velocity_v = scalar_to_float(model.v[row, col])
    velocity = float(np.sqrt(velocity_u**2 + velocity_v**2))
    water_surface = scalar_to_float(model.dem[row, col]) + depth

    return {
        "timestamp": datetime.now().isoformat(),
        "time_step": sim_state.current_time_step,
        "station_id": station_id,
        "water_level": round(water_surface, 3),
        "rainfall": round(sim_state.rainfall_rate, 2),
        "flow_rate": round(velocity, 3),
        "depth": round(depth, 3),
    }


def record_station_history(model: SWEModel) -> None:
    for station_id in SENSOR_STATIONS:
        sim_state.history.append(build_station_snapshot(model, station_id))


def advance_one_step(model: SWEModel) -> None:
    model.step(
        dt=SIMULATION_DT,
        rainfall_rate=rainfall_mm_h_to_mps(sim_state.rainfall_rate),
        upstream_inflow=sim_state.upstream_inflow,
        gate_release=sim_state.gate_release,
        downstream_stage=sim_state.downstream_level,
    )

    sim_state.current_time_step += 1
    record_station_history(model)

    if sim_state.current_time_step >= sim_state.total_steps:
        sim_state.is_running = False


def advance_simulation_if_due(request: Request, max_steps: int = 3) -> None:
    if not sim_state.is_running or sim_state.total_steps <= 0:
        return

    now = datetime.now()
    if sim_state.last_advance_time is None:
        sim_state.last_advance_time = now
        return

    elapsed_seconds = (now - sim_state.last_advance_time).total_seconds()
    steps_due = min(max(int(elapsed_seconds / 1.5), 0), max_steps)
    if steps_due <= 0:
        return

    model = get_model(request)
    for _ in range(steps_due):
        if not sim_state.is_running:
            break
        advance_one_step(model)

    sim_state.last_advance_time = now


class SimulationStartRequest(BaseModel):
    rainfall_mm_h: float = 50.0
    duration_hours: float = 12.0
    upstream_m3s: float = 100.0
    gate_release_m3s: float = float(DAM_CONFIG["default_release_m3s"])
    downstream_level_m: float = float(DAM_CONFIG["downstream_control_level_m"])
    reservoir_level_m: float = float(DAM_CONFIG["initial_reservoir_level_m"])


class ToceBenchmarkImportRequest(BaseModel):
    csv_text: str


class SimulationStatus(BaseModel):
    is_running: bool
    current_time_step: int
    total_steps: int
    elapsed_minutes: float
    rainfall_rate: float
    upstream_inflow: float
    gate_release: float
    downstream_level: float
    reservoir_level: float
    progress_percent: float
    dam_name: str


class GridPoint(BaseModel):
    lat: float
    lng: float
    depth: float
    velocity_u: float
    velocity_v: float
    velocity_mag: float
    dem: float
    water_surface: float
    flooded: bool


class FloodGridResponse(BaseModel):
    timestamp: str
    time_step: int
    total_points: int
    points: List[Dict]
    statistics: Dict


class HistoryEntry(BaseModel):
    timestamp: str
    time_step: int
    station_id: str
    water_level: float
    rainfall: float
    flow_rate: float


class HistoryResponse(BaseModel):
    station_id: str
    hours: int
    entries: List[HistoryEntry]


def _apply_simulation_start(request_data: SimulationStartRequest, request: Request, history_label: str | None = None) -> Dict:
    sim_state.reset()
    request.app.state.swe_model = build_swe_model(
        {
            "initial_reservoir_level_m": request_data.reservoir_level_m,
            "default_release_m3s": request_data.gate_release_m3s,
            "downstream_control_level_m": request_data.downstream_level_m,
        }
    )
    model = request.app.state.swe_model

    duration_seconds = request_data.duration_hours * 3600.0
    sim_state.total_steps = int(duration_seconds / SIMULATION_DT)
    sim_state.rainfall_rate = request_data.rainfall_mm_h
    sim_state.upstream_inflow = request_data.upstream_m3s
    sim_state.gate_release = request_data.gate_release_m3s
    sim_state.downstream_level = request_data.downstream_level_m
    sim_state.reservoir_level = request_data.reservoir_level_m
    sim_state.is_running = True
    sim_state.start_time = datetime.now()
    sim_state.last_advance_time = sim_state.start_time

    record_station_history(model)

    response = {
        "status": "simulation_started",
        "total_steps": sim_state.total_steps,
        "duration_hours": request_data.duration_hours,
        "rainfall_mm_h": request_data.rainfall_mm_h,
        "upstream_inflow_m3s": request_data.upstream_m3s,
        "gate_release_m3s": request_data.gate_release_m3s,
        "downstream_level_m": request_data.downstream_level_m,
        "reservoir_level_m": request_data.reservoir_level_m,
        "dam_name": DAM_CONFIG["name"],
    }
    if history_label:
        response["history_label"] = history_label
    return response


@router.get("/case")
async def get_active_case() -> Dict:
    return {
        "case_id": DAM_CONFIG.get("case_id", "custom"),
        "dam": {
            "name": DAM_CONFIG["name"],
            "owner": DAM_CONFIG.get("owner"),
            "river": DAM_CONFIG.get("river"),
            "lat": DAM_CONFIG.get("dam_lat"),
            "lng": DAM_CONFIG.get("dam_lng"),
            "crest_elevation_m": DAM_CONFIG.get("crest_elevation_m"),
            "normal_reservoir_level_m": DAM_CONFIG.get("normal_reservoir_level_m"),
        },
        "grid": {
            "rows": GRID_ROWS,
            "cols": GRID_COLS,
            "base_lat": BASE_LAT,
            "base_lng": BASE_LNG,
            "dx_deg": GRID_DX,
            "dy_deg": GRID_DY,
        },
        "sensor_stations": SENSOR_STATIONS,
        "key_points": KEY_POINTS,
        "dem_control_points": DAM_CONFIG.get("dem_control_points", []),
        "dem_grid_cache": {
            "path": DAM_CONFIG.get("dem_grid_path"),
            "enabled": bool(DAM_CONFIG.get("dem_grid_path")),
            "mode": "local_raster_cache",
        },
        "data_sources": DAM_CONFIG.get("data_sources", []),
    }


@router.get("/capabilities")
async def get_model_capabilities() -> Dict:
    return build_model_capability_profile()


@router.get("/runtime/benchmark")
async def benchmark_solver_runtime(engine: str = "auto", steps: int = 10) -> Dict:
    """Run a small in-process SWE benchmark for deployment sanity checks."""
    safe_steps = int(np.clip(steps, 1, 100))
    model = build_swe_model({"solver_engine": engine})

    start = time.perf_counter()
    for _ in range(safe_steps):
        model.step(
            dt=SIMULATION_DT,
            rainfall_rate=rainfall_mm_h_to_mps(30.0),
            upstream_inflow=900.0,
            gate_release=float(DAM_CONFIG["default_release_m3s"]),
            downstream_stage=float(DAM_CONFIG["downstream_control_level_m"]),
        )
    elapsed_ms = (time.perf_counter() - start) * 1000

    return {
        "requested_engine": engine,
        "actual_engine": getattr(model, "engine_name", "unknown"),
        "grid": {"rows": model.rows, "cols": model.cols, "cells": model.rows * model.cols},
        "steps": safe_steps,
        "elapsed_ms": round(elapsed_ms, 3),
        "ms_per_step": round(elapsed_ms / safe_steps, 3),
        "torch_available": torch is not None,
    }


@router.get("/benchmarks/toce")
async def get_toce_benchmark() -> Dict:
    comparison_csv = Path(__file__).resolve().parents[1] / "data" / "toce_river_comparison.csv"
    if not comparison_csv.exists():
        return {
            "benchmark": "Toce River dam-break",
            "status": "data_not_loaded",
            "expected_file": str(comparison_csv),
            "required_columns": [
                *REQUIRED_COLUMNS,
            ],
        }

    return {"status": "scored", **score_toce_csv(comparison_csv)}


@router.post("/benchmarks/toce/import")
async def import_toce_benchmark(payload: ToceBenchmarkImportRequest) -> Dict:
    comparison_csv = Path(__file__).resolve().parents[1] / "data" / "toce_river_comparison.csv"
    try:
        rows = load_toce_comparison_text(payload.csv_text)
        write_toce_comparison_csv(rows, comparison_csv)
        return {
            "status": "scored",
            "saved_to": str(comparison_csv),
            **score_toce_csv(comparison_csv),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/real-data/status")
async def get_real_data_status() -> Dict:
    station_ids = [station_id.replace("usgs_", "") for station_id in SENSOR_STATIONS if station_id.startswith("usgs_")]
    usgs_probe = await fetch_usgs_probe(station_ids=station_ids, period="P7D")
    event = get_oroville_2017_event()

    return {
        "case_id": DAM_CONFIG.get("case_id", "custom"),
        "checked_at": datetime.now().isoformat(),
        "dem": {
            "status": "cached",
            "path": DAM_CONFIG.get("dem_grid_path"),
            "mode": "local DEM grid cache; next step is GeoTIFF crop/import",
        },
        "usgs": usgs_probe,
        "historical_event": {
            "event_id": event["event_id"],
            "name": event["name"],
            "period": event["period"],
            "known_milestones": event["known_milestones"],
            "calibration_targets": event["calibration_targets"],
            "limitations": event["limitations"],
            "starter_simulation": event["starter_simulation"],
            "milestone_count": len(event["known_milestones"]),
            "calibration_target_count": len(event["calibration_targets"]),
        },
        "next_steps": [
            "Replace local DEM cache with cropped USGS 3DEP GeoTIFF.",
            "Persist USGS/CDEC station time series as model forcing data.",
            "Tune model parameters against the 2017 Oroville replay window.",
        ],
    }


@router.get("/historical-events/oroville-2017")
async def get_oroville_2017_historical_event() -> Dict:
    return get_oroville_2017_event()


def generate_synthetic_history(station_id: str, hours: int = 24) -> List[HistoryEntry]:
    entries = []
    base_water_level = {
        "usgs_11406800": 266.0,
        "usgs_11406818": 112.0,
        "usgs_11407000": 49.5,
        "usgs_11406870": 40.5,
    }.get(station_id, 50.0)

    now = datetime.now()
    for i in range(hours):
        trend = np.sin(i / 6.0) * 0.5
        noise = np.random.normal(0, 0.2)
        water_level = float(np.clip(base_water_level + trend + noise, base_water_level - 5.0, base_water_level + 5.0))
        rainfall = float(np.random.exponential(20) if np.random.rand() > 0.6 else 0)
        flow_rate = float(np.clip(50 + trend * 20 + np.random.normal(0, 5), 0, 200))

        entries.append(
            HistoryEntry(
                timestamp=(now - timedelta(hours=hours - i - 1)).isoformat(),
                time_step=i,
                station_id=station_id,
                water_level=water_level,
                rainfall=rainfall,
                flow_rate=flow_rate,
            )
        )

    return entries


@router.get("/status", response_model=SimulationStatus)
async def get_simulation_status(request: Request) -> SimulationStatus:
    advance_simulation_if_due(request)

    elapsed_minutes = 0.0
    if sim_state.start_time:
        elapsed_minutes = (datetime.now() - sim_state.start_time).total_seconds() / 60.0

    progress = 0.0
    if sim_state.total_steps > 0:
        progress = (sim_state.current_time_step / sim_state.total_steps) * 100.0

    return SimulationStatus(
        is_running=sim_state.is_running,
        current_time_step=sim_state.current_time_step,
        total_steps=sim_state.total_steps,
        elapsed_minutes=elapsed_minutes,
        rainfall_rate=sim_state.rainfall_rate,
        upstream_inflow=sim_state.upstream_inflow,
        gate_release=sim_state.gate_release,
        downstream_level=sim_state.downstream_level,
        reservoir_level=sim_state.reservoir_level,
        progress_percent=min(progress, 100.0),
        dam_name=DAM_CONFIG["name"],
    )


@router.get("/grid", response_model=FloodGridResponse)
async def get_flood_grid(request: Request) -> FloodGridResponse:
    advance_simulation_if_due(request)

    model = get_model(request)
    points = model.get_flood_grid(
        base_lat=BASE_LAT,
        base_lng=BASE_LNG,
        dx_deg=GRID_DX,
        dy_deg=GRID_DY,
    )
    statistics = compute_grid_statistics(points)

    return FloodGridResponse(
        timestamp=datetime.now().isoformat(),
        time_step=sim_state.current_time_step,
        total_points=len(points),
        points=points,
        statistics=statistics,
    )


@router.post("/simulate")
async def start_simulation(request_data: SimulationStartRequest, request: Request) -> Dict:
    return _apply_simulation_start(request_data, request)


@router.post("/simulate/historical/oroville-2017")
async def start_oroville_2017_replay(request: Request) -> Dict:
    event = get_oroville_2017_event()
    seed = event["starter_simulation"]
    response = _apply_simulation_start(
        SimulationStartRequest(
            rainfall_mm_h=seed["rainfall_mm_h"],
            upstream_m3s=seed["upstream_m3s"],
            duration_hours=seed["duration_hours"],
            gate_release_m3s=seed["gate_release_m3s"],
            downstream_level_m=seed["downstream_level_m"],
            reservoir_level_m=seed["reservoir_level_m"],
        ),
        request,
        history_label=event["name"],
    )
    response["event"] = event
    response["status"] = "historical_replay_started"
    return response


@router.post("/simulate/reset")
async def reset_simulation(request: Request) -> Dict:
    sim_state.reset()
    request.app.state.swe_model = build_swe_model()
    return {
        "status": "simulation_reset",
        "dam_name": DAM_CONFIG["name"],
    }


@router.post("/simulate/step")
async def step_simulation(request: Request) -> Dict:
    if not sim_state.is_running:
        raise HTTPException(status_code=400, detail="Simulation not running")

    model = get_model(request)
    advance_one_step(model)
    sim_state.last_advance_time = datetime.now()

    return {
        "current_step": sim_state.current_time_step,
        "total_steps": sim_state.total_steps,
        "is_complete": not sim_state.is_running,
    }


@router.get("/history/{station_id}", response_model=HistoryResponse)
async def get_station_history(station_id: str, hours: int = 24) -> HistoryResponse:
    valid_stations = list(SENSOR_STATIONS.keys())
    if station_id not in valid_stations:
        raise HTTPException(status_code=400, detail=f"Invalid station_id. Must be one of {valid_stations}")

    if sim_state.history:
        entries = [
            HistoryEntry(
                timestamp=entry["timestamp"],
                time_step=entry["time_step"],
                station_id=entry["station_id"],
                water_level=entry["water_level"],
                rainfall=entry["rainfall"],
                flow_rate=entry["flow_rate"],
            )
            for entry in sim_state.history
            if entry["station_id"] == station_id
        ]
    else:
        entries = generate_synthetic_history(station_id, hours)

    return HistoryResponse(station_id=station_id, hours=hours, entries=entries[-hours:])

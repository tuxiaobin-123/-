# -*- coding: utf-8 -*-
"""
FastAPI application entrypoint.

This version keeps the previous API surface but replaces the placeholder
WebSocket stream with messages derived from the live dam-centered simulation.
"""

import asyncio
from datetime import datetime
from typing import Set

import numpy as np
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from config import (
    APP_TITLE,
    APP_VERSION,
    BASE_LAT,
    BASE_LNG,
    CORS_ORIGINS,
    DAM_CONFIG,
    GRID_COLS,
    GRID_DX,
    GRID_DY,
    GRID_ROWS,
    WS_PUSH_INTERVAL,
)
from models.hydraulic import SWEModel
from models.risk_assessment import RiskAssessor
from routers import flood, historical, predict, report, risk, sensors


app = FastAPI(title=APP_TITLE, description="坝区洪水预警与指挥系统后端", version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app_start_time = datetime.now()
risk_assessor = RiskAssessor()


def build_initial_model() -> SWEModel:
    return SWEModel(
        rows=GRID_ROWS,
        cols=GRID_COLS,
        dx=GRID_DX * 111000,
        dy=GRID_DY * 111000,
        dam_config=DAM_CONFIG,
    )


swe_model = build_initial_model()


class SystemInfo(BaseModel):
    app_name: str
    version: str
    uptime_seconds: float
    current_time: str
    model_state: str


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict) -> None:
        stale_connections: list[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                stale_connections.append(connection)

        for connection in stale_connections:
            self.disconnect(connection)

    async def send_personal(self, websocket: WebSocket, message: dict) -> None:
        await websocket.send_json(message)


manager = ConnectionManager()


def _station_grid_index(station_lat: float, station_lng: float, model: SWEModel) -> tuple[int, int]:
    row = int(round((BASE_LAT - station_lat) / GRID_DY))
    col = int(round((station_lng - BASE_LNG) / GRID_DX))
    return int(np.clip(row, 0, model.rows - 1)), int(np.clip(col, 0, model.cols - 1))


def _sample_station_snapshot(station_id: str, model: SWEModel) -> dict:
    station_info = sensors.SENSOR_STATIONS[station_id]
    row, col = _station_grid_index(station_info["lat"], station_info["lng"], model)
    water_level = float(model.dem[row, col] + model.h[row, col])
    flow_rate = float(np.sqrt(model.u[row, col] ** 2 + model.v[row, col] ** 2))
    return {
        "station_id": station_id,
        "name": station_info["name"],
        "water_level": water_level,
        "flow_rate": flow_rate,
        "rainfall": float(flood.sim_state.rainfall_rate),
    }


def _build_live_dashboard_message() -> dict:
    model = getattr(app.state, "swe_model", swe_model)
    grid = model.get_flood_grid(base_lat=BASE_LAT, base_lng=BASE_LNG, dx_deg=GRID_DX, dy_deg=GRID_DY)
    assessed_grid = risk_assessor.assess_grid(grid)
    stats = risk_assessor.get_risk_statistics(assessed_grid)

    realtime_readings = [_sample_station_snapshot(station_id, model) for station_id in sensors.SENSOR_STATIONS]
    readings_by_risk = sorted(
        realtime_readings,
        key=lambda station: (station["water_level"], station["flow_rate"], station["rainfall"]),
        reverse=True,
    )
    primary_station = readings_by_risk[0] if readings_by_risk else None

    if any(point["risk_level"] == "critical" for point in stats["affected_key_points"]) or stats["critical_area"] > 0:
        risk_level = "extreme"
    elif stats["high_risk_area"] > 0:
        risk_level = "high"
    elif stats["medium_risk_area"] > 0:
        risk_level = "medium"
    else:
        risk_level = "low"

    max_water_level = max((reading["water_level"] for reading in realtime_readings), default=0.0)
    avg_rainfall = float(np.mean([reading["rainfall"] for reading in realtime_readings])) if realtime_readings else 0.0

    alert_message = None
    if risk_level in {"extreme", "high"} and primary_station is not None:
        alert_message = (
            f"{primary_station['name']} 风险抬升，当前水位 {primary_station['water_level']:.2f} m，"
            f"流速 {primary_station['flow_rate']:.2f} m/s。"
        )

    return {
        "type": "alert" if alert_message else "update",
        "timestamp": datetime.now().isoformat(),
        "data": {
            "water_level": round(max_water_level, 2),
            "rainfall": round(avg_rainfall, 2),
            "risk_level": risk_level,
            "alert_message": alert_message,
            "station_id": primary_station["station_id"] if primary_station else None,
        },
    }


async def websocket_broadcast_task() -> None:
    while True:
        await asyncio.sleep(WS_PUSH_INTERVAL)
        if not manager.active_connections:
            continue
        try:
            await manager.broadcast(_build_live_dashboard_message())
        except Exception as error:
            print(f"WebSocket broadcast error: {error}")


@app.on_event("startup")
async def startup_event() -> None:
    app.state.swe_model = swe_model
    app.state.flood_router_state = flood.sim_state
    asyncio.create_task(websocket_broadcast_task())


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="healthy", timestamp=datetime.now().isoformat(), version=APP_VERSION)


@app.get("/api/system/info", response_model=SystemInfo)
async def get_system_info() -> SystemInfo:
    uptime = (datetime.now() - app_start_time).total_seconds()
    return SystemInfo(
        app_name=APP_TITLE,
        version=APP_VERSION,
        uptime_seconds=uptime,
        current_time=datetime.now().isoformat(),
        model_state="running",
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        await manager.send_personal(websocket, _build_live_dashboard_message())
        while True:
            raw_message = await websocket.receive_text()
            if raw_message == "ping":
                await manager.send_personal(websocket, {"type": "heartbeat", "timestamp": datetime.now().isoformat()})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as error:
        manager.disconnect(websocket)
        print(f"WebSocket error: {error}")


app.include_router(flood.router)
app.include_router(sensors.router)
app.include_router(predict.router)
app.include_router(risk.router)
app.include_router(report.router)
app.include_router(historical.router)


@app.get("/")
async def root() -> dict:
    return {
        "message": APP_TITLE,
        "version": APP_VERSION,
        "documentation": "/docs",
        "health": "/health",
        "api": {
            "flood": "/api/flood",
            "sensors": "/api/sensors",
            "predict": "/api/predict",
            "risk": "/api/risk",
        },
        "websocket": "ws://localhost:8000/ws",
    }


@app.get("/api")
async def api_root() -> dict:
    return {
        "app": APP_TITLE,
        "version": APP_VERSION,
        "endpoints": {
            "flood": "/api/flood",
            "sensors": "/api/sensors",
            "predict": "/api/predict",
            "risk": "/api/risk",
        },
        "websocket": "ws://localhost:8000/ws",
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(_request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code, "timestamp": datetime.now().isoformat()},
    )


@app.exception_handler(Exception)
async def general_exception_handler(_request, exc: Exception):
    print(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "status_code": 500, "timestamp": datetime.now().isoformat()},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info", access_log=True)

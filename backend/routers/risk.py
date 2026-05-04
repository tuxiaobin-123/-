# -*- coding: utf-8 -*-
"""
Risk assessment and evacuation APIs.

All outputs are now derived from the same dam-centered SWE flood grid used by
the flood and sensor routes.
"""

from datetime import datetime
from typing import Dict, List

from fastapi import APIRouter, Request
from pydantic import BaseModel

from config import BASE_LAT, BASE_LNG, GRID_DX, GRID_DY, KEY_POINTS
from models.risk_assessment import EvacuationRouter, RiskAssessor

router = APIRouter(prefix="/api/risk", tags=["risk"])

risk_assessor = RiskAssessor()
evacuation_router = EvacuationRouter(KEY_POINTS)


class RiskZone(BaseModel):
    id: str
    risk_level: str
    area_km2: float
    population: int
    coordinates: List[List[float]]


class RiskAssessmentResponse(BaseModel):
    timestamp: str
    global_risk_level: str
    risk_score: float
    zones: List[RiskZone]
    affected_key_points: List[Dict]
    statistics: Dict


class WayPoint(BaseModel):
    lat: float
    lng: float
    order: int


class EvacuationRoute(BaseModel):
    route_id: int
    origin: str
    destination: str
    waypoints: List[WayPoint]
    distance_km: float
    risk_score: float
    estimated_minutes: float
    status: str


class EvacuationRoutesResponse(BaseModel):
    total_routes: int
    routes: List[EvacuationRoute]
    recommended_route_id: int


class AffectedPopulation(BaseModel):
    total_affected: int
    critical_zone: int
    high_risk_zone: int
    medium_risk_zone: int
    low_risk_zone: int


class PopulationResponse(BaseModel):
    timestamp: str
    affected_population: AffectedPopulation
    key_points_at_risk: List[Dict]
    recommendation: str


def _get_model_grid(request: Request) -> List[Dict]:
    model = getattr(request.app.state, "swe_model", None)
    if model is None:
        flood_module = getattr(request.app.state, "flood_router_state", None)
        if flood_module and hasattr(flood_module, "build_swe_model"):
            model = flood_module.build_swe_model()
            request.app.state.swe_model = model
        else:
            raise RuntimeError("SWE model is not available on app state")

    return model.get_flood_grid(
        base_lat=BASE_LAT,
        base_lng=BASE_LNG,
        dx_deg=GRID_DX,
        dy_deg=GRID_DY,
    )


def _build_zones_from_grid(assessed_grid: List[Dict], statistics: Dict) -> List[RiskZone]:
    zone_specs = [
      ("critical", "critical_zone"),
      ("high", "high_zone"),
      ("medium", "medium_zone"),
      ("low", "low_zone"),
    ]
    zones: List[RiskZone] = []

    for risk_level, zone_id in zone_specs:
        points = [point for point in assessed_grid if point.get("risk_level") == risk_level and point.get("flooded")]
        if not points:
            continue

        latitudes = [point["lat"] for point in points]
        longitudes = [point["lng"] for point in points]
        coordinates = [
            [max(latitudes), min(longitudes)],
            [max(latitudes), max(longitudes)],
            [min(latitudes), max(longitudes)],
            [min(latitudes), min(longitudes)],
        ]

        zone_population = int(statistics["estimated_affected_population"] * {
            "critical": 0.38,
            "high": 0.32,
            "medium": 0.2,
            "low": 0.1,
        }[risk_level])

        area_lookup = {
            "critical": statistics["critical_area"],
            "high": statistics["high_risk_area"],
            "medium": statistics["medium_risk_area"],
            "low": statistics["low_risk_area"],
        }

        zones.append(
            RiskZone(
                id=zone_id,
                risk_level=risk_level,
                area_km2=round(area_lookup[risk_level] / 1e6, 2),
                population=zone_population,
                coordinates=coordinates,
            )
        )

    return zones


def _global_risk_from_statistics(statistics: Dict) -> tuple[str, float]:
    affected_points = statistics["affected_key_points"]
    if any(point["risk_level"] == "critical" for point in affected_points) or statistics["critical_area"] > 0:
        return "critical", 95.0
    if any(point["risk_level"] == "high" for point in affected_points) or statistics["high_risk_area"] > 0:
        return "high", 78.0
    if statistics["medium_risk_area"] > 0:
        return "medium", 52.0
    return "low", 24.0


@router.get("/assessment", response_model=RiskAssessmentResponse)
async def get_risk_assessment(request: Request) -> RiskAssessmentResponse:
    flood_grid = _get_model_grid(request)
    assessed_grid = risk_assessor.assess_grid(flood_grid)
    statistics = risk_assessor.get_risk_statistics(assessed_grid)
    global_risk_level, risk_score = _global_risk_from_statistics(statistics)

    return RiskAssessmentResponse(
        timestamp=datetime.now().isoformat(),
        global_risk_level=global_risk_level,
        risk_score=risk_score,
        zones=_build_zones_from_grid(assessed_grid, statistics),
        affected_key_points=statistics["affected_key_points"],
        statistics={
            "total_flooded_area_km2": round(statistics["total_flooded_area"] / 1e6, 2),
            "critical_area_km2": round(statistics["critical_area"] / 1e6, 2),
            "high_risk_area_km2": round(statistics["high_risk_area"] / 1e6, 2),
            "medium_risk_area_km2": round(statistics["medium_risk_area"] / 1e6, 2),
            "estimated_affected_population": statistics["estimated_affected_population"],
        },
    )


@router.get("/zones")
async def get_risk_zones_geojson(request: Request) -> Dict:
    flood_grid = _get_model_grid(request)
    assessed_grid = risk_assessor.assess_grid(flood_grid)
    statistics = risk_assessor.get_risk_statistics(assessed_grid)
    zones = _build_zones_from_grid(assessed_grid, statistics)

    color_map = {
        "critical": "#ff0000",
        "high": "#ff6600",
        "medium": "#ffff00",
        "low": "#00ff88",
    }

    features = []
    for zone in zones:
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "risk_level": zone.risk_level,
                    "color": color_map[zone.risk_level],
                    "area_km2": zone.area_km2,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [lng, lat] for lat, lng in zone.coordinates
                    ] + [[zone.coordinates[0][1], zone.coordinates[0][0]]]],
                },
            }
        )

    return {"type": "FeatureCollection", "features": features}


@router.get("/evacuation/routes", response_model=EvacuationRoutesResponse)
async def get_evacuation_routes(request: Request) -> EvacuationRoutesResponse:
    flood_grid = _get_model_grid(request)
    assessed_grid = risk_assessor.assess_grid(flood_grid)
    statistics = risk_assessor.get_risk_statistics(assessed_grid)
    routes = evacuation_router.find_routes(assessed_grid, statistics)

    route_responses = [
        EvacuationRoute(
            route_id=index + 1,
            origin=route.get("origin_name", route["origin"]),
            destination=route.get("destination_name", route["destination"]),
            waypoints=[WayPoint(lat=waypoint[0], lng=waypoint[1], order=waypoint_index) for waypoint_index, waypoint in enumerate(route["waypoints"])],
            distance_km=round(route["distance"] / 1000, 2),
            risk_score=round(route["risk_score"], 1),
            estimated_minutes=round(route["estimated_minutes"], 0),
            status=route["status"],
        )
        for index, route in enumerate(routes)
    ]

    return EvacuationRoutesResponse(
        total_routes=len(route_responses),
        routes=route_responses,
        recommended_route_id=1 if route_responses else 0,
    )


@router.get("/affected-population", response_model=PopulationResponse)
async def get_affected_population(request: Request) -> PopulationResponse:
    flood_grid = _get_model_grid(request)
    assessed_grid = risk_assessor.assess_grid(flood_grid)
    statistics = risk_assessor.get_risk_statistics(assessed_grid)

    total_affected = statistics["estimated_affected_population"]
    critical_pop = int(total_affected * 0.15)
    high_pop = int(total_affected * 0.35)
    medium_pop = int(total_affected * 0.35)
    low_pop = int(total_affected * 0.15)

    if critical_pop > 0:
        recommendation = "紧急：立即启动坝区下游全面转移和最高级应急响应。"
    elif high_pop > 0:
        recommendation = "警戒：组织重点人群转移，保持坝后通道畅通。"
    elif medium_pop > 0:
        recommendation = "预警：保持巡查与广播，准备扩大疏散范围。"
    else:
        recommendation = "平稳：继续监测坝区和下游断面变化。"

    return PopulationResponse(
        timestamp=datetime.now().isoformat(),
        affected_population=AffectedPopulation(
            total_affected=total_affected,
            critical_zone=critical_pop,
            high_risk_zone=high_pop,
            medium_risk_zone=medium_pop,
            low_risk_zone=low_pop,
        ),
        key_points_at_risk=statistics["affected_key_points"],
        recommendation=recommendation,
    )


@router.get("/early-warning")
async def get_early_warning(request: Request) -> Dict:
    flood_grid = _get_model_grid(request)
    assessed_grid = risk_assessor.assess_grid(flood_grid)
    statistics = risk_assessor.get_risk_statistics(assessed_grid)
    global_risk_level, _ = _global_risk_from_statistics(statistics)

    warning_map = {
        "critical": ("red", "红色预警：坝区及下游存在极高风险，请立即执行应急转移。"),
        "high": ("orange", "橙色预警：下游关键点已进入高风险，请快速落实调度与疏散。"),
        "medium": ("yellow", "黄色预警：风险正在扩大，请加强巡检和预案待命。"),
        "low": ("none", "无预警，保持坝区监测。"),
    }
    warning_level, message = warning_map[global_risk_level]

    return {
        "should_warn": warning_level != "none",
        "warning_level": warning_level,
        "affected_population": statistics["estimated_affected_population"],
        "critical_area_km2": round(statistics["critical_area"] / 1e6, 2),
        "affected_key_points": len(statistics["affected_key_points"]),
        "message": message,
    }

# -*- coding: utf-8 -*-
"""
Global configuration for the flood twin system.
"""

APP_TITLE = "基于数字孪生的洪水智能分析与决策系统"
APP_VERSION = "1.0.0"

CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

ACTIVE_CASE_ID = "oroville_dam"

GRID_ROWS = 30
GRID_COLS = 40

# Oroville Dam / Feather River study window.
# Grid origin is the north-west corner; rows go south, columns go east.
BASE_LAT = 39.5900
BASE_LNG = -121.6700

GRID_DX = 0.0065
GRID_DY = 0.0055

SIMULATION_DT = 300
MANNING_COEFF = 0.03
MIN_WATER_DEPTH = 0.001
DRY_TOLERANCE = 1e-3

KEY_POINTS = {
    "oroville_hospital": {
        "name": "Oroville Hospital",
        "lat": 39.5010,
        "lng": -121.5567,
        "type": "hospital",
        "population": 4500,
        "priority": 1,
    },
    "oroville_high_school": {
        "name": "Oroville High School",
        "lat": 39.5097,
        "lng": -121.5468,
        "type": "school",
        "population": 1800,
        "priority": 1,
    },
    "nelson_avenue_shelter": {
        "name": "Nelson Ave 高地避险点",
        "lat": 39.5230,
        "lng": -121.5845,
        "type": "shelter",
        "capacity": 8000,
        "priority": 2,
    },
    "table_mountain_shelter": {
        "name": "Table Mountain 临时避险点",
        "lat": 39.5655,
        "lng": -121.5485,
        "type": "shelter",
        "capacity": 12000,
        "priority": 2,
    },
    "downtown_oroville": {
        "name": "Oroville Downtown",
        "lat": 39.5138,
        "lng": -121.5564,
        "type": "civic",
        "population": 6000,
        "priority": 2,
    },
    "feather_river_fish_hatchery": {
        "name": "Feather River Fish Hatchery",
        "lat": 39.5300,
        "lng": -121.5020,
        "type": "fire_station",
        "priority": 1,
    },
}

SENSOR_STATIONS = {
    "usgs_11406800": {
        "name": "LK Oroville NR Oroville CA",
        "lat": 39.5372,
        "lng": -121.4856,
        "type": "reservoir_level",
        "source": "USGS-11406800",
    },
    "usgs_11406818": {
        "name": "Edward Hyatt PH Power Release",
        "lat": 39.5355,
        "lng": -121.4935,
        "type": "release_flow",
        "source": "USGS-11406818",
    },
    "usgs_11407000": {
        "name": "FEATHER R A OROVILLE CA",
        "lat": 39.52155294,
        "lng": -121.5477477,
        "type": "stream_gage",
        "source": "USGS-11407000",
    },
    "usgs_11406870": {
        "name": "Thermalito Afterbay NR Oroville CA",
        "lat": 39.458333,
        "lng": -121.638056,
        "type": "afterbay_level",
        "source": "USGS-11406870",
    },
}

WARNING_LEVELS = {
    "normal": 2.0,
    "alert": 5.0,
    "dangerous": 8.0,
    "critical": 12.0,
}

RISK_LEVELS = {
    "low": {"depth_range": (0, 0.5), "color": "#00ff00"},
    "medium": {"depth_range": (0.5, 1.0), "color": "#ffff00"},
    "high": {"depth_range": (1.0, 2.0), "color": "#ff6600"},
    "critical": {"depth_range": (2.0, 100), "color": "#ff0000"},
}

MAX_SIMULATION_HOURS = 48
SAVE_HISTORY_STEPS = 12
WS_PUSH_INTERVAL = 2

DAM_CONFIG = {
    "case_id": ACTIVE_CASE_ID,
    "name": "Oroville Dam / Lake Oroville",
    "owner": "California Department of Water Resources",
    "river": "Feather River",
    "dam_lat": 39.537193,
    "dam_lng": -121.485565,
    "dam_row": 10,
    "gate_start_col": 25,
    "gate_end_col": 32,
    "crest_elevation_m": 281.0,
    "normal_reservoir_level_m": 274.0,
    "initial_reservoir_level_m": 266.0,
    "default_gate_opening_ratio": 0.45,
    "default_release_m3s": 900.0,
    "max_release_m3s": 4200.0,
    "downstream_control_level_m": 52.0,
    "dem_grid_path": "backend/data/oroville_dem_grid.json",
    "data_sources": [
        "California DWR Oroville facility page",
        "USGS Water Data for the Nation station pages",
        "USGS 3DEP EPQS sampled DEM control points",
    ],
    "dem_control_points": [
        {"id": "dam_axis", "lat": 39.537193, "lng": -121.485565, "elevation_m": 220.5235, "source": "USGS 3DEP EPQS raster 47646"},
        {"id": "lake_north_arm", "lat": 39.595000, "lng": -121.432000, "elevation_m": 462.9408, "source": "USGS 3DEP EPQS raster 106986"},
        {"id": "lake_middle_fork", "lat": 39.505000, "lng": -121.380000, "elevation_m": 588.0569, "source": "USGS 3DEP EPQS raster 47646"},
        {"id": "spillway_downstream", "lat": 39.520000, "lng": -121.505000, "elevation_m": 114.4419, "source": "USGS 3DEP EPQS raster 85689"},
        {"id": "feather_oroville_gage", "lat": 39.52155294, "lng": -121.5477477, "elevation_m": 49.0008, "source": "USGS 3DEP EPQS raster 85689"},
        {"id": "oroville_city", "lat": 39.513775, "lng": -121.556360, "elevation_m": 49.9356, "source": "USGS 3DEP EPQS raster 113758"},
        {"id": "thermalito_afterbay", "lat": 39.458333, "lng": -121.638056, "elevation_m": 40.1838, "source": "USGS 3DEP EPQS raster 5032"},
        {"id": "downstream_lowland", "lat": 39.445000, "lng": -121.615000, "elevation_m": 32.7745, "source": "USGS 3DEP EPQS raster 132876"},
        {"id": "east_ridge", "lat": 39.548000, "lng": -121.430000, "elevation_m": 255.5856, "source": "USGS 3DEP EPQS raster 47646"},
        {"id": "west_lowland", "lat": 39.505000, "lng": -121.625000, "elevation_m": 53.1686, "source": "USGS 3DEP EPQS raster 92659"},
    ],
}

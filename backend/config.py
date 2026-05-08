# -*- coding: utf-8 -*-
"""
Global configuration for the flood twin system.
研究区域：桑干河（怀仁段）—— 山西省朔州市怀仁县
"""

APP_TITLE = "基于数字孪生的洪水智能分析与决策系统"
APP_VERSION = "1.0.0"

CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

ACTIVE_CASE_ID = "sanggan_river_huairen"

GRID_ROWS = 30
GRID_COLS = 40

# 桑干河（怀仁段）研究窗口
# 网格左上角（西北角），行向南，列向东
BASE_LAT = 39.870   # 西北角纬度
BASE_LNG = 113.280  # 西北角经度

GRID_DX = 0.0055    # 列方向经度步长 ≈ 500 m
GRID_DY = 0.0055    # 行方向纬度步长 ≈ 550 m

SIMULATION_DT = 300
MANNING_COEFF = 0.035   # 桑干河河床糙率（卵石河床）
MIN_WATER_DEPTH = 0.001
DRY_TOLERANCE = 1e-3

# 关键保护目标（怀仁县域内）
KEY_POINTS = {
    "huairen_hospital": {
        "name": "怀仁市人民医院",
        "lat": 39.8268,
        "lng": 113.3872,
        "type": "hospital",
        "population": 3200,
        "priority": 1,
    },
    "huairen_high_school": {
        "name": "怀仁第一中学",
        "lat": 39.8310,
        "lng": 113.3750,
        "type": "school",
        "population": 2400,
        "priority": 1,
    },
    "maan_mountain_shelter": {
        "name": "马鞍山高地避险点",
        "lat": 39.7850,
        "lng": 113.3100,
        "type": "shelter",
        "capacity": 6000,
        "priority": 2,
    },
    "beishan_shelter": {
        "name": "北山应急安置区",
        "lat": 39.8650,
        "lng": 113.3650,
        "type": "shelter",
        "capacity": 10000,
        "priority": 2,
    },
    "huairen_downtown": {
        "name": "怀仁市区（金沙滩镇）",
        "lat": 39.8290,
        "lng": 113.3810,
        "type": "civic",
        "population": 85000,
        "priority": 2,
    },
    "sanggan_bridge": {
        "name": "桑干河大桥（S322省道）",
        "lat": 39.8150,
        "lng": 113.3550,
        "type": "fire_station",
        "priority": 1,
    },
}

# 沿河水文监测站（怀仁段 + 上下游衔接站）
SENSOR_STATIONS = {
    "sgr_upstream": {
        "name": "桑干河上游入境站（应县—怀仁）",
        "lat": 39.855,
        "lng": 113.295,
        "type": "stream_gage",
        "source": "山西省水文局-怀仁上游断面",
    },
    "sgr_huairen_main": {
        "name": "桑干河怀仁主站",
        "lat": 39.820,
        "lng": 113.355,
        "type": "reservoir_level",
        "source": "山西省水文局-怀仁水文站",
    },
    "sgr_south_tributary": {
        "name": "恢河支流汇入口",
        "lat": 39.800,
        "lng": 113.400,
        "type": "release_flow",
        "source": "山西省水文局-恢河口站",
    },
    "sgr_downstream": {
        "name": "桑干河下游出境站（怀仁—山阴）",
        "lat": 39.768,
        "lng": 113.455,
        "type": "afterbay_level",
        "source": "山西省水文局-怀仁出境断面",
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
    "name": "桑干河怀仁段综合治理工程",
    "owner": "山西省朔州市水利局",
    "river": "桑干河（海河流域永定河支流）",
    "dam_lat": 39.8420,
    "dam_lng": 113.3220,
    "dam_row": 5,
    "gate_start_col": 18,
    "gate_end_col": 24,
    "crest_elevation_m": 1068.0,
    "normal_reservoir_level_m": 1058.0,
    "initial_reservoir_level_m": 1048.0,
    "default_gate_opening_ratio": 0.40,
    "default_release_m3s": 120.0,   # 桑干河常规流量远小于 Oroville
    "max_release_m3s": 850.0,        # 历史最大洪峰（1996年）
    "downstream_control_level_m": 1018.0,
    "dem_grid_path": "backend/data/sanggan_dem_grid.json",
    "data_sources": [
        "桑干河（怀仁段）综合治理工程初步设计报告（2024）",
        "山西省水文局桑干河水文站年鉴（1956-2023）",
        "国家基础地理信息中心 1:50000 DEM（SRTM 补充）",
    ],
    "dem_control_points": [
        {"id": "upstream_inlet",   "lat": 39.860, "lng": 113.290, "elevation_m": 1072.0, "source": "初设报告表3-1"},
        {"id": "dam_axis",         "lat": 39.842, "lng": 113.322, "elevation_m": 1052.5, "source": "初设报告图2-3"},
        {"id": "huairen_gage",     "lat": 39.820, "lng": 113.355, "elevation_m": 1038.2, "source": "水文局实测"},
        {"id": "south_tributary",  "lat": 39.800, "lng": 113.400, "elevation_m": 1028.6, "source": "水文局实测"},
        {"id": "downtown_reach",   "lat": 39.825, "lng": 113.380, "elevation_m": 1035.0, "source": "初设报告表3-2"},
        {"id": "downstream_exit",  "lat": 39.768, "lng": 113.455, "elevation_m": 1010.4, "source": "水文局实测"},
        {"id": "north_ridge",      "lat": 39.865, "lng": 113.420, "elevation_m": 1280.0, "source": "地形图量算"},
        {"id": "south_hills",      "lat": 39.760, "lng": 113.310, "elevation_m": 1350.0, "source": "地形图量算"},
    ],
}

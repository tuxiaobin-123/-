# -*- coding: utf-8 -*-
"""
和风天气 API 服务 — 为桑干河（怀仁段）提供真实降雨预报

免费版 API: https://dev.qweather.com/docs/api/grid-weather/
配置方式: 在 backend/.env 中设置 QWEATHER_KEY=你的密钥

未配置时自动降级为历史统计模拟降雨，系统仍可正常运行。
"""

import os
import time
from datetime import datetime, timedelta
from typing import List, Optional

import httpx
import numpy as np

# 桑干河怀仁段坐标（网格中心）
SANGGAN_LAT = 39.815
SANGGAN_LNG = 113.360

_cache: dict = {"ts": 0, "data": None}
CACHE_TTL = 1800  # 30分钟缓存，避免浪费免费额度


async def fetch_qweather_hourly(lat: float = SANGGAN_LAT, lng: float = SANGGAN_LNG) -> Optional[List[float]]:
    """
    从和风天气获取未来72小时逐小时降水量（mm/h）。
    返回 list[float] 长度24，取前24小时预报；失败返回 None。
    """
    api_key = os.environ.get("QWEATHER_KEY", "").strip()
    if not api_key:
        return None

    now = time.time()
    if _cache["data"] is not None and (now - _cache["ts"]) < CACHE_TTL:
        return _cache["data"]

    url = "https://devapi.qweather.com/v7/grid-weather/24h"
    params = {
        "location": f"{lng:.2f},{lat:.2f}",
        "key": api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            body = resp.json()

        if body.get("code") != "200":
            return None

        hourly = body.get("hourly", [])
        precip = [float(h.get("precip", 0)) for h in hourly[:24]]
        while len(precip) < 24:
            precip.append(0.0)

        _cache["ts"] = now
        _cache["data"] = precip
        return precip

    except Exception:
        return None


def _simulate_seasonal_rainfall(hours: int = 24) -> List[float]:
    """
    桑干河流域统计降雨模型（无API密钥时的后备方案）。
    基于华北地区7-9月汛期特征，生成物理合理的逐小时降雨序列。
    """
    month = datetime.now().month
    # 汛期（7-9月）降水概率和强度更高
    is_flood_season = 7 <= month <= 9

    base_prob = 0.35 if is_flood_season else 0.12
    base_intensity = 8.0 if is_flood_season else 2.5

    rng = np.random.default_rng(int(time.time()) // 3600)  # 每小时换种子，缓慢变化
    precip = []

    raining = rng.random() < base_prob
    for _ in range(hours):
        if raining:
            intensity = rng.exponential(base_intensity)
            intensity = float(np.clip(intensity, 0.1, 80.0))
            precip.append(round(intensity, 1))
            raining = rng.random() < 0.72  # 降雨持续性
        else:
            precip.append(0.0)
            raining = rng.random() < (base_prob * 0.4)

    return precip


async def get_rainfall_forecast(hours: int = 24) -> dict:
    """
    获取降雨预报，优先使用和风天气真实数据，降级为统计模拟。

    返回:
        {
          "source": "qweather" | "simulated",
          "location": "桑干河（怀仁段）",
          "forecast": [float, ...],   # mm/h，长度 = hours
          "total_mm": float,
          "peak_mm": float,
          "generated_at": str
        }
    """
    real = await fetch_qweather_hourly()

    if real is not None:
        forecast = (real * ((hours // 24) + 1))[:hours]
        source = "qweather"
    else:
        forecast = _simulate_seasonal_rainfall(hours)
        source = "simulated"

    return {
        "source": source,
        "location": "桑干河（怀仁段）",
        "forecast": forecast,
        "total_mm": round(sum(forecast), 1),
        "peak_mm": round(max(forecast), 1),
        "generated_at": datetime.now().isoformat(),
    }

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
桑干河（怀仁段）DEM 地形网格生成脚本

地理背景：
  - 大同盆地西南缘，桑干河自东向西流经怀仁县
  - 盆地底部高程：1020-1080 m
  - 两侧丘陵：1200-1500 m
  - 河槽宽约 80-150 m，弯曲系数 ~1.3

网格参数：
  - 左上角（西北）：39.870°N，113.280°E
  - 行数 30，列数 40，分辨率 ~550 m × 500 m
  - 覆盖范围：东西约 22 km，南北约 16.5 km

高程控制点（基于地形图估算）：
  站址       纬度      经度      高程(m)
  上游入口  39.870   113.280   1085
  河道中段  39.820   113.360   1038
  怀仁县城  39.830   113.380   1042
  下游出口  39.770   113.460   1018
  北侧丘陵  39.870   113.420   1280
  南侧丘陵  39.760   113.300   1350

输出：backend/data/sanggan_dem_grid.json（与 oroville_dem_grid.json 格式相同）
"""

import json
import sys
from pathlib import Path

import numpy as np

# ── 网格配置（与 config.py 保持一致）──────────────────────────────
ROWS = 30
COLS = 40
BASE_LAT = 39.870   # 西北角纬度
BASE_LNG = 113.280  # 西北角经度
DX = 0.0055         # 列方向（东向）经度步长 ≈ 500 m
DY = 0.0055         # 行方向（南向）纬度步长 ≈ 550 m

OUT_PATH = Path(__file__).parent.parent / "backend" / "data" / "sanggan_dem_grid.json"


def _bilinear_base(rows: int, cols: int) -> np.ndarray:
    """用控制点构造双线性基础地形面。"""
    # 控制点 (row_frac, col_frac, elev_m)
    ctrl = [
        (0.00, 0.00, 1085),   # 西北角（上游）
        (0.50, 0.15, 1060),   # 西侧山地
        (0.33, 0.40, 1042),   # 上游河段
        (0.55, 0.55, 1035),   # 河道中段
        (0.60, 0.65, 1038),   # 怀仁县城附近
        (0.80, 0.80, 1025),   # 下游河段
        (1.00, 1.00, 1012),   # 东南角（下游）
        (0.15, 1.00, 1280),   # 东北丘陵
        (0.00, 1.00, 1310),   # 正北山地
        (1.00, 0.00, 1350),   # 西南山地（马鞍山方向）
        (1.00, 0.50, 1180),   # 南侧高地
        (0.50, 1.00, 1095),   # 东侧缓坡
    ]

    # RBF（薄板样条近似）：最简单的双调和插值
    def rbf_weight(r):
        return r ** 2 * np.log(r + 1e-12)

    r_pts = np.array([(rf * rows, cf * cols) for rf, cf, _ in ctrl])
    elev_pts = np.array([e for _, _, e in ctrl])

    grid = np.zeros((rows, cols))
    for i in range(rows):
        for j in range(cols):
            dists = np.sqrt(((r_pts[:, 0] - i) ** 2) + ((r_pts[:, 1] - j) ** 2))
            w = rbf_weight(dists)
            w += 1e-8
            grid[i, j] = np.average(elev_pts, weights=np.abs(1.0 / (w + 1e-6)))

    # 线性混合使插值更平滑
    from scipy.interpolate import RBFInterpolator
    pts = np.array([[rf * rows, cf * cols] for rf, cf, _ in ctrl])
    vals = elev_pts.astype(float)
    interp = RBFInterpolator(pts, vals, kernel="thin_plate_spline", smoothing=0.5)

    xi = np.array([[i, j] for i in range(rows) for j in range(cols)])
    grid = interp(xi).reshape(rows, cols)
    return grid


def _carve_river_channel(dem: np.ndarray) -> np.ndarray:
    """
    在 DEM 中雕刻桑干河主河槽。
    河道路径：从西北（上游）向东南蜿蜒，符合地形走势。
    """
    dem = dem.copy()
    rows, cols = dem.shape

    # 河道中心线（控制点：行, 列, 河床高程）
    channel_pts = [
        (5,  3,  1072),
        (8,  6,  1065),
        (10, 10, 1058),
        (12, 14, 1050),
        (14, 18, 1044),
        (15, 22, 1040),
        (16, 26, 1036),
        (18, 30, 1028),
        (20, 34, 1022),
        (23, 37, 1016),
        (26, 39, 1012),
    ]

    # 用样条插值生成连续河道中心线
    from scipy.interpolate import interp1d
    ch_rows = np.array([p[0] for p in channel_pts], dtype=float)
    ch_cols = np.array([p[1] for p in channel_pts], dtype=float)
    ch_elvs = np.array([p[2] for p in channel_pts], dtype=float)

    t = np.linspace(0, 1, len(channel_pts))
    t_fine = np.linspace(0, 1, 300)

    row_fn = interp1d(t, ch_rows, kind='cubic')
    col_fn = interp1d(t, ch_cols, kind='cubic')
    elv_fn = interp1d(t, ch_elvs, kind='linear')

    ch_r = row_fn(t_fine)
    ch_c = col_fn(t_fine)
    ch_e = elv_fn(t_fine)

    # 河槽宽度（格点数）：主槽 2 格，漫滩 4 格
    channel_width = 2
    floodplain_width = 4

    for ri, ci, ei in zip(ch_r, ch_c, ch_e):
        ri, ci = int(round(ri)), int(round(ci))
        if not (0 <= ri < rows and 0 <= ci < cols):
            continue
        # 主槽下切 15-20 m
        for dr in range(-channel_width, channel_width + 1):
            for dc in range(-channel_width, channel_width + 1):
                nr, nc = ri + dr, ci + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    dist = (dr**2 + dc**2) ** 0.5
                    if dist <= channel_width:
                        dem[nr, nc] = min(dem[nr, nc], ei - 15 + dist * 3)
        # 漫滩缓坡（梯形横断面）
        for dr in range(-floodplain_width, floodplain_width + 1):
            for dc in range(-floodplain_width, floodplain_width + 1):
                nr, nc = ri + dr, ci + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    dist = (dr**2 + dc**2) ** 0.5
                    if channel_width < dist <= floodplain_width:
                        ratio = (dist - channel_width) / (floodplain_width - channel_width)
                        floodplain_elev = ei - 15 + ratio * 18
                        dem[nr, nc] = min(dem[nr, nc], floodplain_elev)

    return dem


def _add_terrain_noise(dem: np.ndarray, seed: int = 42) -> np.ndarray:
    """添加小幅随机地形起伏，使 DEM 更真实。"""
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, 3.0, dem.shape)
    # 低通滤波平滑噪声
    from scipy.ndimage import uniform_filter
    noise = uniform_filter(noise, size=3)
    return dem + noise


def build_sanggan_dem() -> list:
    """生成完整的桑干河 DEM 网格并返回为 JSON 兼容格式。"""
    print("正在生成桑干河（怀仁段）DEM 网格...")

    try:
        dem = _bilinear_base(ROWS, COLS)
    except ImportError:
        print("  提示: scipy 未安装，使用简化线性插值")
        dem = np.ones((ROWS, COLS)) * 1050
        for i in range(ROWS):
            for j in range(COLS):
                dem[i, j] = 1080 - i * 2.0 - j * 0.5 + abs(i - 15) * 3 + abs(j - 20) * 2

    dem = _carve_river_channel(dem)
    dem = _add_terrain_noise(dem)

    # 构造 JSON 格式（与 oroville_dem_grid.json 相同结构）
    grid_data = []
    for i in range(ROWS):
        for j in range(COLS):
            lat = BASE_LAT - i * DY
            lng = BASE_LNG + j * DX
            elev = float(round(dem[i, j], 2))
            grid_data.append({
                "row": i,
                "col": j,
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "elevation_m": elev
            })

    print(f"  网格尺寸: {ROWS}×{COLS} = {ROWS*COLS} 个格点")
    print(f"  高程范围: {dem.min():.1f} m ~ {dem.max():.1f} m")
    print(f"  河槽最低点: {dem.min():.1f} m")
    print(f"  输出路径: {OUT_PATH}")

    return grid_data


if __name__ == "__main__":
    grid_data = build_sanggan_dem()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(grid_data, f, ensure_ascii=False)
    print(f"✅ DEM 生成完成，共 {len(grid_data)} 个格点。")

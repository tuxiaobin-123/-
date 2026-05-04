# 基于数字孪生的洪水智能分析与决策系统 - 后端

## 项目概述

本项目是一个完整的 FastAPI 后端系统，实现了基于数字孪生技术的洪水监测、预报和应急决策支持功能。

### 核心功能

1. **水动力模型** - 浅水方程(SWE)数值计算
2. **AI预测** - 基于LSTM的24小时水位预测
3. **风险评估** - 实时洪水风险分析与等级划分
4. **避险路径** - 动态避险路线规划
5. **传感器集成** - 多站点实时水文数据
6. **WebSocket推送** - 实时数据流推送

---

## 项目结构

```
flood-twin-system/backend/
├── config.py                    # 全局配置
├── requirements.txt             # 依赖包列表
├── main.py                      # FastAPI主应用
├── models/
│   ├── __init__.py
│   ├── hydraulic.py            # 浅水方程水动力模型
│   ├── lstm_predict.py         # LSTM预测模型
│   └── risk_assessment.py      # 风险评估与避险路由
├── routers/
│   ├── __init__.py
│   ├── flood.py                # 洪水模拟API
│   ├── sensors.py              # 传感器数据API
│   ├── predict.py              # 预测API
│   └── risk.py                 # 风险评估API
└── README.md                    # 本文档
```

---

## 环境配置

### 1. Python 版本要求

- Python 3.8+

### 2. 安装依赖

```bash
cd E:\大坝\flood-twin-system\backend
pip install -r requirements.txt
```

依赖包括：
- **fastapi==0.110.0** - 现代Web框架
- **uvicorn[standard]==0.29.0** - ASGI服务器
- **websockets==12.0** - WebSocket支持
- **numpy==1.26.4** - 数值计算
- **scipy==1.13.0** - 科学计算
- **pydantic==2.6.4** - 数据验证

---

## 快速启动

### 启动服务器

```bash
python main.py
```

或使用uvicorn直接启动：

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 访问应用

- **API文档** (Swagger UI): http://localhost:8000/docs
- **ReDoc文档**: http://localhost:8000/redoc
- **API根路由**: http://localhost:8000/api
- **WebSocket**: ws://localhost:8000/ws

---

## API 接口清单

### 1. 洪水模拟 (`/api/flood`)

```
GET  /api/flood/status           - 获取模拟状态
GET  /api/flood/grid             - 获取当前洪水格点数据
POST /api/flood/simulate         - 启动/重置模拟
POST /api/flood/simulate/step    - 执行单个时间步
GET  /api/flood/history/{id}     - 获取站点历史数据
```

**示例请求：启动模拟**
```bash
curl -X POST "http://localhost:8000/api/flood/simulate" \
  -H "Content-Type: application/json" \
  -d '{
    "rainfall_mm_h": 50.0,
    "duration_hours": 12.0,
    "upstream_m3s": 100.0
  }'
```

### 2. 传感器数据 (`/api/sensors`)

```
GET /api/sensors/realtime              - 所有站点实时数据
GET /api/sensors/stations              - 站点列表
GET /api/sensors/realtime/{station_id} - 单站点实时数据
GET /api/sensors/history/{station_id}  - 站点历史数据(48小时)
GET /api/sensors/stats/{station_id}    - 站点统计信息
```

**示例请求：获取传感器实时数据**
```bash
curl "http://localhost:8000/api/sensors/realtime"
```

### 3. 预测 (`/api/predict`)

```
GET  /api/predict/flood          - 24小时水位预测
GET  /api/predict/risk-trend     - 12小时风险趋势预测
POST /api/predict/scenario       - 情景预测
GET  /api/predict/ensemble       - 集合预测
```

**示例请求：情景预测**
```bash
curl -X POST "http://localhost:8000/api/predict/scenario" \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_type": "heavy_rain",
    "duration_hours": 6.0,
    "intensity": 1.0
  }'
```

### 4. 风险与避险 (`/api/risk`)

```
GET /api/risk/assessment              - 当前风险评估
GET /api/risk/zones                   - 风险区域GeoJSON
GET /api/risk/evacuation/routes       - 避险路径(3条最优)
GET /api/risk/affected-population     - 受影响人口统计
GET /api/risk/early-warning           - 早期预警信息
```

---

## 核心模块说明

### 1. 水动力模型 (`models/hydraulic.py`)

**类**: `SWEModel`

实现浅水方程(Shallow Water Equations)数值计算：

```python
# 初始化
model = SWEModel(rows=30, cols=40, dx=0.003, dy=0.003)

# 单步推进
model.step(dt=300, rainfall_rate=0.001, upstream_inflow=100)

# 获取状态
grid = model.get_flood_grid(base_lat=30.5, base_lng=114.3, dx_deg=0.003, dy_deg=0.003)

# 重置
model.reset()
```

**关键参数**:
- `rows, cols`: 计算网格尺寸
- `dx, dy`: 网格间距
- `rainfall_rate`: 降雨速率 (m/s)
- `upstream_inflow`: 上游入流 (m³/s)

**输出**:
- 水深 `h` (m)
- 流速 `u, v` (m/s)
- 地形 `dem` (m)

### 2. LSTM预测模型 (`models/lstm_predict.py`)

**类**: `LSTMPredictor`

基于NumPy实现的轻量级LSTM，用于24小时水位预测：

```python
# 初始化
predictor = LSTMPredictor(input_size=3, hidden_size=32, output_size=24)

# 预测
predictions = predictor.predict(history, rainfall_forecast)

# 带置信区间
result = predictor.get_prediction_with_confidence(history, rainfall)
# 返回: timestamps, predicted_levels, confidence_upper, confidence_lower, risk_trend
```

**输入**:
- `history`: 历史水位序列 (24小时)
- `rainfall_forecast`: 降雨预报 (24小时)

**输出**:
- 预测水位序列 (24小时)
- 置信上下界
- 风险趋势判断

### 3. 风险评估 (`models/risk_assessment.py`)

**类**: `RiskAssessor`

基于水深和流速的风险评估：

```python
assessor = RiskAssessor()

# 评估格点
assessed = assessor.assess_grid(flood_grid)

# 获取统计
stats = assessor.get_risk_statistics(assessed)
```

**风险等级**:
- `low`: 水深 < 0.5m
- `medium`: 0.5m ~ 1.0m
- `high`: 1.0m ~ 2.0m
- `critical`: > 2.0m

**类**: `EvacuationRouter`

动态避险路径规划：

```python
router = EvacuationRouter(key_points)

# 计算避险路径
routes = router.find_routes(flood_grid, current_risk)
# 返回3条最优路径
```

---

## 配置说明 (`config.py`)

### 网格配置

```python
GRID_ROWS = 30              # 网格行数
GRID_COLS = 40              # 网格列数
GRID_DX = 0.003             # 经度间距(度) ~ 300m
GRID_DY = 0.003             # 纬度间距(度) ~ 300m
SIMULATION_DT = 300         # 时间步长 (秒)
```

### 地理坐标基准（武汉附近）

```python
BASE_LAT = 30.5             # 基准纬度
BASE_LNG = 114.3            # 基准经度
```

### 关键点配置

`KEY_POINTS` 字典包含6个关键设施：
- 武汉中心医院 (医疗)
- 武汉第一中学 (学校)
- 北部避险所 (避险)
- 南部避险所 (避险)
- 市民中心 (市政)
- 消防中队 (应急)

### 预警阈值

```python
WARNING_LEVELS = {
    "normal": 2.0,          # 常水位
    "alert": 5.0,           # 警戒水位
    "dangerous": 8.0,       # 危险水位
    "critical": 12.0,       # 临界水位
}
```

---

## WebSocket 实时推送

### 连接

```javascript
// JavaScript 客户端
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('水位数据:', data.water_levels);
  console.log('风险等级:', data.risk.level);
  console.log('告警信息:', data.alerts);
};

// 保活心跳
setInterval(() => {
  ws.send('ping');
}, 30000);
```

### 推送内容

每2秒推送一次：

```json
{
  "type": "system_update",
  "timestamp": "2026-04-23T10:30:45.123456",
  "water_levels": {
    "upstream": 5.23,
    "urban_a": 4.85,
    "urban_b": 4.42,
    "downstream": 3.78,
    "tributary": 4.15
  },
  "sensors": {
    "total_stations": 5,
    "operational": 5,
    "with_warnings": 1
  },
  "risk": {
    "level": "high",
    "max_water_level": 5.23,
    "status": "monitored"
  },
  "alerts": [
    {
      "type": "water_level_high",
      "severity": "high",
      "message": "水位超过警戒线: 5.23m"
    }
  ]
}
```

---

## 数据流向

```
┌─────────────────┐
│  传感器数据      │
│ (5个站点)       │
└────────┬────────┘
         │
         ↓
┌─────────────────┐      ┌──────────────┐
│  浅水方程模型    │←────→│  LSTM预测    │
│  (水动力仿真)   │      │ (24h预报)    │
└────────┬────────┘      └──────────────┘
         │
         ↓
┌─────────────────┐      ┌──────────────┐
│  风险评估       │←────→│  避险路由    │
│  (等级划分)     │      │ (最优路径)   │
└────────┬────────┘      └──────────────┘
         │
         ↓
┌──────────────────────────────┐
│  WebSocket 实时推送           │
│  - 水位 / 风险 / 告警         │
└──────────────────────────────┘
```

---

## 数值示例

### 传感器数据（实时）

```json
{
  "station_id": "urban_a",
  "name": "城区A站",
  "lat": 30.505,
  "lng": 114.300,
  "water_level": 4.85,
  "rainfall": 23.45,
  "flow_rate": 125.60,
  "battery": 92.3,
  "signal_quality": 78.5
}
```

### 风险评估

```json
{
  "global_risk_level": "high",
  "risk_score": 75.0,
  "affected_population": 15000,
  "critical_area_km2": 12.45,
  "affected_key_points": [
    {
      "id": "central_hospital",
      "name": "武汉中心医院",
      "risk_level": "high",
      "water_depth": 1.85
    }
  ]
}
```

### 避险路径

```json
{
  "route_id": 1,
  "origin": "central_hospital",
  "destination": "shelter_north",
  "distance_km": 2.4,
  "risk_score": 35.2,
  "estimated_minutes": 36.0,
  "status": "warning"
}
```

---

## 性能优化建议

1. **数据库**: 将历史数据存储到PostgreSQL或InfluxDB
2. **缓存**: 使用Redis缓存热点数据
3. **消息队列**: 使用RabbitMQ/Kafka处理高并发
4. **前端优化**: 使用Mapbox GL渲染洪水可视化
5. **模型优化**: 使用CUDA加速大规模计算

---

## 故障排除

### 导入错误

如果遇到导入错误，确保：
1. 所有文件都在正确的目录
2. Python路径包含项目根目录
3. 依赖包已完整安装

```bash
pip install -r requirements.txt --upgrade
```

### WebSocket连接问题

- 检查防火墙配置
- 确保使用 `ws://` (不安全) 或 `wss://` (安全) 协议
- 检查CORS配置

### 数据异常

- 验证坐标范围 (lat: 30.47~30.53, lng: 114.28~114.33)
- 检查时间同步
- 重置模型状态

---

## 后续开发方向

1. **优化水动力模型**: 加入地形细节、河道摩擦、降雨分布异质性
2. **集成真实数据**: 接入国家水文站、气象站数据
3. **增强预报**: 融合数值天气模式(NWP)降雨预报
4. **决策支持**: 添加多目标优化(避险效率 vs 时间成本)
5. **可视化**: 3D浸没分析、风险热力图、动画演变
6. **移动应用**: iOS/Android应急决策助手

---

## 参考资源

- FastAPI 文档: https://fastapi.tiangolo.com/
- NumPy 文档: https://numpy.org/doc/
- 浅水方程: https://en.wikipedia.org/wiki/Shallow_water_equations
- LSTM: https://en.wikipedia.org/wiki/Long_short-term_memory

---

## 许可证

本项目仅供学习和研究使用。

## 联系方式

技术支持: backend@flood-twin-system.local

---

最后更新: 2026-04-23
版本: 1.0.0

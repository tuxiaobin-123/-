# 🌊 基于数字孪生的洪水智能分析与决策系统

> 互联网+大学生创新创业大赛参赛项目 · 完整全栈工程成品

---

## 🚀 一键启动（开发模式）

### 前置条件
- Python 3.11+
- Node.js 20+
- （可选）Docker + Docker Compose

---

### 方式一：本地开发启动（推荐演示用）

**步骤 1 — 启动后端**
```bash
cd backend
pip install -r requirements.txt
python main.py
# 后端运行在 http://localhost:8000
# API文档: http://localhost:8000/docs
```

**步骤 2 — 启动前端**（新终端）
```bash
cd frontend
npm install
npm run dev
# 前端运行在 http://localhost:5173
```

**步骤 3 — 浏览器打开**
```
http://localhost:5173
```

---

### 方式二：Docker Compose（一键部署）

```bash
# 在项目根目录执行
docker-compose up --build

# 访问地址
http://localhost        # 前端界面
http://localhost:8000/docs  # 后端API文档
```

---

## 🗂️ 项目结构

```
flood-twin-system/
├── backend/                    # Python FastAPI 后端
│   ├── main.py                 # 主应用入口（WebSocket + 路由注册）
│   ├── config.py               # 全局配置
│   ├── requirements.txt        # Python依赖
│   ├── models/
│   │   ├── hydraulic.py        # 浅水方程(SWE)水动力模型
│   │   ├── lstm_predict.py     # LSTM洪水预测模型（NumPy实现）
│   │   └── risk_assessment.py  # 风险评估 + 动态避险路径Dijkstra
│   └── routers/
│       ├── flood.py            # 洪水模拟API（启动/状态/格点数据）
│       ├── sensors.py          # 传感器实时/历史数据API
│       ├── predict.py          # AI预测API（24h水位+风险趋势）
│       └── risk.py             # 风险分区+避险路径API
│
├── frontend/                   # React + TypeScript 前端
│   ├── src/
│   │   ├── components/
│   │   │   ├── FloodMap/       # WebGIS洪水地图（Leaflet.js）
│   │   │   ├── Dashboard/      # 顶部6指标仪表盘
│   │   │   ├── PredictionChart/# AI预测ECharts图表
│   │   │   ├── RiskPanel/      # 风险等级评估面板
│   │   │   ├── EvacuationPanel/# 避险路径规划面板
│   │   │   └── SensorPanel/    # 传感器监测状态面板
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts # WebSocket实时连接（自动重连）
│   │   │   └── useFloodData.ts # 数据管理（轮询+初始化）
│   │   ├── api/client.ts       # Axios HTTP客户端
│   │   ├── types/index.ts      # TypeScript类型定义
│   │   └── pages/MainPage.tsx  # 主页面（完整布局容器）
│   └── package.json
│
├── docker-compose.yml          # Docker一键部署
└── README.md                   # 本文档
```

---

## 🧠 核心技术架构

```
【数据层】
  水位传感器(5站) · 降雨监测 · DEM地形数据 · 上游入流
         ↓  多源数据融合
【模型层】
  SWE浅水方程 · 有限体积法 · LSTM水位预测 · 自适应网格
         ↓  数值计算
【计算层】
  NumPy矩阵运算 · WebSocket实时推送 · FastAPI异步处理
         ↓  智能决策
【决策层】
  动态风险评估(4级) · Dijkstra避险路径 · 洪峰时间预测
         ↓  可视化输出
【展示层】
  Leaflet WebGIS地图 · ECharts预测图表 · Ant Design仪表盘
```

---

## 🔌 API接口说明

| 分类 | 接口 | 说明 |
|------|------|------|
| 洪水模拟 | `POST /api/flood/simulate` | 启动模拟（设置降雨/入流参数） |
| 洪水模拟 | `GET /api/flood/grid` | 获取当前洪水格点数据（含坐标/水深/流速） |
| 洪水模拟 | `GET /api/flood/history` | 24小时水位历史 |
| 传感器 | `GET /api/sensors/realtime` | 5站实时数据 |
| 传感器 | `GET /api/sensors/history/{id}` | 48小时历史 |
| AI预测 | `GET /api/predict/flood` | 24小时水位预测+置信区间 |
| AI预测 | `POST /api/predict/scenario` | 情景分析（暴雨/溃坝等） |
| 风险 | `GET /api/risk/assessment` | 综合风险评估 |
| 风险 | `GET /api/risk/evacuation/routes` | 3条最优避险路径 |
| 实时 | `WS /ws` | WebSocket实时推送（2秒/次） |

---

## 🎯 核心创新点

**1. 数字孪生洪水系统**
> 基于SWE浅水方程 + 有限体积法，构建物理-数字双向映射，实时同步洪水演进状态

**2. LSTM智能预测**
> NumPy实现轻量LSTM，输入历史水位+降雨预报，输出24小时水位预测及置信区间，无需深度学习框架依赖

**3. 动态避险路径**
> 改进Dijkstra算法，实时将洪水水深转换为路段权重，每30秒动态更新3条最优撤离路径

**4. 多源数据融合**
> 传感器数据 + 气象预报 + 地形DEM + 历史洪水记录四维融合，提升预测精度

---

## 🎓 比赛答辩说明

**演示步骤建议**：
1. 打开系统，展示地图全貌（洪水淹没范围 + 颜色分级）
2. 拖动"降雨强度"滑块至 120 mm/h，点击"启动模拟"
3. 展示右侧风险等级由"低"升至"高"的实时变化
4. 点击"查看避险路径"，展示3条动态路径规划
5. 切换到"AI预测"图表，展示24小时水位预测曲线
6. 强调：整套系统实时闭环运行，从数据采集到决策输出全自动

---

## 📦 技术栈总览

| 层次 | 技术 | 版本 |
|------|------|------|
| 后端框架 | FastAPI | 0.110 |
| 科学计算 | NumPy / SciPy | 1.26 / 1.13 |
| 前端框架 | React + TypeScript | 18 + 5.2 |
| 地图引擎 | Leaflet.js | 1.9 |
| 图表库 | ECharts | 5.4 |
| UI组件 | Ant Design | 5.15 |
| 构建工具 | Vite | 5.2 |
| 部署 | Docker + Nginx | - |

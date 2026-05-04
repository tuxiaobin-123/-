# 洪水智能分析与决策系统 - 前端项目

基于React 18 + TypeScript + Vite的高性能数字孪生平台前端应用。

## 项目特性

### 核心功能
- **实时WebGIS地图** - 使用Leaflet.js呈现洪水淹没范围、流速分布、避险路径
- **AI预测图表** - ECharts绘制24小时水位预测和风险趋势热力图
- **传感器监控** - 实时监测站网状态展示（水位、降雨、信号强度等）
- **风险评估** - 动态风险分级和分区风险分布可视化
- **避险路径规划** - 实时生成3条最优避险路线
- **WebSocket实时更新** - 自动重连机制的实时数据推送

### 技术栈
- **框架**: React 18.2 + TypeScript 5.2
- **构建工具**: Vite 5.2 (快速HMR)
- **UI库**: Ant Design 5.15 (深色主题)
- **地图**: Leaflet.js 1.9.4
- **图表**: ECharts 5.4.3 + echarts-for-react
- **HTTP**: Axios 1.6.7
- **时间库**: dayjs 1.11.10

### 视觉设计
- 深色科技感主题 (#0a1628为主背景)
- 科技蓝 (#00d4ff) 为主色调
- 危险红 (#ff4d4d)、警告橙 (#ffa500)、安全绿 (#00ff88)
- 玻璃拟态效果 (backdrop-filter: blur)
- 响应式布局 (左侧300px控制面板 + 中间地图 + 右侧320px数据面板)

## 项目结构

```
frontend/
├── src/
│   ├── api/
│   │   └── client.ts              # Axios API封装
│   ├── components/
│   │   ├── FloodMap/              # 核心地图组件 (Leaflet)
│   │   ├── Dashboard/             # 顶部仪表盘 (6个指标卡)
│   │   ├── PredictionChart/       # 预测图表 (ECharts)
│   │   ├── RiskPanel/             # 风险评估面板
│   │   ├── EvacuationPanel/       # 避险路径面板
│   │   └── SensorPanel/           # 传感器状态面板
│   ├── hooks/
│   │   ├── useWebSocket.ts        # WebSocket连接管理
│   │   └── useFloodData.ts        # 数据获取和轮询
│   ├── pages/
│   │   └── MainPage.tsx           # 主页面容器
│   ├── types/
│   │   └── index.ts               # TypeScript类型定义
│   ├── App.tsx                    # 根组件
│   ├── App.css                    # 全局样式
│   ├── index.css                  # 入口样式
│   └── main.tsx                   # 入口文件
├── index.html                     # HTML模板
├── vite.config.ts                 # Vite配置 (带API代理)
├── tsconfig.json                  # TypeScript配置
├── package.json                   # 项目依赖
└── README.md                      # 本文件
```

## 快速开始

### 1. 安装依赖
```bash
npm install
# 或
pnpm install
```

### 2. 开发模式
```bash
npm run dev
# 访问: http://localhost:5173
```

开发模式特性：
- 快速HMR (Hot Module Reload)
- API代理到后端: `/api/*` → `http://localhost:8000`
- WebSocket代理: `/ws/*` → `ws://localhost:8000`

### 3. 生产构建
```bash
npm run build
```

输出：`dist/` 文件夹可直接部署到静态服务器

### 4. 预览构建结果
```bash
npm run preview
```

## 核心组件说明

### FloodMap (地图组件) ⭐
- 底图: OpenStreetMap/卫星图层切换
- 洪水层: 按水深分色的格点 (极危/高危/中危/低危)
- 流速层: 动画箭头显示水流方向和速度
- 传感器标记: 自定义圆形图标(颜色按状态)
- 避险路径: 彩色虚线 (绿/黄/红表示安全度)
- 图例、比例尺、全屏按钮

### Dashboard (仪表盘)
- 当前水位 (m) - 带趋势箭头
- 实时降雨 (mm/h) - 雨滴图标
- 洪峰预测时间 - 倒计时
- 风险等级 - 彩色标签
- 受影响面积 (km²)
- 建议撤离人口

### PredictionChart (预测图表) ⭐
**Tab 1 - 24小时水位预测**
- X轴: 时间 (小时)
- Y轴: 水位 (m)
- 3条线: 预测值 + 置信区间 (上/下界)
- 红色虚线: 5m警戒线
- 区域填充: 置信区间

**Tab 2 - 风险趋势热力图**
- X轴: 24小时时间
- Y轴: 5个监测站点
- 颜色: 绿→黄→橙→红 (低→中→高→极危)

### RiskPanel (风险评估)
- 总体风险等级 (大号彩色徽章 + 脉冲动画)
- 分区风险分布 (5个区域进度条)
- 影响统计 (面积、人口、高风险区数)
- 最新5条告警信息
- 撤离建议 (红色/绿色提示)

### EvacuationPanel (避险路径)
- 3条最优避险路线卡片
- 显示: 起点→终点、距离、预计时间、风险评分
- 状态徽章 (安全/注意/危险) + 渐变色
- 点击路径高亮地图

### SensorPanel (传感器监控)
- 实时监测站点列表
- 每站显示:
  - 状态指示灯 (闪烁动画)
  - 主水位值 (大字体)
  - 降雨 + 流量
  - 电池 + 信号强度 (进度条)
  - 最后更新时间

## API接口约定

后端应提供以下RESTful API（在 `/api` 路径下）:

```
GET  /flood/grid              # 洪水格点数据
GET  /flood/status            # 实时洪水状态
POST /flood/simulate          # 启动模拟
GET  /flood/history           # 历史数据

GET  /sensors/realtime        # 实时传感器数据
GET  /sensors/history/{id}    # 单站历史数据

GET  /predict/flood           # AI水位预测
GET  /predict/risk-trend      # 风险趋势

GET  /risk/assessment         # 风险评估
GET  /risk/evacuation/routes  # 避险路径

GET  /system/info             # 系统信息
```

## WebSocket消息格式

连接: `ws://localhost:8000/ws`

消息格式:
```typescript
{
  type: 'update' | 'alert' | 'heartbeat',
  timestamp: '2024-01-01T12:00:00Z',
  data?: {
    water_level?: number,
    rainfall?: number,
    risk_level?: string,
    alert_message?: string,
    station_id?: string
  }
}
```

## 数据流

```
┌─────────────────────────────────────────────────────┐
│          useFloodData Hook (数据管理)                  │
│  - 初始化: getPrediction() 预测数据                    │
│  - 轮询(5s): getFloodGrid() 实时格点                  │
│           getSensorData() 传感器数据                   │
│  - 首次: getRiskAssessment() 风险评估                 │
│         getEvacuationRoutes() 避险路径                │
└────────┬────────────────────────────────────────────┘
         │
    ┌────┴────────────────────────────────┐
    │                                       │
    ▼                                       ▼
┌──────────────┐                   ┌──────────────┐
│  FloodMap    │                   │ PredictionChart │
│  RiskPanel   │                   │ Dashboard    │
│  SensorPanel │  ◄─────────────►  │ EvacuationPanel│
│              │    组件通信        │              │
└──────────────┘    (Props回调)     └──────────────┘
    △
    │ WebSocket实时更新
    │
┌────────────────────────────┐
│   useWebSocket Hook        │
│   自动重连 (最多5次)        │
│   指数退避延迟             │
└────────────────────────────┘
```

## 性能优化

1. **代码分割**: 组件按需加载
2. **React.memo**: 防止不必要的重渲染
3. **useMemo/useCallback**: 缓存计算和回调
4. **Leaflet地图**: 正确处理挂载/卸载，防止内存泄漏
5. **ECharts**: 使用notMerge和lazyUpdate优化更新
6. **轮询优化**: 5秒间隔，避免频繁更新

## 部署

### Nginx配置示例
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    root /path/to/dist;
    
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /ws {
        proxy_pass ws://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Docker部署
```dockerfile
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

## 浏览器支持

- Chrome/Edge: 最新版本
- Firefox: 最新版本
- Safari: 14+
- 不支持IE

## 环境变量

创建 `.env.local` 文件：
```
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
```

在代码中使用：
```typescript
const apiUrl = import.meta.env.VITE_API_BASE_URL
```

## 常见问题

### 1. 地图不显示
- 检查Leaflet CSS是否正确加载 (`index.html` 中的 `<link>` 标签)
- 确保容器有正确的高度

### 2. WebSocket连接失败
- 检查后端WebSocket服务是否运行
- Vite代理配置中 `/ws` 是否指向正确的后端地址
- 浏览器控制台查看具体错误信息

### 3. 模拟参数滑块不工作
- 检查Ant Design版本是否为5.15+
- 清除浏览器缓存重新加载

### 4. 性能问题
- 减少轮询频率 (调整useFloodData中的interval)
- 在地图上减少格点数量
- 检查浏览器DevTools的Performance标签

## 开发建议

1. **添加新组件**: 在 `src/components/` 下创建文件夹，包含 `index.tsx` 和 `ComponentName.css`
2. **新增API**: 在 `src/api/client.ts` 中添加对应的异步函数
3. **新增Hook**: 在 `src/hooks/` 下创建新文件
4. **样式规范**: 所有CSS遵循深色科技主题，使用CSS变量 `--color-*`
5. **TypeScript**: 所有代码严格遵循类型检查，不使用any

## 许可证

该项目是"互联网+"竞赛参赛作品，仅供学习和参考使用。

## 联系方式

技术问题或建议请联系项目组。

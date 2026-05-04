# 项目启动指南

## 环境要求

- **Node.js**: v18.0.0 或以上
- **npm**: v9.0.0 或以上 (或 pnpm/yarn)
- **操作系统**: Windows / macOS / Linux

## 第一步：安装依赖

```bash
# 进入项目目录
cd frontend

# 使用npm安装
npm install

# 或使用pnpm (更快)
pnpm install

# 或使用yarn
yarn install
```

## 第二步：配置环境变量

复制环境模板文件：
```bash
cp .env.example .env.local
```

编辑 `.env.local` 根据实际后端地址修改：
```
VITE_API_BASE_URL=http://your-backend-address:8000
VITE_WS_URL=ws://your-backend-address:8000/ws
```

## 第三步：启动开发服务器

```bash
npm run dev
```

输出示例：
```
  VITE v5.2.0  ready in 123 ms

  ➜  Local:   http://localhost:5173/
  ➜  Press h + enter to show help
```

打开浏览器访问: **http://localhost:5173**

## 第四步：构建生产版本（可选）

```bash
npm run build
```

生成的文件在 `dist/` 目录，可用于部署到生产环境。

## 常见命令

```bash
# 开发模式（带热更新）
npm run dev

# 生产构建
npm run build

# 预览生产构建
npm run preview

# TypeScript类型检查
npm run type-check

# 清理node_modules和dist
npm run clean
```

## 开发工具推荐

### IDE
- **VS Code** (推荐) + 以下扩展:
  - ES7+ React/Redux/React-Native snippets
  - Prettier - Code formatter
  - ESLint
  - TypeScript Vue Plugin (Volar)

### 浏览器扩展
- **React Developer Tools** - React组件调试
- **Redux DevTools** - 状态管理调试（如使用Redux）

## 调试技巧

### 1. 查看网络请求
打开浏览器DevTools → Network标签，查看API请求详情

### 2. 查看WebSocket连接
DevTools → Network → 筛选WS，检查WebSocket连接状态

### 3. 查看控制台错误
DevTools → Console标签，查看JavaScript错误和警告

### 4. React组件调试
- 安装React DevTools浏览器扩展
- DevTools → Components标签查看组件树和props

### 5. 性能分析
- DevTools → Performance标签，记录应用运行
- 分析CPU、内存、帧率等指标

## 常见问题排查

### 问题：端口5173已被占用
```bash
# 使用其他端口
npm run dev -- --port 3000
```

### 问题：依赖安装失败
```bash
# 清理缓存后重新安装
rm -rf node_modules package-lock.json
npm install
```

### 问题：地图不显示
1. 检查浏览器控制台是否有错误
2. 确保Leaflet CSS正确加载
3. 检查地图容器高度是否正确设置

### 问题：API请求失败
1. 确保后端服务运行在 http://localhost:8000
2. 检查代理配置 (vite.config.ts 中的 proxy)
3. 检查CORS设置（后端应允许前端跨域请求）

### 问题：WebSocket连接失败
1. 后端WebSocket服务应运行在 ws://localhost:8000/ws
2. 网络代理可能阻止WebSocket，检查防火墙和代理设置
3. 浏览器DevTools → Network → WS 检查连接状态

## 最佳实践

### 代码组织
```
src/
├── api/          - API调用封装
├── components/   - React组件
├── hooks/        - 自定义Hooks
├── pages/        - 页面级组件
├── types/        - TypeScript类型
└── utils/        - 工具函数
```

### 提交代码前
```bash
# 1. 运行类型检查
npm run type-check

# 2. 构建测试
npm run build

# 3. 预览构建结果
npm run preview
```

### 性能优化
- 使用React.memo避免不必要重渲染
- 使用useMemo缓存计算结果
- 使用useCallback缓存函数引用
- 减少组件数量和深度

## 获取帮助

1. 查看 `README.md` 获取项目概述
2. 查看各组件的代码注释
3. 查看 `src/types/index.ts` 了解数据结构
4. 查看 `src/api/client.ts` 了解API接口

## 后续部署

### 开发环境
使用 `npm run dev` 启动本地开发服务器

### 测试环境
使用 `npm run build` 构建，部署dist文件夹

### 生产环境
1. 修改 `.env.production` 配置生产API地址
2. 运行 `npm run build`
3. 将dist文件夹部署到Nginx或其他Web服务器
4. 配置反向代理指向后端服务

## 性能目标

- 首屏加载时间: < 2秒
- 地图交互帧率: ≥ 30 FPS
- API响应时间: < 500ms
- WebSocket延迟: < 100ms

祝开发顺利！🚀

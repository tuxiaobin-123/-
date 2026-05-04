import React, { Suspense, lazy, useCallback, useMemo, useState } from 'react'
import { Spin } from 'antd'
import { WifiOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'

import { getFloodHistory, resetSimulation, startHistoricalReplay, startSimulation } from '../api/client'
import { SensorPanel } from '../components/SensorPanel'
import { useFloodData } from '../hooks/useFloodData'
import { useWebSocket } from '../hooks/useWebSocket'
import { AffectedKeyPoint, EvacuationRoute, SensorStation, SimulationParams, StationHistory } from '../types'

import './MainPage.css'

const loadFloodMap = () => import('../components/FloodMap').then((module) => ({ default: module.FloodMap }))
const loadPredictionChart = () =>
  import('../components/PredictionChart').then((module) => ({ default: module.PredictionChart }))
const loadRiskPanel = () => import('../components/RiskPanel').then((module) => ({ default: module.RiskPanel }))
const loadEvacuationPanel = () =>
  import('../components/EvacuationPanel').then((module) => ({ default: module.EvacuationPanel }))
const loadSimulationControls = () =>
  import('../components/SimulationControls').then((module) => ({ default: module.SimulationControls }))

const FloodMap = lazy(loadFloodMap)
const PredictionChart = lazy(loadPredictionChart)
const RiskPanel = lazy(loadRiskPanel)
const EvacuationPanel = lazy(loadEvacuationPanel)
const SimulationControls = lazy(loadSimulationControls)

const NAV_ITEMS = ['实时监测', '洪水预警', '洪水预演', '调度预判', '调度预案']
type RightPanelTab = 'risk' | 'forecast' | 'routes' | 'case'

const LEVEL_COPY: Record<SensorStation['status'], { label: string; color: string }> = {
  normal: { label: '正常', color: '#45f5b0' },
  warning: { label: '预警', color: '#ffd56f' },
  danger: { label: '危险', color: '#ff6673' }
}

const formatCaseCoordinate = (value?: number) => (typeof value === 'number' ? value.toFixed(5) : '-')

const formatCaseNumber = (value?: number, fractionDigits = 0) =>
  typeof value === 'number' ? value.toLocaleString('zh-CN', { maximumFractionDigits: fractionDigits }) : '-'

const DATA_STATUS_COPY = {
  live: { label: 'LIVE 实时', tone: 'good', detail: '已连通 USGS 实时接口，可用于当前观测链路。' },
  cached: { label: 'CACHE 缓存', tone: 'warn', detail: '实时源暂不可达，正在使用最近一次成功抓取的数据。' },
  offline_seed: { label: 'SEED 离线种子', tone: 'muted', detail: '当前网络拦截 USGS，先用透明离线种子跑通流程，不冒充实时。' },
  unavailable: { label: 'DOWN 不可达', tone: 'danger', detail: '实时源和缓存都不可用，需要先恢复外部网络链路。' }
} as const

const SCENARIO_PRESETS: Array<{
  key: string
  name: string
  description: string
  params: SimulationParams
}> = [
  {
    key: 'routine-release',
    name: '常规泄洪',
    description: '中等来流配合常规泄量，适合日常值守和库区调度复盘。',
    params: {
      rainfall_intensity: 35,
      upstream_inflow: 1200,
      duration_hours: 18,
      gate_release: 900,
      downstream_level: 50.5,
      reservoir_level: 266
    }
  },
  {
    key: 'storm-runoff',
    name: '强降雨来水',
    description: '持续强降雨叠加上游来流抬升，用于检验 Oroville 下游站点和城区风险演化。',
    params: {
      rainfall_intensity: 95,
      upstream_inflow: 2100,
      duration_hours: 24,
      gate_release: 1400,
      downstream_level: 52.0,
      reservoir_level: 270
    }
  },
  {
    key: 'downstream-blocking',
    name: '下游顶托',
    description: '下游控制水位偏高，适合检查坝后断面和下游滞洪压力。',
    params: {
      rainfall_intensity: 60,
      upstream_inflow: 1700,
      duration_hours: 20,
      gate_release: 1050,
      downstream_level: 55.0,
      reservoir_level: 268
    }
  },
  {
    key: 'emergency-high-water',
    name: '险情工况',
    description: '高库水位叠加大流量入库，用于应急演练和最不利工况推演。',
    params: {
      rainfall_intensity: 120,
      upstream_inflow: 3200,
      duration_hours: 30,
      gate_release: 2600,
      downstream_level: 56.5,
      reservoir_level: 274
    }
  }
]

const FadeInContent: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isVisible, setIsVisible] = useState(false)

  React.useEffect(() => {
    const frame = window.requestAnimationFrame(() => setIsVisible(true))
    return () => window.cancelAnimationFrame(frame)
  }, [])

  return <div className={`deferred-content ${isVisible ? 'is-visible' : ''}`}>{children}</div>
}

const DeferredPanel: React.FC<{
  label: string
  mapArea?: boolean
  compact?: boolean
  children: React.ReactNode
}> = ({ label, mapArea = false, compact = false, children }) => (
  <Suspense
    fallback={
      <div
        className={['deferred-fallback', mapArea ? 'deferred-fallback-map' : '', compact ? 'deferred-fallback-compact' : '']
          .filter(Boolean)
          .join(' ')}
      >
        <div className="deferred-fallback-header">
          <span className="deferred-fallback-dot" />
          <span>{label}加载中...</span>
        </div>
        <div className="deferred-fallback-skeleton">
          <div className="deferred-fallback-line deferred-fallback-line-lg" />
          <div className="deferred-fallback-line" />
          <div className="deferred-fallback-line deferred-fallback-line-sm" />
        </div>
        <Spin size="small" />
      </div>
    }
  >
    <FadeInContent>{children}</FadeInContent>
  </Suspense>
)

const distanceScore = (station: SensorStation, route: EvacuationRoute) => {
  const routePoints = [route.origin, ...route.waypoints, route.destination]
  return Math.min(
    ...routePoints.map((point) => {
      const latDiff = station.lat - point.lat
      const lngDiff = station.lng - point.lng
      return latDiff * latDiff + lngDiff * lngDiff
    })
  )
}

export const MainPage: React.FC = () => {
  const [selectedStationId, setSelectedStationId] = useState<string | null>(null)
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null)
  const [selectedKeyPointId, setSelectedKeyPointId] = useState<string | null>(null)
  const { floodGrid, sensors, prediction, riskStats, riskZones, evacuationRoutes, simulationStatus, caseProfile, realDataStatus, loading, error, refetchRealtime } =
    useFloodData(selectedStationId)
  const { lastMessage, connectionStatus } = useWebSocket()

  const [currentTime, setCurrentTime] = useState(new Date())
  const [showVelocity, setShowVelocity] = useState(true)
  const [showRoutes, setShowRoutes] = useState(true)
  const [rainfallIntensity, setRainfallIntensity] = useState(50)
  const [upstreamInflow, setUpstreamInflow] = useState(1500)
  const [simulationDuration, setSimulationDuration] = useState(24)
  const [gateRelease, setGateRelease] = useState(900)
  const [downstreamLevel, setDownstreamLevel] = useState(52)
  const [reservoirLevel, setReservoirLevel] = useState(266)
  const [activeNav, setActiveNav] = useState('洪水预警')
  const [stationHistory, setStationHistory] = useState<StationHistory | null>(null)
  const [startingSimulation, setStartingSimulation] = useState(false)
  const [activeScenarioKey, setActiveScenarioKey] = useState<string | null>(null)
  const [activeScenarioName, setActiveScenarioName] = useState<string>('手动参数')
  const [launchingScenarioKey, setLaunchingScenarioKey] = useState<string | null>(null)
  const [rightPanelTab, setRightPanelTab] = useState<RightPanelTab>('risk')
  const [comparisonPresetKey, setComparisonPresetKey] = useState('emergency-high-water')
  const [startingHistoricalReplay, setStartingHistoricalReplay] = useState(false)

  const simulationRunning = startingSimulation || Boolean(simulationStatus?.is_running)

  React.useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  React.useEffect(() => {
    let timeoutId: number | null = null
    let idleId: number | null = null

    const warmHeavyPanels = () => {
      void loadFloodMap()
      void loadPredictionChart()
      void loadRiskPanel()
      void loadEvacuationPanel()
    }

    if (typeof window.requestIdleCallback === 'function') {
      idleId = window.requestIdleCallback(() => warmHeavyPanels(), { timeout: 1200 })
    } else {
      timeoutId = window.setTimeout(() => warmHeavyPanels(), 900)
    }

    return () => {
      if (idleId !== null && typeof window.cancelIdleCallback === 'function') {
        window.cancelIdleCallback(idleId)
      }
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId)
      }
    }
  }, [])

  React.useEffect(() => {
    if (!simulationStatus?.is_running) {
      setStartingSimulation(false)
      return
    }

    const timer = window.setInterval(async () => {
      try {
        await refetchRealtime()
      } catch (stepError) {
        console.error('Failed to refresh simulation state:', stepError)
      }
    }, 1600)

    return () => window.clearInterval(timer)
  }, [refetchRealtime, simulationStatus?.is_running])

  const runSimulation = useCallback(
    async (params: SimulationParams) => {
      setStartingSimulation(true)
      try {
        const result = await startSimulation(params)
        await refetchRealtime()
        return { total_steps: result.total_steps, dam_name: result.dam_name }
      } catch (err) {
        setStartingSimulation(false)
        throw err
      }
    },
    [refetchRealtime]
  )

  const handleStartSimulation = useCallback(
    async () => {
      setActiveScenarioKey(null)
      setActiveScenarioName('手动参数')
      return runSimulation({
        rainfall_intensity: rainfallIntensity,
        upstream_inflow: upstreamInflow,
        duration_hours: simulationDuration,
        gate_release: gateRelease,
        downstream_level: downstreamLevel,
        reservoir_level: reservoirLevel
      })
    },
    [downstreamLevel, gateRelease, rainfallIntensity, reservoirLevel, runSimulation, simulationDuration, upstreamInflow]
  )

  const handleScenarioLaunch = useCallback(
    async (params: SimulationParams) => {
      const preset = SCENARIO_PRESETS.find((item) => item.params === params)
      setLaunchingScenarioKey(preset?.key ?? null)
      setActiveNav('洪水预演')
      setRainfallIntensity(params.rainfall_intensity)
      setUpstreamInflow(params.upstream_inflow)
      setSimulationDuration(params.duration_hours)
      setGateRelease(params.gate_release ?? 900)
      setDownstreamLevel(params.downstream_level ?? 52)
      setReservoirLevel(params.reservoir_level ?? 266)
      try {
        const result = await runSimulation(params)
        setActiveScenarioKey(preset?.key ?? null)
        setActiveScenarioName(preset?.name ?? '预设工况')
        return result
      } finally {
        setLaunchingScenarioKey(null)
      }
    },
    [runSimulation]
  )

  const handleResetSimulation = useCallback(async () => {
    setStartingSimulation(false)
    setRainfallIntensity(50)
    setUpstreamInflow(1500)
    setSimulationDuration(24)
    setGateRelease(900)
    setDownstreamLevel(52)
    setReservoirLevel(266)
    setActiveScenarioKey(null)
    setActiveScenarioName('手动参数')
    await resetSimulation()
    await refetchRealtime()
  }, [refetchRealtime])

  const handleHistoricalReplay = useCallback(async () => {
    setStartingHistoricalReplay(true)
    setActiveNav('洪水预演')
    setActiveScenarioKey('oroville-2017')
    try {
      const result = await startHistoricalReplay()
      setRainfallIntensity(result.rainfall_mm_h)
      setUpstreamInflow(result.upstream_inflow_m3s)
      setSimulationDuration(result.duration_hours)
      setGateRelease(result.gate_release_m3s)
      setDownstreamLevel(result.downstream_level_m)
      setReservoirLevel(result.reservoir_level_m)
      setActiveScenarioName('2017 Oroville 历史回放')
      await refetchRealtime()
    } finally {
      setStartingHistoricalReplay(false)
    }
  }, [refetchRealtime])

  const selectedStation = useMemo(() => {
    if (sensors.length === 0) return null
    if (selectedStationId) {
      const matchedStation = sensors.find((station) => station.station_id === selectedStationId)
      if (matchedStation) return matchedStation
    }
    return [...sensors].sort((a, b) => {
      const weight = { danger: 3, warning: 2, normal: 1 }
      return weight[b.status] - weight[a.status] || b.water_level - a.water_level
    })[0]
  }, [selectedStationId, sensors])

  const selectedRoute = useMemo(() => {
    if (evacuationRoutes.length === 0) return null
    if (selectedRouteId) {
      const directRoute = evacuationRoutes.find((route) => route.id === selectedRouteId)
      if (directRoute) return directRoute
    }
    if (!selectedStation) return evacuationRoutes[0]
    return [...evacuationRoutes].sort((left, right) => distanceScore(selectedStation, left) - distanceScore(selectedStation, right))[0]
  }, [evacuationRoutes, selectedRouteId, selectedStation])

  const selectedKeyPoint = useMemo(() => {
    if (!riskStats?.affected_key_points?.length) return null
    if (selectedKeyPointId) {
      return riskStats.affected_key_points.find((point) => point.id === selectedKeyPointId) || null
    }
    return riskStats.affected_key_points[0]
  }, [riskStats?.affected_key_points, selectedKeyPointId])

  const highestRiskStation = useMemo(() => {
    if (sensors.length === 0) return null
    return [...sensors].sort((left, right) => {
      const severity = { danger: 3, warning: 2, normal: 1 }
      return severity[right.status] - severity[left.status] || right.water_level - left.water_level || right.rainfall - left.rainfall
    })[0]
  }, [sensors])

  const heaviestRainStation = useMemo(() => {
    if (sensors.length === 0) return null
    return [...sensors].sort((left, right) => right.rainfall - left.rainfall)[0]
  }, [sensors])

  React.useEffect(() => {
    if (!selectedStation || evacuationRoutes.length === 0) return
    const bestRoute = [...evacuationRoutes].sort((left, right) => distanceScore(selectedStation, left) - distanceScore(selectedStation, right))[0]
    if (bestRoute && bestRoute.id !== selectedRouteId) {
      setSelectedRouteId(bestRoute.id)
    }
  }, [evacuationRoutes, selectedRouteId, selectedStation])

  const handleStationSelect = useCallback((station: SensorStation) => setSelectedStationId(station.station_id), [])
  const handleRouteSelect = useCallback((route: EvacuationRoute) => setSelectedRouteId(route.id), [])
  const handleKeyPointSelect = useCallback((point: AffectedKeyPoint) => setSelectedKeyPointId(point.id), [])

  const handleLocateHighestRisk = useCallback(() => {
    if (highestRiskStation) setSelectedStationId(highestRiskStation.station_id)
  }, [highestRiskStation])

  const handleLocateLatestAlert = useCallback(() => {
    const stationId = lastMessage?.type === 'alert' ? lastMessage.data?.station_id : null
    if (stationId) setSelectedStationId(stationId)
  }, [lastMessage])

  const handleLocateHeavyRain = useCallback(() => {
    if (heaviestRainStation) setSelectedStationId(heaviestRainStation.station_id)
  }, [heaviestRainStation])

  React.useEffect(() => {
    if (!selectedStation?.station_id) {
      setStationHistory(null)
      return
    }

    let cancelled = false
    const loadHistory = async () => {
      try {
        const history = await getFloodHistory(selectedStation.station_id, 12)
        if (!cancelled) {
          setStationHistory(history)
        }
      } catch (historyError) {
        console.error('Failed to load station history:', historyError)
      }
    }
    void loadHistory()
    return () => {
      cancelled = true
    }
  }, [selectedStation?.station_id, simulationStatus?.current_time_step])

  const selectedStationLevel = selectedStation ? LEVEL_COPY[selectedStation.status] : null

  const overviewStats = useMemo(() => {
    const warningStations = sensors.filter((station) => station.status !== 'normal').length
    const dangerStations = sensors.filter((station) => station.status === 'danger').length
    const heavyRainStations = sensors.filter((station) => station.rainfall >= 20).length
    const highFlowStations = sensors.filter((station) => station.flow_rate >= 2).length
    return { warningStations, dangerStations, heavyRainStations, highFlowStations }
  }, [sensors])

  const overallRiskLabel =
    riskStats?.overall_level === 'extreme' ? '极高' : riskStats?.overall_level === 'high' ? '高' : riskStats?.overall_level === 'medium' ? '中' : '低'

  const connectionLabel = connectionStatus === 'connected' ? '在线' : connectionStatus === 'connecting' ? '连接中' : '离线'
  const mapBadgeLabel = lastMessage?.type === 'alert' ? '重点预警' : '全域联动'
  const mapBadgeValue = lastMessage?.type === 'alert' ? 'ALERT' : 'ACTIVE'

  const etaInsight = useMemo(() => {
    if (!prediction || prediction.timestamps.length === 0 || prediction.predicted_levels.length === 0 || !selectedStation) return null

    const currentLevel = selectedStation.water_level
    const peakLevel = Math.max(...prediction.predicted_levels)
    const peakIndex = prediction.predicted_levels.findIndex((level) => level === peakLevel)
    const peakTimestamp = prediction.timestamps[peakIndex]
    const highRiskIndex = prediction.risk_trend.findIndex((level) => level === 'high' || level === 'extreme')
    const highRiskTimestamp = highRiskIndex >= 0 ? prediction.timestamps[highRiskIndex] : null
    const riseThreshold = currentLevel + 0.3
    const riseIndex = prediction.predicted_levels.findIndex((level) => level >= riseThreshold)
    const riseTimestamp = riseIndex >= 0 ? prediction.timestamps[riseIndex] : null

    const formatDelta = (timestamp: string | null) => {
      if (!timestamp) return '未触发'
      const diffMinutes = Math.max(0, Math.round((new Date(timestamp).getTime() - Date.now()) / 60000))
      if (diffMinutes < 60) return `${diffMinutes} 分钟`
      const hours = Math.floor(diffMinutes / 60)
      const minutes = diffMinutes % 60
      return `${hours} 小时 ${minutes} 分钟`
    }

    return {
      riseEta: formatDelta(riseTimestamp),
      highRiskEta: formatDelta(highRiskTimestamp),
      peakEta: formatDelta(peakTimestamp),
      peakLevel
    }
  }, [prediction, selectedStation])

  const dispatchInsight = useMemo(() => {
    const upstream = simulationStatus?.upstream_inflow ?? upstreamInflow
    const release = simulationStatus?.gate_release ?? gateRelease
    const reservoir = simulationStatus?.reservoir_level ?? reservoirLevel
    const downstream = simulationStatus?.downstream_level ?? downstreamLevel
    const flowBalance = release - upstream
    const reservoirBuffer = 42 - reservoir
    const downstreamPressure = downstream - 18.5

    if (flowBalance >= 250 && reservoirBuffer > 1.0 && downstreamPressure < 1.0) {
      return {
        label: '削峰有效',
        summary: `当前泄量高于入流 ${flowBalance.toFixed(0)} m³/s，库区仍有 ${reservoirBuffer.toFixed(1)} m 安全余量。`,
        color: '#45f5b0'
      }
    }
    if (flowBalance < 0 && reservoirBuffer < 1.0) {
      return {
        label: '风险积压',
        summary: `当前入流高于泄量 ${Math.abs(flowBalance).toFixed(0)} m³/s，库区余量仅 ${reservoirBuffer.toFixed(1)} m，建议评估增泄。`,
        color: '#ff6673'
      }
    }
    if (downstreamPressure > 1.6) {
      return {
        label: '下游承压',
        summary: `下游控制水位抬高 ${downstreamPressure.toFixed(1)} m，继续增泄会放大坝后压力。`,
        color: '#ff9858'
      }
    }
    return {
      label: '调度平衡',
      summary: `当前入泄差值 ${flowBalance.toFixed(0)} m³/s，库区余量 ${reservoirBuffer.toFixed(1)} m，建议持续跟踪。`,
      color: '#ffd56f'
    }
  }, [downstreamLevel, gateRelease, reservoirLevel, simulationStatus, upstreamInflow])

  const selectedComparisonPreset = SCENARIO_PRESETS.find((preset) => preset.key === comparisonPresetKey) || SCENARIO_PRESETS[0]

  const caseStations = useMemo(() => Object.entries(caseProfile?.sensor_stations || {}), [caseProfile?.sensor_stations])
  const caseKeyPoints = useMemo(() => Object.entries(caseProfile?.key_points || {}), [caseProfile?.key_points])
  const demCacheEnabled = Boolean(caseProfile?.dem_grid_cache?.enabled)
  const demCacheMode = caseProfile?.dem_grid_cache?.mode || 'control_point_interpolation'
  const usgsLiveSeriesCount = realDataStatus?.usgs.series.reduce((total, series) => total + series.count, 0) || 0
  const dataStatus = realDataStatus?.usgs.status || 'unavailable'
  const dataStatusCopy = DATA_STATUS_COPY[dataStatus]
  const historicalEvent = realDataStatus?.historical_event

  const planComparison = useMemo(() => {
    const currentRelease = simulationStatus?.gate_release ?? gateRelease
    const currentInflow = simulationStatus?.upstream_inflow ?? upstreamInflow
    const currentReservoir = simulationStatus?.reservoir_level ?? reservoirLevel
    const compareRelease = selectedComparisonPreset.params.gate_release ?? 0
    const compareInflow = selectedComparisonPreset.params.upstream_inflow
    const compareReservoir = selectedComparisonPreset.params.reservoir_level ?? 0

    return {
      releaseDelta: currentRelease - compareRelease,
      inflowDelta: currentInflow - compareInflow,
      reservoirDelta: currentReservoir - compareReservoir,
      currentSummary: currentRelease >= currentInflow ? '当前方案偏重削峰' : '当前方案偏重蓄水，需关注库水位继续抬升',
      compareSummary: compareRelease > currentRelease ? '对照方案需要更大泄量换取下游更早预警' : '对照方案与当前方案接近'
    }
  }, [gateRelease, reservoirLevel, selectedComparisonPreset.params.gate_release, selectedComparisonPreset.params.reservoir_level, selectedComparisonPreset.params.upstream_inflow, simulationStatus, upstreamInflow])

  if (loading && floodGrid.length === 0) {
    return (
      <div className="loading-container">
        <Spin size="large">
          <div style={{ padding: 50, textAlign: 'center', color: '#e0e0e0' }}>
            <div style={{ fontSize: 18, marginBottom: 8 }}>正在加载防洪智慧大屏...</div>
            <div style={{ fontSize: 13, color: '#84acc8' }}>坝区模型、预警面板与场景地图初始化中</div>
          </div>
        </Spin>
      </div>
    )
  }

  return (
    <div className="main-page screen-page">
      <div className="screen-shell" />
      <header className="screen-header">
        <div className="brand-block">
          <div className="brand-icon">F</div>
          <div className="brand-copy">
            <div className="brand-title">防洪“四预”智慧水利平台</div>
            <div className="brand-subtitle">Dam-Centered Flood Command Center</div>
          </div>
        </div>

        <nav className="screen-nav">
          {NAV_ITEMS.map((item) => (
            <button key={item} className={`nav-chip ${activeNav === item ? 'is-active' : ''}`} onClick={() => setActiveNav(item)}>
              {item}
            </button>
          ))}
        </nav>

        <div className="screen-meta">
          <div className={`meta-chip meta-connection ${connectionStatus}`}>
            <WifiOutlined />
            <span>{connectionLabel}</span>
          </div>
          <div className="meta-clock">
            <span>{dayjs(currentTime).format('YYYY-MM-DD HH:mm:ss')}</span>
            <span className="meta-weather">晴 26°C</span>
          </div>
        </div>
      </header>

      <section className="screen-overview" aria-label="关键态势摘要">
        <div className="overview-card">
          <span>整体风险</span>
          <strong>{overallRiskLabel}</strong>
          <em>{riskStats?.warning_message || '持续监测坝区状态'}</em>
        </div>
        <div className="overview-card">
          <span>影响范围</span>
          <strong>{(riskStats?.affected_area_km2 || 0).toFixed(1)} km²</strong>
          <em>{(riskStats?.affected_population || 0).toLocaleString('zh-CN')} 人受影响</em>
        </div>
        <div className="overview-card">
          <span>模型进度</span>
          <strong>{simulationStatus ? `${simulationStatus.progress_percent.toFixed(1)}%` : '待启动'}</strong>
          <em>{simulationStatus ? `${simulationStatus.current_time_step} / ${simulationStatus.total_steps} 步` : '选择工况开始推演'}</em>
        </div>
        <div className="overview-card">
          <span>当前焦点</span>
          <strong>{selectedStation?.name || simulationStatus?.dam_name || 'Oroville Dam'}</strong>
          <em>{selectedStation ? `${selectedStation.water_level.toFixed(2)} m · ${selectedStationLevel?.label}` : '等待站点联动'}</em>
        </div>
      </section>

      <main className="screen-layout">
        <aside className="side-column left-column">
          <section className="screen-module module-control command-panel">
            <div className="module-head">
              <span className="module-orb" />
              <div>
                <h3>工况模拟</h3>
                <p>选择情景，启动真实坝区推演</p>
              </div>
            </div>
            <DeferredPanel label="模拟控制" compact>
              <SimulationControls
                simulationRunning={simulationRunning}
                rainfallIntensity={rainfallIntensity}
                upstreamInflow={upstreamInflow}
                simulationDuration={simulationDuration}
                gateRelease={gateRelease}
                downstreamLevel={downstreamLevel}
                reservoirLevel={reservoirLevel}
                simulationStatus={simulationStatus}
                scenarioPresets={SCENARIO_PRESETS}
                activeScenarioKey={activeScenarioKey}
                launchingScenarioKey={launchingScenarioKey}
                onRainfallChange={setRainfallIntensity}
                onUpstreamChange={setUpstreamInflow}
                onDurationChange={setSimulationDuration}
                onGateReleaseChange={setGateRelease}
                onDownstreamLevelChange={setDownstreamLevel}
                onReservoirLevelChange={setReservoirLevel}
                onSimulationStarted={handleStartSimulation}
                onScenarioLaunch={handleScenarioLaunch}
                onReset={handleResetSimulation}
              />
            </DeferredPanel>
          </section>

          <section className="screen-module module-monitor">
            <div className="module-head">
              <span className="module-orb" />
              <div>
                <h3>监测站点</h3>
                <p>真实站点状态与当前联动焦点</p>
              </div>
            </div>

            <div className="station-summary-grid">
              <div className="warning-grid-card">
                <span>预警站点</span>
                <strong>{overviewStats.warningStations}</strong>
              </div>
              <div className="warning-grid-card">
                <span>危险站点</span>
                <strong>{overviewStats.dangerStations}</strong>
              </div>
              <div className="warning-grid-card">
                <span>强降雨</span>
                <strong>{overviewStats.heavyRainStations}</strong>
              </div>
              <div className="warning-grid-card">
                <span>高流速</span>
                <strong>{overviewStats.highFlowStations}</strong>
              </div>
            </div>

            <DeferredPanel label="水位监测" compact>
              <SensorPanel stations={sensors} selectedStationId={selectedStation?.station_id ?? null} onStationSelect={handleStationSelect} />
            </DeferredPanel>
          </section>

          <section className="screen-module module-compare">
            <div className="module-head">
              <span className="module-orb" />
              <div>
                <h3>方案对比</h3>
                <p>当前调度与预设工况快速比较</p>
              </div>
            </div>
            <div className="compare-tabs">
              {SCENARIO_PRESETS.map((preset) => (
                <button
                  key={preset.key}
                  type="button"
                  className={`tool-chip ${comparisonPresetKey === preset.key ? 'is-active' : ''}`}
                  onClick={() => setComparisonPresetKey(preset.key)}
                >
                  {preset.name}
                </button>
              ))}
            </div>
            <div className="compare-copy">
              <div>{planComparison.currentSummary}</div>
              <div>对照：{selectedComparisonPreset.name} · {planComparison.compareSummary}</div>
            </div>
            <div className="compare-grid">
              <div className="warning-grid-card">
                <span>泄量差值</span>
                <strong>{planComparison.releaseDelta > 0 ? '+' : ''}{planComparison.releaseDelta.toFixed(0)}</strong>
              </div>
              <div className="warning-grid-card">
                <span>入流差值</span>
                <strong>{planComparison.inflowDelta > 0 ? '+' : ''}{planComparison.inflowDelta.toFixed(0)}</strong>
              </div>
              <div className="warning-grid-card">
                <span>库水位差</span>
                <strong>{planComparison.reservoirDelta > 0 ? '+' : ''}{planComparison.reservoirDelta.toFixed(1)}</strong>
              </div>
            </div>
          </section>
        </aside>

        <section className="map-stage">
          <div className="map-stage-head">
            <div className="map-stage-title">
              <span className="module-orb" />
              <div>
                <h3>Oroville Dam 洪水预警主视图</h3>
                <p>坝体、库区、Feather River 河道、风险层与监测站联动</p>
              </div>
            </div>
            <div className="map-stage-tools">
              <button className={`tool-chip ${showVelocity ? 'is-active' : ''}`} onClick={() => setShowVelocity((value) => !value)}>
                流速
              </button>
              <button className={`tool-chip ${showRoutes ? 'is-active' : ''}`} onClick={() => setShowRoutes((value) => !value)}>
                路线
              </button>
              <button className="tool-chip" onClick={handleLocateHighestRisk} disabled={!highestRiskStation}>
                最高风险
              </button>
              <button className="tool-chip" onClick={handleLocateHeavyRain} disabled={!heaviestRainStation}>
                强降雨
              </button>
              <button className="tool-chip" onClick={handleLocateLatestAlert} disabled={lastMessage?.type !== 'alert'}>
                最新告警
              </button>
              <button className="tool-chip case-fullscreen-link" onClick={() => { window.location.href = '/case-data' }}>
                案例全屏
              </button>
              <div className="map-badge">
                <span>{mapBadgeLabel}</span>
                <strong>{mapBadgeValue}</strong>
              </div>
            </div>
          </div>

          <div className="map-stage-frame">
            <div className="map-stage-rings" />
            <div className="map-stage-grid" />
            <div className="map-stage-shine" />
            <div className="map-corner map-corner-tl" />
            <div className="map-corner map-corner-tr" />
            <div className="map-corner map-corner-bl" />
            <div className="map-corner map-corner-br" />

            <DeferredPanel label="地图舞台" mapArea>
              <div className="map-shell">
                <FloodMap
                  floodGrid={floodGrid}
                  sensors={sensors}
                  evacuationRoutes={evacuationRoutes}
                  riskZones={riskZones}
                  keyPoints={riskStats?.affected_key_points || []}
                  showVelocity={showVelocity}
                  showRoutes={showRoutes}
                  selectedStationId={selectedStation?.station_id ?? null}
                  selectedRouteId={selectedRoute?.id ?? null}
                  selectedKeyPointId={selectedKeyPoint?.id ?? null}
                  onStationSelect={handleStationSelect}
                  onKeyPointSelect={handleKeyPointSelect}
                />
              </div>
            </DeferredPanel>
          </div>

          <div className="map-status-strip">
            <div className="status-kpi">
              <span>最新告警</span>
              <strong>{lastMessage?.type === 'alert' ? lastMessage.data?.alert_message || '站点出现异常波动' : '暂无新增告警'}</strong>
            </div>
            <div className="status-kpi">
              <span>坝区调度</span>
              <strong>{simulationStatus ? `${simulationStatus.gate_release.toFixed(0)} m³/s · ${activeScenarioName}` : '待启动'}</strong>
            </div>
            <div className="status-kpi">
              <span>模拟进度</span>
              <strong>
                {simulationStatus
                  ? `${simulationStatus.current_time_step} / ${simulationStatus.total_steps} · ${simulationStatus.progress_percent.toFixed(1)}%`
                  : '未启动'}
              </strong>
            </div>
            <div className="status-kpi">
              <span>影响对象</span>
              <strong>{selectedKeyPoint ? `${selectedKeyPoint.name} · ${selectedKeyPoint.water_depth.toFixed(2)} m` : '暂无关键对象受影响'}</strong>
            </div>
          </div>
        </section>

        <aside className="side-column right-column">
          <section className="screen-module right-workbench">
            <div className="module-head">
              <span className="module-orb" />
              <div>
                <h3>态势详情</h3>
                <p>点选地图或站点后在这里查看详情</p>
              </div>
            </div>

            <div className="focus-detail-card">
              <div className="focus-detail-head">
                <div>
                  <span>{simulationStatus?.dam_name || 'Oroville Dam'}</span>
                  <strong>{selectedStation?.name || '选择一个监测站点'}</strong>
                </div>
                <div className="command-badge" style={{ color: selectedStationLevel?.color, borderColor: `${selectedStationLevel?.color || '#6edcff'}66` }}>
                  {selectedStationLevel?.label || 'MONITOR'}
                </div>
              </div>

              {selectedStation && (
                <div className="focus-metric-grid">
                  <div className="command-item">
                    <span>实时水位</span>
                    <strong>{selectedStation.water_level.toFixed(2)} m</strong>
                  </div>
                  <div className="command-item">
                    <span>降雨强度</span>
                    <strong>{selectedStation.rainfall.toFixed(1)} mm/h</strong>
                  </div>
                  <div className="command-item">
                    <span>局部流速</span>
                    <strong>{selectedStation.flow_rate.toFixed(2)} m/s</strong>
                  </div>
                  <div className="command-item">
                    <span>更新时间</span>
                    <strong>{dayjs(selectedStation.last_update).format('HH:mm:ss')}</strong>
                  </div>
                </div>
              )}

              <div className="focus-insight">
                <span>调度收益反馈</span>
                <strong style={{ color: dispatchInsight.color }}>{dispatchInsight.label}</strong>
                <p>{dispatchInsight.summary}</p>
              </div>

              {etaInsight && (
                <div className="focus-eta-row">
                  <div>
                    <span>高风险预计</span>
                    <strong>{etaInsight.highRiskEta}</strong>
                  </div>
                  <div>
                    <span>峰值到达</span>
                    <strong>{etaInsight.peakEta}</strong>
                  </div>
                </div>
              )}
            </div>

            <div className="right-tabs">
              {[
                ['risk', '风险告警'],
                ['forecast', '预测回灌'],
                ['routes', '避险路线'],
                ['case', '案例数据']
              ].map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  className={`right-tab ${rightPanelTab === key ? 'is-active' : ''}`}
                  onClick={() => setRightPanelTab(key as RightPanelTab)}
                >
                  {label}
                </button>
              ))}
            </div>

            <div className="right-tab-content">
              {rightPanelTab === 'risk' && (
                <DeferredPanel label="风险评估">
                  <RiskPanel
                    riskStats={riskStats}
                    wsMessage={lastMessage}
                    selectedKeyPointId={selectedKeyPoint?.id ?? null}
                    onKeyPointSelect={handleKeyPointSelect}
                  />
                </DeferredPanel>
              )}
              {rightPanelTab === 'forecast' && (
                <DeferredPanel label="预测图表" compact>
                  <PredictionChart prediction={prediction} sensors={sensors} stationHistory={stationHistory} focusedStationName={selectedStation?.name ?? null} />
                </DeferredPanel>
              )}
              {rightPanelTab === 'routes' && (
                <DeferredPanel label="避险路径" compact>
                  <EvacuationPanel routes={evacuationRoutes} selectedRouteId={selectedRoute?.id ?? null} onRouteSelect={handleRouteSelect} />
                </DeferredPanel>
              )}
              {rightPanelTab === 'case' && (
                <div className="case-data-panel">
                  <div className="case-identity-card">
                    <span>当前落地案例</span>
                    <strong>{caseProfile?.dam.name || simulationStatus?.dam_name || 'Oroville Dam / Lake Oroville'}</strong>
                    <p>
                      {caseProfile?.dam.river || 'Feather River'} · {formatCaseCoordinate(caseProfile?.dam.lat)},{' '}
                      {formatCaseCoordinate(caseProfile?.dam.lng)}
                    </p>
                  </div>

                  <div className="case-data-grid">
                    <div>
                      <span>DEM 缓存</span>
                      <strong className={demCacheEnabled ? 'case-status-good' : ''}>{demCacheEnabled ? '已启用' : '未启用'}</strong>
                      <em>{demCacheMode}</em>
                    </div>
                    <div>
                      <span>网格规模</span>
                      <strong>
                        {caseProfile ? `${caseProfile.grid.rows} x ${caseProfile.grid.cols}` : '-'}
                      </strong>
                      <em>{caseProfile ? `${caseProfile.grid.dx_deg}° / ${caseProfile.grid.dy_deg}°` : '等待案例接口'}</em>
                    </div>
                    <div>
                      <span>监测站</span>
                      <strong>{caseStations.length}</strong>
                      <em>USGS / 坝区联动站点</em>
                    </div>
                    <div>
                      <span>关键对象</span>
                      <strong>{caseKeyPoints.length}</strong>
                      <em>学校、医院、避险点、河道断面</em>
                    </div>
                  </div>

                  <section className="case-section real-data-section">
                    <div className="case-section-head">
                      <strong>真实数据链路</strong>
                      <span>{realDataStatus ? dayjs(realDataStatus.checked_at).format('HH:mm:ss') : '检查中'}</span>
                    </div>
                    <div className={`data-trust-banner data-trust-${dataStatusCopy.tone}`}>
                      <div>
                        <span>数据可信等级</span>
                        <strong>{dataStatusCopy.label}</strong>
                      </div>
                      <p>{dataStatusCopy.detail}</p>
                    </div>
                    <div className="case-data-grid">
                      <div>
                        <span>USGS 时序</span>
                        <strong className={realDataStatus?.usgs.status === 'live' ? 'case-status-good' : ''}>{dataStatus}</strong>
                        <em>{usgsLiveSeriesCount.toLocaleString('zh-CN')} 条观测样本</em>
                      </div>
                      <div>
                        <span>历史校准事件</span>
                        <strong>{historicalEvent?.event_id || 'oroville_2017'}</strong>
                        <em>{historicalEvent?.period.start.slice(0, 10) || '2017-02-06'} 起</em>
                      </div>
                    </div>
                    <div className="real-series-list">
                      {(realDataStatus?.usgs.series || []).slice(0, 4).map((series) => (
                        <div key={`${series.station_id}-${series.parameter_code}`} className="real-series-item">
                          <span>{series.station_name}</span>
                          <strong>
                            {series.parameter_name}: {series.latest_value ?? '-'}
                          </strong>
                          <em>{series.count} samples · {series.latest_time ? dayjs(series.latest_time).format('MM-DD HH:mm') : 'no latest'}</em>
                        </div>
                      ))}
                    </div>
                    {realDataStatus?.usgs.last_error && <p className="real-data-warning">实时源暂不可达，已使用缓存或等待下次探测：{realDataStatus.usgs.last_error}</p>}
                    {historicalEvent && (
                      <div className="historical-evidence">
                        <div className="historical-evidence-head">
                          <strong>2017 回放证据链</strong>
                          <span>{historicalEvent.milestone_count} 节点 · {historicalEvent.calibration_target_count} 目标</span>
                        </div>
                        <div className="event-timeline">
                          {historicalEvent.known_milestones.map((milestone) => (
                            <div key={`${milestone.time}-${milestone.label}`} className="event-node">
                              <span>{milestone.time}</span>
                              <strong>{milestone.label}</strong>
                            </div>
                          ))}
                        </div>
                        <div className="calibration-targets">
                          {historicalEvent.calibration_targets.map((target) => (
                            <span key={target}>{target}</span>
                          ))}
                        </div>
                      </div>
                    )}
                    <button type="button" className="historical-replay-button" onClick={handleHistoricalReplay} disabled={startingHistoricalReplay}>
                      {startingHistoricalReplay ? '正在启动 2017 回放...' : '运行 2017 Oroville 历史回放'}
                    </button>
                  </section>

                  <section className="case-section">
                    <div className="case-section-head">
                      <strong>坝体 / 河道边界</strong>
                      <span>不是普通地图底图</span>
                    </div>
                    <div className="case-fact-list">
                      <div>
                        <span>坝顶高程</span>
                        <strong>{formatCaseNumber(caseProfile?.dam.crest_elevation_m, 1)} m</strong>
                      </div>
                      <div>
                        <span>常水位</span>
                        <strong>{formatCaseNumber(caseProfile?.dam.normal_reservoir_level_m, 1)} m</strong>
                      </div>
                      <div>
                        <span>案例编号</span>
                        <strong>{caseProfile?.case_id || 'oroville_dam'}</strong>
                      </div>
                    </div>
                  </section>

                  <section className="case-section">
                    <div className="case-section-head">
                      <strong>真实监测点</strong>
                      <span>{caseStations.length} 个站点</span>
                    </div>
                    <div className="case-list">
                      {caseStations.map(([stationId, station]) => (
                        <button key={stationId} type="button" className="case-list-item" onClick={() => setSelectedStationId(stationId)}>
                          <span>{station.name}</span>
                          <strong>{station.type}</strong>
                          <em>
                            {formatCaseCoordinate(station.lat)}, {formatCaseCoordinate(station.lng)}
                          </em>
                        </button>
                      ))}
                    </div>
                  </section>

                  <section className="case-section">
                    <div className="case-section-head">
                      <strong>关键对象</strong>
                      <span>影响链路输入</span>
                    </div>
                    <div className="case-chip-list">
                      {caseKeyPoints.map(([pointId, point]) => (
                        <span key={pointId} className="case-pill">
                          {point.name} · {point.type}
                        </span>
                      ))}
                    </div>
                  </section>

                  <section className="case-section">
                    <div className="case-section-head">
                      <strong>数据来源</strong>
                      <span>接口返回</span>
                    </div>
                    <div className="case-source-list">
                      {(caseProfile?.data_sources || ['USGS station metadata', 'Oroville Dam public coordinates', 'local DEM raster cache']).map(
                        (source) => (
                          <span key={source}>{source}</span>
                        )
                      )}
                    </div>
                  </section>
                </div>
              )}
            </div>
          </section>
        </aside>
      </main>

      <section className="case-workspace-panel" aria-label="Oroville Dam 妗堜緥鏁版嵁宸ヤ綔鍙?">
        <div className="case-workspace-head">
          <div>
            <span>CASE DATA WORKSPACE</span>
            <h3>{caseProfile?.dam.name || simulationStatus?.dam_name || 'Oroville Dam / Lake Oroville'}</h3>
            <p>
              {caseProfile?.dam.river || 'Feather River'} · {formatCaseCoordinate(caseProfile?.dam.lat)}, {formatCaseCoordinate(caseProfile?.dam.lng)}
            </p>
          </div>
          <button type="button" className="historical-replay-button case-workspace-action" onClick={handleHistoricalReplay} disabled={startingHistoricalReplay}>
            {startingHistoricalReplay ? '正在启动 2017 回放...' : '运行 2017 历史回放'}
          </button>
        </div>

        <div className="case-workspace-grid">
          <div className="case-workspace-card case-workspace-status">
            <span>数据可信等级</span>
            <strong className={`trust-${dataStatusCopy.tone}`}>{dataStatusCopy.label}</strong>
            <p>{dataStatusCopy.detail}</p>
          </div>
          <div className="case-workspace-card">
            <span>DEM / 模型网格</span>
            <strong>{demCacheEnabled ? 'DEM 缓存已启用' : 'DEM 缓存未启用'}</strong>
            <p>{caseProfile ? `${caseProfile.grid.rows} x ${caseProfile.grid.cols} · ${demCacheMode}` : demCacheMode}</p>
          </div>
          <div className="case-workspace-card">
            <span>USGS 时序链路</span>
            <strong>{dataStatus}</strong>
            <p>{usgsLiveSeriesCount.toLocaleString('zh-CN')} 条观测样本 · {realDataStatus ? dayjs(realDataStatus.checked_at).format('HH:mm:ss') : '检查中'}</p>
          </div>
          <div className="case-workspace-card">
            <span>案例对象</span>
            <strong>{caseStations.length} 站点 · {caseKeyPoints.length} 对象</strong>
            <p>坝体、库区、Feather River 河道、监测站与关键影响对象分离展示。</p>
          </div>
        </div>

        <div className="case-workspace-detail">
          <section>
            <div className="case-section-head">
              <strong>真实监测点</strong>
              <span>{caseStations.length} 个</span>
            </div>
            <div className="case-workspace-list">
              {caseStations.map(([stationId, station]) => (
                <button key={stationId} type="button" onClick={() => setSelectedStationId(stationId)}>
                  <span>{station.name}</span>
                  <em>{station.type} · {formatCaseCoordinate(station.lat)}, {formatCaseCoordinate(station.lng)}</em>
                </button>
              ))}
            </div>
          </section>

          <section>
            <div className="case-section-head">
              <strong>2017 回放证据链</strong>
              <span>{historicalEvent?.milestone_count || 0} 节点</span>
            </div>
            <div className="case-workspace-timeline">
              {(historicalEvent?.known_milestones || []).map((milestone) => (
                <div key={`${milestone.time}-${milestone.label}`}>
                  <span>{milestone.time}</span>
                  <strong>{milestone.label}</strong>
                </div>
              ))}
            </div>
          </section>

          <section>
            <div className="case-section-head">
              <strong>校准目标</strong>
              <span>{historicalEvent?.calibration_target_count || 0} 项</span>
            </div>
            <div className="case-workspace-chips">
              {(historicalEvent?.calibration_targets || []).map((target) => (
                <span key={target}>{target}</span>
              ))}
            </div>
          </section>
        </div>
      </section>
      {error && <div className="screen-error-toast">{error}</div>}
    </div>
  )
}

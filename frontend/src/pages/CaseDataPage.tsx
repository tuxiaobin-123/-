import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Spin } from 'antd'
import dayjs from 'dayjs'
import { getActiveCase, getModelCapabilities, getRealDataStatus, startHistoricalReplay } from '../api/client'
import { CaseProfile, ModelCapabilities, RealDataStatus } from '../types'
import './CaseDataPage.css'

const DATA_STATUS_COPY = {
  live: { label: 'LIVE 实时', tone: 'good', detail: '已连通 USGS 实时接口，可用于当前观测链路。' },
  cached: { label: 'CACHE 缓存', tone: 'warn', detail: '实时源暂不可达，正在使用最近一次成功抓取的数据。' },
  offline_seed: { label: 'SEED 离线种子', tone: 'muted', detail: '当前网络拦截 USGS，先用透明离线种子跑通流程，不冒充实时。' },
  unavailable: { label: 'DOWN 不可达', tone: 'danger', detail: '实时源和缓存都不可用，需要先恢复外部网络链路。' }
} as const

const formatCoordinate = (value?: number) => (typeof value === 'number' ? value.toFixed(5) : '-')
const formatNumber = (value?: number, fractionDigits = 0) =>
  typeof value === 'number' ? value.toLocaleString('zh-CN', { maximumFractionDigits: fractionDigits }) : '-'

export const CaseDataPage: React.FC = () => {
  const [caseProfile, setCaseProfile] = useState<CaseProfile | null>(null)
  const [modelCapabilities, setModelCapabilities] = useState<ModelCapabilities | null>(null)
  const [realDataStatus, setRealDataStatus] = useState<RealDataStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [startingReplay, setStartingReplay] = useState(false)
  const [replayMessage, setReplayMessage] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [caseData, capabilityData, statusData] = await Promise.all([getActiveCase(), getModelCapabilities(), getRealDataStatus()])
      setCaseProfile(caseData)
      setModelCapabilities(capabilityData)
      setRealDataStatus(statusData)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : '案例数据加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadData()
  }, [loadData])

  const caseStations = useMemo(() => Object.entries(caseProfile?.sensor_stations || {}), [caseProfile?.sensor_stations])
  const caseKeyPoints = useMemo(() => Object.entries(caseProfile?.key_points || {}), [caseProfile?.key_points])
  const historicalEvent = realDataStatus?.historical_event
  const dataStatus = realDataStatus?.usgs.status || 'unavailable'
  const dataStatusCopy = DATA_STATUS_COPY[dataStatus]
  const usgsSampleCount = realDataStatus?.usgs.series.reduce((total, series) => total + series.count, 0) || 0
  const innovationCards = useMemo(() => {
    const points = modelCapabilities?.innovation_points
    return [
      {
        key: 'physics-ai',
        title: '物理模型 + AI 预测',
        value: modelCapabilities ? 'SWE 水动力 + 预测链路' : 'Physics + AI',
        detail: points?.physics_ai_fusion.evidence.length
          ? '水动力模型输出水深、流速和水面线，预测接口继续给出未来风险趋势。'
          : 'SWE 水动力结果与预测 API 联动。'
      },
      {
        key: 'dam-boundary',
        title: '大坝对象边界条件',
        value: modelCapabilities ? '坝前-泄洪-下游水位' : 'Dam Boundary',
        detail: points?.dam_boundary_conditions.evidence.length
          ? '上游来水、库水位、闸门泄洪和下游控制水位都进入同一套推演参数。'
          : '坝前水位、泄洪、下游控制水位进入模型。'
      },
      {
        key: 'decision-loop',
        title: '预警处置闭环',
        value: modelCapabilities ? `${modelCapabilities.decision_loop.length} 环节闭环` : 'Decision Loop',
        detail: points?.monitor_simulate_warn_respond_loop.evidence.length
          ? '监测、推演、风险识别、避险路线和报告输出组成完整处置链。'
          : '风险对象、避险路线和报告输出联动。'
      }
    ]
  }, [modelCapabilities])

  const handleStartReplay = async () => {
    setStartingReplay(true)
    try {
      const result = await startHistoricalReplay()
      setReplayMessage(`2017 回放已启动：${result.total_steps} 步，入流 ${result.upstream_inflow_m3s.toFixed(0)} m³/s`)
    } catch (err) {
      setReplayMessage(err instanceof Error ? err.message : '历史回放启动失败')
    } finally {
      setStartingReplay(false)
    }
  }

  if (loading) {
    return (
      <div className="case-page-loading">
        <Spin size="large" />
        <span>正在加载桑干河怀仁段案例数据...</span>
      </div>
    )
  }

  return (
    <div className="case-page">
      <header className="case-page-header">
        <button type="button" className="case-back-button" onClick={() => { window.location.href = '/' }}>
          返回主大屏
        </button>
        <div>
          <span>SANGGAN RIVER CASE CENTER</span>
          <h1>{caseProfile?.dam.name || '桑干河怀仁段水利枢纽'}</h1>
          <p>
            {caseProfile?.dam.river || '桑干河'} · {formatCoordinate(caseProfile?.dam.lat)}, {formatCoordinate(caseProfile?.dam.lng)}
          </p>
        </div>
        <button type="button" className="case-primary-action" onClick={handleStartReplay} disabled={startingReplay}>
          {startingReplay ? '正在启动回放...' : '运行 1996 桑干河历史回放'}
        </button>
      </header>

      {error && <div className="case-page-error">{error}</div>}
      {replayMessage && <div className="case-page-message">{replayMessage}</div>}

      <main className="case-page-grid">
        <section className={`case-hero-card case-trust-${dataStatusCopy.tone}`}>
          <span>数据可信等级</span>
          <strong>{dataStatusCopy.label}</strong>
          <p>{dataStatusCopy.detail}</p>
          <em>{realDataStatus ? `检查时间 ${dayjs(realDataStatus.checked_at).format('YYYY-MM-DD HH:mm:ss')}` : '等待检查'}</em>
        </section>

        <section className="case-kpi-card">
          <span>USGS 时序样本</span>
          <strong>{usgsSampleCount.toLocaleString('zh-CN')}</strong>
          <p>{realDataStatus?.usgs.series.length || 0} 组站点/参数序列</p>
        </section>

        <section className="case-kpi-card">
          <span>DEM / 网格</span>
          <strong>{caseProfile ? `${caseProfile.grid.rows} x ${caseProfile.grid.cols}` : '-'}</strong>
          <p>{realDataStatus?.dem.mode || 'local DEM grid cache'}</p>
        </section>

        <section className="case-kpi-card">
          <span>案例对象</span>
          <strong>{caseStations.length} 站 · {caseKeyPoints.length} 对象</strong>
          <p>坝体、库区、河道、监测点、关键影响对象</p>
        </section>
      </main>

      <section className="case-innovation-strip" aria-label="核心创新证据链">
        {innovationCards.map((card) => (
          <article key={card.key} className="case-innovation-card">
            <span>{card.title}</span>
            <strong>{card.value}</strong>
            <p>{card.detail}</p>
          </article>
        ))}
      </section>

      <section className="case-page-sections">
        <article className="case-page-panel">
          <div className="case-panel-head">
            <div>
              <span>REAL OBSERVATIONS</span>
              <h2>实时/缓存时序链路</h2>
            </div>
            <button type="button" onClick={loadData}>重新探测</button>
          </div>
          <div className="case-series-table">
            {(realDataStatus?.usgs.series || []).map((series) => (
              <div key={`${series.station_id}-${series.parameter_code}`} className="case-series-row">
                <strong>{series.station_name}</strong>
                <span>{series.parameter_name}</span>
                <span>{series.latest_value ?? '-'}</span>
                <em>{series.count} samples · {series.latest_time ? dayjs(series.latest_time).format('MM-DD HH:mm') : 'no latest'}</em>
              </div>
            ))}
          </div>
          {realDataStatus?.usgs.last_error && <p className="case-source-warning">实时源暂不可达：{realDataStatus.usgs.last_error}</p>}
        </article>

        <article className="case-page-panel">
          <div className="case-panel-head">
            <div>
              <span>STATIONS</span>
              <h2>真实监测点</h2>
            </div>
            <span>{caseStations.length} 个</span>
          </div>
          <div className="case-station-grid">
            {caseStations.map(([stationId, station]) => (
              <div key={stationId} className="case-station-card">
                <strong>{station.name}</strong>
                <span>{station.type} · {station.source || stationId}</span>
                <em>{formatCoordinate(station.lat)}, {formatCoordinate(station.lng)}</em>
              </div>
            ))}
          </div>
        </article>

        <article className="case-page-panel wide">
          <div className="case-panel-head">
            <div>
              <span>2017 REPLAY</span>
              <h2>历史回放证据链与校准目标</h2>
            </div>
            <span>{historicalEvent?.period.start.slice(0, 10)} 至 {historicalEvent?.period.end.slice(0, 10)}</span>
          </div>
          <div className="case-replay-layout">
            <div className="case-timeline">
              {(historicalEvent?.known_milestones || []).map((milestone) => (
                <div key={`${milestone.time}-${milestone.label}`}>
                  <span>{milestone.time}</span>
                  <strong>{milestone.label}</strong>
                </div>
              ))}
            </div>
            <div className="case-targets">
              {(historicalEvent?.calibration_targets || []).map((target) => (
                <span key={target}>{target}</span>
              ))}
            </div>
            <div className="case-seed-card">
              <span>回放启动参数</span>
              <strong>{formatNumber(historicalEvent?.starter_simulation.upstream_m3s)} m³/s 入流</strong>
              <p>
                降雨 {formatNumber(historicalEvent?.starter_simulation.rainfall_mm_h, 1)} mm/h ·
                泄量 {formatNumber(historicalEvent?.starter_simulation.gate_release_m3s)} m³/s ·
                时长 {formatNumber(historicalEvent?.starter_simulation.duration_hours)} h
              </p>
            </div>
          </div>
        </article>

        <article className="case-page-panel wide">
          <div className="case-panel-head">
            <div>
              <span>KEY OBJECTS</span>
              <h2>关键影响对象与数据来源</h2>
            </div>
          </div>
          <div className="case-object-grid">
            {caseKeyPoints.map(([pointId, point]) => (
              <div key={pointId}>
                <strong>{point.name}</strong>
                <span>{point.type}</span>
                <em>{formatCoordinate(point.lat)}, {formatCoordinate(point.lng)}</em>
              </div>
            ))}
          </div>
          <div className="case-source-list-full">
            {(caseProfile?.data_sources || []).map((source) => (
              <span key={source}>{source}</span>
            ))}
          </div>
        </article>
      </section>
    </div>
  )
}

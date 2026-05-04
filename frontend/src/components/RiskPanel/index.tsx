import React, { useMemo } from 'react'
import { AlertOutlined, CheckCircleOutlined, RadarChartOutlined } from '@ant-design/icons'
import { AffectedKeyPoint, RiskStats, WSMessage } from '../../types'
import './RiskPanel.css'

interface RiskPanelProps {
  riskStats: RiskStats | null
  wsMessage: WSMessage | null
  selectedKeyPointId?: string | null
  onKeyPointSelect?: (point: AffectedKeyPoint) => void
}

type RiskLevel = 'low' | 'medium' | 'high' | 'extreme'

const RISK_META: Record<RiskLevel, { color: string; label: string; score: number }> = {
  low: { color: '#45f5b0', label: '低风险', score: 25 },
  medium: { color: '#ffd56f', label: '中风险', score: 52 },
  high: { color: '#ff9858', label: '高风险', score: 76 },
  extreme: { color: '#ff6673', label: '极高风险', score: 92 }
}

export const RiskPanel: React.FC<RiskPanelProps> = ({ riskStats, wsMessage, selectedKeyPointId, onKeyPointSelect }) => {
  const overallLevel = (riskStats?.overall_level || 'low') as RiskLevel
  const riskInfo = RISK_META[overallLevel]

  const zoneRisks = useMemo(() => {
    if (!riskStats?.risk_breakdown) {
      return []
    }

    return Object.entries(riskStats.risk_breakdown)
      .map(([zone, data]) => {
        const percentage = Math.round((data.population / Math.max(riskStats.affected_population || 1, 1)) * 100)
        return { name: zone, percentage, level: data.level, area: data.area_km2, population: data.population }
      })
      .sort((left, right) => right.percentage - left.percentage)
  }, [riskStats])

  const alertMessages = useMemo(() => {
    const messages: Array<{ time: string; message: string; level: RiskLevel }> = []

    if (riskStats?.warning_message) {
      messages.push({
        time: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
        message: riskStats.warning_message,
        level: overallLevel
      })
    }

    riskStats?.affected_key_points?.slice(0, 3).forEach((point, index) => {
      messages.push({
        time: new Date(Date.now() - index * 90_000).toLocaleTimeString('zh-CN', { hour12: false }),
        message: `${point.name} 当前积水 ${point.water_depth.toFixed(2)} m，风险等级 ${RISK_META[point.risk_level].label}。`,
        level: point.risk_level
      })
    })

    if (wsMessage?.type === 'alert' && wsMessage.data?.alert_message) {
      messages.push({
        time: new Date(wsMessage.timestamp).toLocaleTimeString('zh-CN', { hour12: false }),
        message: wsMessage.data.alert_message,
        level: (wsMessage.data.risk_level as RiskLevel) || overallLevel
      })
    }

    if (messages.length === 0) {
      messages.push({
        time: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
        message: '当前未触发新的风险告警，系统持续监测坝区与下游断面。',
        level: 'low'
      })
    }

    return messages.slice(0, 5)
  }, [overallLevel, riskStats, wsMessage])

  return (
    <div className="risk-panel">
      <div className="risk-section risk-level-section">
        <div className="section-header">整体风险评估</div>

        <div className="risk-radar-card">
          <div className={`risk-radar risk-${overallLevel}`} style={{ ['--risk-color' as string]: riskInfo.color }}>
            <div className="risk-radar-core">
              <span>综合指数</span>
              <strong>{Math.round(riskStats?.risk_score ?? riskInfo.score)}</strong>
            </div>
          </div>

          <div className="risk-radar-copy">
            <div
              className={`risk-badge risk-${overallLevel}`}
              style={{
                borderColor: riskInfo.color,
                boxShadow: `0 0 18px ${riskInfo.color}33`
              }}
            >
              <div className="badge-label">{riskInfo.label}</div>
              <div className="badge-emoji">{riskStats?.warning_level?.toUpperCase() || 'LIVE'}</div>
            </div>

            <div className="risk-summary-line">
              <RadarChartOutlined /> 重点高风险区 {riskStats?.high_risk_zones || 0} 处
            </div>
          </div>
        </div>

        {riskStats?.evacuation_recommended ? (
          <div className="evacuation-warning">
            <AlertOutlined /> 建议立即组织重点区域人员转移
          </div>
        ) : (
          <div className="evacuation-safe">
            <CheckCircleOutlined /> 当前尚未达到大范围疏散阈值
          </div>
        )}
      </div>

      <div className="risk-section zones-section">
        <div className="section-header">分区风险分布</div>
        <div className="zones-list">
          {zoneRisks.map((zone) => {
            const zoneInfo = RISK_META[zone.level]
            return (
              <div key={zone.name} className="zone-item">
                <div className="zone-row">
                  <div className="zone-name">{zone.name}</div>
                  <div className="zone-tag" style={{ color: zoneInfo.color }}>
                    {zoneInfo.label}
                  </div>
                </div>
                <div className="zone-progress">
                  <div className="progress-bar">
                    <div
                      className="progress-fill"
                      style={{
                        width: `${zone.percentage}%`,
                        backgroundColor: zoneInfo.color,
                        boxShadow: `0 0 10px ${zoneInfo.color}55`
                      }}
                    />
                  </div>
                  <div className="progress-percent">{zone.percentage}%</div>
                </div>
                <div className="zone-row">
                  <div className="zone-name">{zone.area.toFixed(2)} km²</div>
                  <div className="zone-tag">{zone.population.toLocaleString('zh-CN')} 人</div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="risk-section stats-section">
        <div className="section-header">影响统计</div>
        <div className="stats-grid">
          <div className="stat-item">
            <div className="stat-label">影响面积</div>
            <div className="stat-value">{(riskStats?.affected_area_km2 || 0).toFixed(1)}</div>
            <div className="stat-unit">km²</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">影响人口</div>
            <div className="stat-value">{((riskStats?.affected_population || 0) / 1000).toFixed(0)}</div>
            <div className="stat-unit">千人</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">受影响点位</div>
            <div className="stat-value">{riskStats?.affected_key_points?.length || 0}</div>
            <div className="stat-unit">处</div>
          </div>
        </div>
      </div>

      <div className="risk-section">
        <div className="section-header">关键对象影响链</div>
        <div className="alerts-list">
          {(riskStats?.affected_key_points || []).slice(0, 5).map((point) => (
            <div
              key={point.id}
              className={`alert-item alert-${point.risk_level} ${selectedKeyPointId === point.id ? 'is-selected' : ''}`}
              onClick={() => onKeyPointSelect?.(point)}
              style={{ cursor: 'pointer' }}
            >
              <div className="alert-time">{point.type}</div>
              <div className="alert-message">
                {point.name} · {RISK_META[point.risk_level].label} · 积水 {point.water_depth.toFixed(2)} m
              </div>
            </div>
          ))}
          {(!riskStats?.affected_key_points || riskStats.affected_key_points.length === 0) && (
            <div className="alert-item alert-low">
              <div className="alert-time">无对象</div>
              <div className="alert-message">当前暂无关键对象进入受影响链。</div>
            </div>
          )}
        </div>
      </div>

      <div className="risk-section alerts-section">
        <div className="section-header">最新告警</div>
        <div className="alerts-list">
          {alertMessages.map((alert, index) => (
            <div key={`${alert.time}-${index}`} className={`alert-item alert-${alert.level}`}>
              <div className="alert-time">{alert.time}</div>
              <div className="alert-message">{alert.message}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

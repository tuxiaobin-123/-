import React, { useMemo } from 'react'
import {
  AlertOutlined,
  ArrowDownOutlined,
  ArrowUpOutlined,
  CloudOutlined,
  EnvironmentOutlined,
  TeamOutlined
} from '@ant-design/icons'
import { PredictionData, RiskStats, SensorStation, SimulationStatus, WSMessage } from '../../types'
import './Dashboard.css'

interface DashboardProps {
  sensors: SensorStation[]
  riskStats: RiskStats | null
  prediction: PredictionData | null
  simulationStatus: SimulationStatus | null
  wsMessage: WSMessage | null
}

interface MetricCard {
  label: string
  value: string | number
  unit: string
  trend?: 'up' | 'down' | null
  riskColor?: string
  icon: React.ReactNode
}

const getRiskColor = (level: string) => {
  switch (level) {
    case 'extreme':
      return '#ff6673'
    case 'high':
      return '#ff9858'
    case 'medium':
      return '#ffd56f'
    case 'low':
      return '#45f5b0'
    default:
      return '#99a8b8'
  }
}

const getRiskLabel = (level: string) => {
  const labels: Record<string, string> = {
    extreme: '极高风险',
    high: '高风险',
    medium: '中风险',
    low: '低风险'
  }

  return labels[level] || level
}

export const Dashboard: React.FC<DashboardProps> = ({ sensors, riskStats, prediction, simulationStatus, wsMessage }) => {
  const waterLevelMetrics = useMemo(() => {
    if (sensors.length === 0) {
      return { avg: 0, trend: null as 'up' | 'down' | null }
    }

    const avg = sensors.reduce((sum, station) => sum + station.water_level, 0) / sensors.length
    let trend: 'up' | 'down' | null = null

    if (wsMessage?.data?.water_level !== undefined) {
      trend = wsMessage.data.water_level > avg ? 'up' : 'down'
    }

    return { avg, trend }
  }, [sensors, wsMessage])

  const avgRainfall = useMemo(() => {
    if (sensors.length === 0) {
      return 0
    }
    return sensors.reduce((sum, station) => sum + station.rainfall, 0) / sensors.length
  }, [sensors])

  const peakTimeMetrics = useMemo(() => {
    if (!prediction || prediction.timestamps.length === 0) {
      return { hoursFromNow: 0 }
    }

    const maxIndex = prediction.predicted_levels.indexOf(Math.max(...prediction.predicted_levels))
    const peakTime = new Date(prediction.timestamps[maxIndex])
    const now = new Date()
    const hoursFromNow = Math.round((peakTime.getTime() - now.getTime()) / (1000 * 60 * 60))

    return { hoursFromNow }
  }, [prediction])

  const highestStation = useMemo(() => {
    return [...sensors].sort((left, right) => right.water_level - left.water_level)[0] || null
  }, [sensors])

  const metrics: MetricCard[] = [
    {
      label: '当前平均水位',
      value: waterLevelMetrics.avg.toFixed(2),
      unit: 'm',
      trend: waterLevelMetrics.trend,
      icon: <EnvironmentOutlined />
    },
    {
      label: '实时平均雨量',
      value: avgRainfall.toFixed(1),
      unit: 'mm/h',
      icon: <CloudOutlined />
    },
    {
      label: '洪峰预计到达',
      value: peakTimeMetrics.hoursFromNow > 0 ? peakTimeMetrics.hoursFromNow : '已过',
      unit: peakTimeMetrics.hoursFromNow > 0 ? '小时后' : '',
      icon: <AlertOutlined />
    },
    {
      label: '整体风险等级',
      value: getRiskLabel(riskStats?.overall_level || 'low'),
      unit: '',
      riskColor: getRiskColor(riskStats?.overall_level || 'low'),
      icon: <AlertOutlined />
    },
    {
      label: '当前泄洪流量',
      value: (simulationStatus?.gate_release || 0).toFixed(0),
      unit: 'm³/s',
      icon: <ArrowDownOutlined />
    },
    {
      label: '影响人口',
      value: (riskStats?.affected_population || 0).toLocaleString('zh-CN'),
      unit: '人',
      icon: <TeamOutlined />
    }
  ]

  return (
    <div className="dashboard-container">
      <div className="dashboard-metrics-row">
        {metrics.map((metric, index) => (
          <div key={index} className="dashboard-metric-card">
            <div className="dashboard-metric-icon">{metric.icon}</div>
            <div className="dashboard-metric-content">
              <div className="dashboard-metric-label">{metric.label}</div>
              <div className="dashboard-metric-value" style={metric.riskColor ? { color: metric.riskColor } : {}}>
                {metric.value}
                {metric.trend && (
                  <span className={`dashboard-trend-indicator ${metric.trend}`}>
                    {metric.trend === 'up' ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
                  </span>
                )}
              </div>
              <div className="dashboard-metric-unit">{metric.unit}</div>
            </div>
          </div>
        ))}
      </div>

      {highestStation && (
        <div className="dashboard-metrics-row">
          <div className="dashboard-metric-card">
            <div className="dashboard-metric-icon">
              <EnvironmentOutlined />
            </div>
            <div className="dashboard-metric-content">
              <div className="dashboard-metric-label">当前最高关注站点</div>
              <div className="dashboard-metric-value">{highestStation.name}</div>
              <div className="dashboard-metric-unit">
                {highestStation.water_level.toFixed(2)} m / {highestStation.flow_rate.toFixed(2)} m/s
              </div>
            </div>
          </div>

          <div className="dashboard-metric-card">
            <div className="dashboard-metric-icon">
              <AlertOutlined />
            </div>
            <div className="dashboard-metric-content">
              <div className="dashboard-metric-label">最新风控结论</div>
              <div
                className="dashboard-metric-value"
                style={{ color: getRiskColor(riskStats?.overall_level || 'low') }}
              >
                {riskStats?.warning_level?.toUpperCase() || 'MONITOR'}
              </div>
              <div className="dashboard-metric-unit">{riskStats?.warning_message || '持续监测坝区状态'}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

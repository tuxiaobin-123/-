import React from 'react'
import { ThunderboltOutlined, WifiOutlined } from '@ant-design/icons'
import { SensorStation } from '../../types'
import './SensorPanel.css'

interface SensorPanelProps {
  stations: SensorStation[]
  selectedStationId?: string | null
  onStationSelect?: (station: SensorStation) => void
}

export const SensorPanel: React.FC<SensorPanelProps> = ({ stations, selectedStationId, onStationSelect }) => {
  const getStatusColor = (status: SensorStation['status']) => {
    const colors: Record<SensorStation['status'], string> = {
      normal: '#45f5b0',
      warning: '#ffd56f',
      danger: '#ff6673'
    }
    return colors[status]
  }

  const getStatusLabel = (status: SensorStation['status']) => {
    const labels: Record<SensorStation['status'], string> = {
      normal: '正常',
      warning: '预警',
      danger: '危险'
    }
    return labels[status]
  }

  return (
    <div className="sensor-panel">
      <div className="sensor-header">
        <h3 className="sensor-header-title">水位站监测</h3>
        <div className="station-count">{stations.length} 个站点</div>
      </div>

      <div className="stations-list">
        {stations.length === 0 ? (
          <div className="no-stations">
            <div className="no-stations-icon">●</div>
            <div className="no-stations-text">暂无监测站点数据</div>
          </div>
        ) : (
          stations.map((station) => (
            <div
              key={station.station_id}
              className={`station-card station-${station.status} ${selectedStationId === station.station_id ? 'is-selected' : ''}`}
              onClick={() => onStationSelect?.(station)}
            >
              <div
                className="status-indicator"
                style={{
                  backgroundColor: getStatusColor(station.status),
                  boxShadow: `0 0 12px ${getStatusColor(station.status)}`
                }}
              />

              <div className="station-info">
                <div className="info-header">
                  <div className="station-name">{station.name}</div>
                  <div className="station-status" style={{ color: getStatusColor(station.status) }}>
                    {getStatusLabel(station.status)}
                  </div>
                </div>

                <div className="water-level-display">
                  <span className="level-icon">水位</span>
                  <span className="level-value">{station.water_level.toFixed(2)}</span>
                  <span className="level-unit">m</span>
                </div>

                <div className="metrics-row">
                  <div className="metric">
                    <span className="metric-icon">雨</span>
                    <span className="metric-label">降雨</span>
                    <span className="metric-value">{station.rainfall.toFixed(1)}</span>
                    <span className="metric-unit">mm/h</span>
                  </div>

                  <div className="metric">
                    <span className="metric-icon">流</span>
                    <span className="metric-label">流量</span>
                    <span className="metric-value">{station.flow_rate.toFixed(1)}</span>
                    <span className="metric-unit">m³/s</span>
                  </div>
                </div>

                <div className="sensor-status-row">
                  <div className="sensor-item battery">
                    <ThunderboltOutlined className="sensor-icon" />
                    <div className="sensor-detail">
                      <span className="label">电量</span>
                      <div className="progress-bar">
                        <div
                          className="progress-fill"
                          style={{
                            width: `${station.battery}%`,
                            backgroundColor: station.battery > 50 ? '#45f5b0' : station.battery > 20 ? '#ffd56f' : '#ff6673'
                          }}
                        />
                      </div>
                      <span className="percent">{station.battery}%</span>
                    </div>
                  </div>

                  <div className="sensor-item signal">
                    <WifiOutlined className="sensor-icon" />
                    <div className="sensor-detail">
                      <span className="label">信号</span>
                      <div className="progress-bar">
                        <div
                          className="progress-fill"
                          style={{
                            width: `${station.signal_quality}%`,
                            backgroundColor:
                              station.signal_quality > 70 ? '#45f5b0' : station.signal_quality > 40 ? '#ffd56f' : '#ff6673'
                          }}
                        />
                      </div>
                      <span className="percent">{station.signal_quality}%</span>
                    </div>
                  </div>
                </div>

                <div className="update-time">
                  最后更新 {new Date(station.last_update).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>

              <div className="card-indicator" />
            </div>
          ))
        )}
      </div>

      <div className="sensor-footer">
        <div className="footer-dot" />
        <span className="footer-text">点击站点后，地图、预测图和路线会同步切换到当前对象</span>
      </div>
    </div>
  )
}

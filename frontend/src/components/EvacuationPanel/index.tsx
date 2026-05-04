import React from 'react'
import { ArrowRightOutlined, ClockCircleOutlined, EnvironmentOutlined } from '@ant-design/icons'
import { EvacuationRoute } from '../../types'
import './EvacuationPanel.css'

interface EvacuationPanelProps {
  routes: EvacuationRoute[]
  selectedRouteId?: string | null
  onRouteSelect?: (route: EvacuationRoute) => void
}

export const EvacuationPanel: React.FC<EvacuationPanelProps> = ({ routes, selectedRouteId, onRouteSelect }) => {
  const getStatusInfo = (status: EvacuationRoute['status']) => {
    const statusMap: Record<EvacuationRoute['status'], { color: string; label: string; emoji: string }> = {
      safe: { color: '#45f5b0', label: '安全', emoji: 'OK' },
      caution: { color: '#ffd56f', label: '谨慎', emoji: '!' },
      dangerous: { color: '#ff6673', label: '危险', emoji: 'X' }
    }
    return statusMap[status]
  }

  const displayRoutes = routes.slice(0, 3)
  const featuredRoute = displayRoutes[0]
  const backupRoutes = displayRoutes.slice(1)

  return (
    <div className="evacuation-panel">
      <div className="evacuation-header">
        <h3 className="header-title">动态避险路线</h3>
        <div className="header-subtitle">按风险评分、距离和耗时综合排序</div>
      </div>

      <div className="routes-container route-compact-container">
        {!featuredRoute ? (
          <div className="no-routes">
            <div className="no-routes-icon">→</div>
            <div className="no-routes-text">暂无可用避险路线</div>
          </div>
        ) : (
          <>
            <div
              className={`route-card route-featured route-${featuredRoute.status} ${selectedRouteId === featuredRoute.id ? 'is-selected' : ''}`}
              onClick={() => onRouteSelect?.(featuredRoute)}
            >
              <div className="route-header">
                <div>
                  <div className="route-number">推荐路线</div>
                  <div className="route-main-name">
                    <span>{featuredRoute.origin.name}</span>
                    <ArrowRightOutlined />
                    <span>{featuredRoute.destination.name}</span>
                  </div>
                </div>
                <div
                  className="status-badge"
                  style={{
                    borderColor: getStatusInfo(featuredRoute.status).color,
                    color: getStatusInfo(featuredRoute.status).color,
                    boxShadow: `0 0 10px ${getStatusInfo(featuredRoute.status).color}22`
                  }}
                >
                  <span className="badge-emoji">{getStatusInfo(featuredRoute.status).emoji}</span>
                  <span className="badge-label">{getStatusInfo(featuredRoute.status).label}</span>
                </div>
              </div>

              <div className="route-metric-row">
                <div className="route-mini-metric">
                  <EnvironmentOutlined />
                  <span>{featuredRoute.distance.toFixed(1)} km</span>
                </div>
                <div className="route-mini-metric">
                  <ClockCircleOutlined />
                  <span>{featuredRoute.estimated_minutes} 分钟</span>
                </div>
                <div className="route-mini-metric route-risk-score">
                  <span>风险 {featuredRoute.risk_score.toFixed(1)}</span>
                </div>
              </div>

              <div className="score-bar">
                <div
                  className="score-fill"
                  style={{
                    width: `${featuredRoute.risk_score}%`,
                    backgroundColor: featuredRoute.risk_score > 70 ? '#ff6673' : featuredRoute.risk_score > 40 ? '#ffd56f' : '#45f5b0'
                  }}
                />
              </div>
            </div>

            {backupRoutes.length > 0 && (
              <div className="route-backup-list">
                {backupRoutes.map((route, index) => {
                  const statusInfo = getStatusInfo(route.status)
                  return (
                    <button
                      key={route.id}
                      type="button"
                      className={`route-backup-item route-${route.status} ${selectedRouteId === route.id ? 'is-selected' : ''}`}
                      onClick={() => onRouteSelect?.(route)}
                    >
                      <span className="route-backup-rank">备选 {index + 1}</span>
                      <strong>{route.origin.name}</strong>
                      <ArrowRightOutlined />
                      <strong>{route.destination.name}</strong>
                      <em style={{ color: statusInfo.color }}>{route.risk_score.toFixed(1)}</em>
                    </button>
                  )
                })}
              </div>
            )}
          </>
        )}
      </div>

      <div className="evacuation-footer compact-footer">
        <div className="footer-icon">!</div>
        <div className="footer-text">优先选择低风险路线；点击路线后，地图会高亮对应方案。</div>
      </div>
    </div>
  )
}

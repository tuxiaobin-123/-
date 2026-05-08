import React, { useEffect, useRef } from 'react'
import L from 'leaflet'
import { AffectedKeyPoint, EvacuationRoute, FloodGridPoint, RiskZoneCollection, SensorStation } from '../../types'
import './FloodMap.css'

interface FloodMapProps {
  floodGrid: FloodGridPoint[]
  sensors: SensorStation[]
  evacuationRoutes: EvacuationRoute[]
  riskZones?: RiskZoneCollection | null
  keyPoints?: AffectedKeyPoint[]
  showVelocity?: boolean
  showRoutes?: boolean
  selectedStationId?: string | null
  selectedRouteId?: string | null
  selectedKeyPointId?: string | null
  onStationSelect?: (station: SensorStation) => void
  onKeyPointSelect?: (point: AffectedKeyPoint) => void
}

const GRID_SIZE = 0.0065
const DEFAULT_VIEW: [number, number] = [39.515, -121.545]
const DEFAULT_ZOOM = 11.9

const REGION_BOUNDARY: [number, number][] = [
  [39.595, -121.675],
  [39.592, -121.425],
  [39.555, -121.395],
  [39.520, -121.455],
  [39.490, -121.500],
  [39.430, -121.610],
  [39.445, -121.665],
  [39.520, -121.675]
]

const RESERVOIR_POLYGON: [number, number][] = [
  [39.592, -121.448],
  [39.575, -121.405],
  [39.535, -121.392],
  [39.505, -121.428],
  [39.514, -121.478],
  [39.537, -121.494],
  [39.565, -121.485]
]

const DAM_AXIS: [number, number][] = [
  [39.5374, -121.4975],
  [39.5367, -121.4745]
]

const DOWNSTREAM_SECTION: [number, number][] = [
  [39.522, -121.560],
  [39.500, -121.548]
]

const CONTOUR_BANDS: Array<{ points: [number, number][]; fill: string; opacity: number; className: string }> = [
  {
    points: [
      [39.445, -121.665],
      [39.455, -121.650],
      [39.470, -121.600],
      [39.500, -121.555],
      [39.530, -121.510],
      [39.565, -121.505],
      [39.575, -121.555],
      [39.540, -121.625],
      [39.490, -121.665]
    ],
    fill: 'rgba(126, 245, 194, 0.12)',
    opacity: 0.72,
    className: 'terrain-band terrain-band-1'
  },
  {
    points: [
      [39.505, -121.635],
      [39.518, -121.585],
      [39.535, -121.535],
      [39.548, -121.490],
      [39.570, -121.470],
      [39.570, -121.535],
      [39.545, -121.602],
      [39.520, -121.648]
    ],
    fill: 'rgba(98, 222, 255, 0.1)',
    opacity: 0.8,
    className: 'terrain-band terrain-band-2'
  },
  {
    points: [
      [39.525, -121.500],
      [39.545, -121.455],
      [39.575, -121.430],
      [39.575, -121.395],
      [39.535, -121.410],
      [39.505, -121.455]
    ],
    fill: 'rgba(255, 208, 97, 0.08)',
    opacity: 0.84,
    className: 'terrain-band terrain-band-3'
  }
]

const MAIN_RIVER: [number, number][] = [
  [39.590, -121.430],
  [39.565, -121.465],
  [39.537, -121.486],
  [39.522, -121.548],
  [39.500, -121.575],
  [39.470, -121.615],
  [39.445, -121.638]
]

const BRANCH_RIVERS: [number, number][][] = [
  [
    [39.565, -121.430],
    [39.540, -121.455],
    [39.515, -121.478],
    [39.498, -121.505]
  ],
  [
    [39.522, -121.548],
    [39.505, -121.560],
    [39.485, -121.590],
    [39.458, -121.638]
  ],
  [
    [39.595, -121.520],
    [39.570, -121.500],
    [39.548, -121.486]
  ]
]

const STAGE_LABELS = [
  { name: '怀仁水库 库区', lat: 39.895, lng: 113.265 },
  { name: '桑干河怀仁段 坝轴', lat: 39.870, lng: 113.280 },
  { name: '桑干河下游断面', lat: 39.845, lng: 113.310 },
  { name: '马鞍山高地避险区', lat: 39.830, lng: 113.340 }
]

const RISK_COPY: Record<FloodGridPoint['risk_level'], { label: string; color: string; className: string }> = {
  low: { label: '低风险', color: 'rgba(48, 181, 255, 0.3)', className: 'risk-low' },
  medium: { label: '中风险', color: 'rgba(255, 200, 65, 0.42)', className: 'risk-medium' },
  high: { label: '高风险', color: 'rgba(255, 110, 54, 0.54)', className: 'risk-high' },
  extreme: { label: '极高风险', color: 'rgba(255, 66, 82, 0.62)', className: 'risk-extreme' }
}

const SENSOR_STATUS_COPY: Record<SensorStation['status'], { label: string; color: string }> = {
  normal: { label: '正常', color: '#45f5b0' },
  warning: { label: '预警', color: '#ffcb57' },
  danger: { label: '危险', color: '#ff6673' }
}

const ROUTE_STATUS_COPY: Record<EvacuationRoute['status'], { label: string; color: string; dashArray: string }> = {
  safe: { label: '安全通行', color: '#45f5b0', dashArray: '10, 6' },
  caution: { label: '谨慎通行', color: '#ffcb57', dashArray: '12, 6' },
  dangerous: { label: '危险绕行', color: '#ff6673', dashArray: '4, 8' }
}

const shiftPolygon = (points: [number, number][], latOffset: number, lngOffset: number): [number, number][] =>
  points.map(([lat, lng]) => [lat + latOffset, lng + lngOffset])

const formatVelocity = (point: FloodGridPoint) => Math.sqrt(point.vel_u ** 2 + point.vel_v ** 2)

const buildFloodPopup = (point: FloodGridPoint) => {
  const risk = RISK_COPY[point.risk_level]

  return `
    <div class="screen-popup flood-popup">
      <div class="popup-title-row">
        <div class="popup-title">洪水网格详情</div>
        <div class="popup-badge ${risk.className}">${risk.label}</div>
      </div>
      <div class="popup-metrics">
        <div class="popup-metric"><span>中心坐标</span><strong>${point.lat.toFixed(4)}, ${point.lng.toFixed(4)}</strong></div>
        <div class="popup-metric"><span>积水深度</span><strong>${point.depth.toFixed(2)} m</strong></div>
        <div class="popup-metric"><span>流速强度</span><strong>${formatVelocity(point).toFixed(2)} m/s</strong></div>
      </div>
    </div>
  `
}

const buildSensorPopup = (sensor: SensorStation) => {
  const status = SENSOR_STATUS_COPY[sensor.status]

  return `
    <div class="screen-popup sensor-popup">
      <div class="popup-title-row">
        <div>
          <div class="popup-title">${sensor.name}</div>
          <div class="popup-subtitle">站点编号 ${sensor.station_id}</div>
        </div>
        <div class="popup-badge" style="border-color:${status.color}; color:${status.color};">${status.label}</div>
      </div>
      <div class="popup-grid">
        <div class="popup-grid-item"><span>水位</span><strong>${sensor.water_level.toFixed(2)} m</strong></div>
        <div class="popup-grid-item"><span>雨量</span><strong>${sensor.rainfall.toFixed(1)} mm/h</strong></div>
        <div class="popup-grid-item"><span>流速</span><strong>${sensor.flow_rate.toFixed(2)} m/s</strong></div>
        <div class="popup-grid-item"><span>电量</span><strong>${sensor.battery}%</strong></div>
        <div class="popup-grid-item"><span>信号</span><strong>${sensor.signal_quality}%</strong></div>
        <div class="popup-grid-item"><span>更新时间</span><strong>${new Date(sensor.last_update).toLocaleTimeString('zh-CN', { hour12: false })}</strong></div>
      </div>
    </div>
  `
}

const buildRoutePopup = (route: EvacuationRoute) => {
  const status = ROUTE_STATUS_COPY[route.status]

  return `
    <div class="screen-popup route-popup">
      <div class="popup-title-row">
        <div class="popup-title">避险疏散路线</div>
        <div class="popup-badge" style="border-color:${status.color}; color:${status.color};">${status.label}</div>
      </div>
      <div class="popup-route-name">${route.origin.name} → ${route.destination.name}</div>
      <div class="popup-metrics">
        <div class="popup-metric"><span>路线距离</span><strong>${route.distance.toFixed(1)} km</strong></div>
        <div class="popup-metric"><span>预计耗时</span><strong>${route.estimated_minutes} 分钟</strong></div>
        <div class="popup-metric"><span>风险评分</span><strong>${route.risk_score.toFixed(1)} / 100</strong></div>
      </div>
    </div>
  `
}

const buildRiskZonePopup = (riskLevel: FloodGridPoint['risk_level'], areaKm2: number) => {
  const risk = RISK_COPY[riskLevel]

  return `
    <div class="screen-popup risk-zone-popup">
      <div class="popup-title-row">
        <div class="popup-title">风险分区</div>
        <div class="popup-badge ${risk.className}">${risk.label}</div>
      </div>
      <div class="popup-metrics">
        <div class="popup-metric"><span>影响面积</span><strong>${areaKm2.toFixed(2)} km²</strong></div>
        <div class="popup-metric"><span>数据来源</span><strong>坝区模型实时推演</strong></div>
      </div>
    </div>
  `
}

const fitMapToScene = (map: L.Map) => {
  map.fitBounds(L.latLngBounds(REGION_BOUNDARY), {
    padding: [32, 32],
    maxZoom: 12.3
  })
}

const getRiskBorderColor = (riskLevel: FloodGridPoint['risk_level']) => {
  switch (riskLevel) {
    case 'extreme':
      return 'rgba(255, 94, 108, 0.96)'
    case 'high':
      return 'rgba(255, 166, 89, 0.9)'
    case 'medium':
      return 'rgba(255, 214, 102, 0.84)'
    default:
      return 'rgba(79, 213, 255, 0.82)'
  }
}

export const FloodMap: React.FC<FloodMapProps> = ({
  floodGrid,
  sensors,
  evacuationRoutes,
  riskZones,
  keyPoints = [],
  showVelocity = true,
  showRoutes = true,
  selectedStationId,
  selectedRouteId,
  selectedKeyPointId,
  onStationSelect,
  onKeyPointSelect
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const layersRef = useRef<{
    stage: L.LayerGroup
    zones: L.LayerGroup
    flood: L.LayerGroup
    velocity: L.LayerGroup
    sensors: L.LayerGroup
    routes: L.LayerGroup
    keyPoints: L.LayerGroup
    legend: L.Control
  } | null>(null)

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) {
      return
    }

    const container = mapContainerRef.current as HTMLElement & { _leaflet_id?: number }
    if (container._leaflet_id) {
      delete container._leaflet_id
    }

    try {
      const map = L.map(mapContainerRef.current, {
        zoomControl: false,
        attributionControl: false,
        preferCanvas: true
      }).setView(DEFAULT_VIEW, DEFAULT_ZOOM)

      const stageLayerGroup = L.layerGroup().addTo(map)
      const zonesLayerGroup = L.layerGroup().addTo(map)
      const floodLayerGroup = L.layerGroup().addTo(map)
      const velocityLayerGroup = L.layerGroup().addTo(map)
      const sensorsLayerGroup = L.layerGroup().addTo(map)
      const routesLayerGroup = L.layerGroup().addTo(map)
      const keyPointsLayerGroup = L.layerGroup().addTo(map)

      const extrudedSteps = [
        { latOffset: -0.02, lngOffset: 0.015, fill: 'rgba(6, 34, 48, 0.96)', opacity: 0.88 },
        { latOffset: -0.04, lngOffset: 0.03, fill: 'rgba(4, 24, 36, 0.92)', opacity: 0.82 },
        { latOffset: -0.06, lngOffset: 0.045, fill: 'rgba(3, 16, 26, 0.88)', opacity: 0.76 }
      ]

      extrudedSteps.forEach((step, index) => {
        stageLayerGroup.addLayer(
          L.polygon(shiftPolygon(REGION_BOUNDARY, step.latOffset, step.lngOffset), {
            color: 'rgba(0,0,0,0)',
            fillColor: step.fill,
            fillOpacity: step.opacity,
            className: `region-depth-shell region-depth-${index + 1}`
          })
        )
      })

      CONTOUR_BANDS.forEach((band) => {
        stageLayerGroup.addLayer(
          L.polygon(band.points, {
            color: 'rgba(143, 241, 255, 0.14)',
            weight: 1,
            opacity: band.opacity,
            fillColor: band.fill,
            fillOpacity: band.opacity,
            className: band.className
          })
        )
      })

      stageLayerGroup.addLayer(
        L.polygon(RESERVOIR_POLYGON, {
          color: 'rgba(114, 225, 255, 0.9)',
          weight: 1.5,
          fillColor: 'rgba(75, 196, 255, 0.18)',
          fillOpacity: 0.38,
          className: 'reservoir-polygon'
        })
      )

      stageLayerGroup.addLayer(
        L.polygon(REGION_BOUNDARY, {
          color: 'rgba(118, 235, 255, 0.95)',
          weight: 3.2,
          opacity: 0.96,
          fillColor: 'rgba(148, 255, 194, 0.2)',
          fillOpacity: 0.3,
          className: 'region-boundary-glow'
        })
      )

      stageLayerGroup.addLayer(
        L.polygon(REGION_BOUNDARY, {
          color: 'rgba(255, 245, 180, 0.86)',
          weight: 1.25,
          opacity: 0.8,
          fillColor: 'rgba(121, 236, 255, 0.08)',
          fillOpacity: 0.12,
          dashArray: '8, 10',
          className: 'region-boundary-inner'
        })
      )

      stageLayerGroup.addLayer(
        L.polyline(DAM_AXIS, {
          color: '#ffd470',
          weight: 6,
          opacity: 0.95,
          className: 'dam-axis-line'
        })
      )
      stageLayerGroup.addLayer(
        L.polyline(DOWNSTREAM_SECTION, {
          color: '#ff8b5c',
          weight: 3,
          opacity: 0.88,
          dashArray: '10, 8',
          className: 'downstream-section-line'
        })
      )

      stageLayerGroup.addLayer(
        L.polyline(MAIN_RIVER, {
          color: '#64ebff',
          weight: 7,
          opacity: 0.36,
          className: 'region-river-main-glow'
        })
      )
      stageLayerGroup.addLayer(
        L.polyline(MAIN_RIVER, {
          color: '#bfffff',
          weight: 3,
          opacity: 0.96,
          className: 'region-river-main'
        })
      )

      BRANCH_RIVERS.forEach((river, index) => {
        stageLayerGroup.addLayer(
          L.polyline(river, {
            color: '#8df3ff',
            weight: 2,
            opacity: 0.76,
            className: `region-river-branch region-river-branch-${index + 1}`
          })
        )
      })

      STAGE_LABELS.forEach((label) => {
        const icon = L.divIcon({
          className: 'stage-label-marker',
          html: `<div class="stage-label-chip">${label.name}</div>`,
          iconSize: [126, 28],
          iconAnchor: [63, 14]
        })

        stageLayerGroup.addLayer(L.marker([label.lat, label.lng], { icon, interactive: false }))
      })

      const damIcon = L.divIcon({
        className: 'dam-marker',
        html: '<div class="dam-marker-core">坝</div>',
        iconSize: [34, 34],
        iconAnchor: [17, 17]
      })
      stageLayerGroup.addLayer(L.marker([39.537193, -121.485565], { icon: damIcon, interactive: false }))

      const beaconIcon = L.divIcon({
        className: 'map-beacon-marker',
        html: '<div class="map-beacon-core"></div>',
        iconSize: [20, 20],
        iconAnchor: [10, 10]
      })
      stageLayerGroup.addLayer(L.marker([39.52155294, -121.5477477], { icon: beaconIcon, interactive: false }))

      const legend = new L.Control({ position: 'bottomright' })
      legend.onAdd = () => {
        const div = L.DomUtil.create('div', 'flood-legend')
        div.innerHTML = `
          <div class="legend-title">坝区洪水图例</div>
          <div class="legend-item"><span class="legend-color risk-extreme"></span><span>极高风险 · 深度 &gt; 2.0 m</span></div>
          <div class="legend-item"><span class="legend-color risk-high"></span><span>高风险 · 深度 1.0 - 2.0 m</span></div>
          <div class="legend-item"><span class="legend-color risk-medium"></span><span>中风险 · 深度 0.5 - 1.0 m</span></div>
          <div class="legend-item"><span class="legend-color risk-low"></span><span>低风险 · 深度 &lt; 0.5 m</span></div>
        `
        return div
      }
      legend.addTo(map)

      const stageControl = new L.Control({ position: 'topright' })
      stageControl.onAdd = () => {
        const div = L.DomUtil.create('div', 'flood-stage-control')
        div.innerHTML = `
          <button class="stage-btn zoom-in-btn" title="放大场景">+</button>
          <button class="stage-btn zoom-out-btn" title="缩小场景">-</button>
          <button class="stage-btn fit-btn" title="回到流域主视角">定位</button>
          <button class="stage-btn fullscreen-btn" title="全屏查看">全屏</button>
        `

        const zoomInButton = div.querySelector('.zoom-in-btn') as HTMLButtonElement
        const zoomOutButton = div.querySelector('.zoom-out-btn') as HTMLButtonElement
        const fitButton = div.querySelector('.fit-btn') as HTMLButtonElement
        const fullscreenButton = div.querySelector('.fullscreen-btn') as HTMLButtonElement

        L.DomEvent.disableClickPropagation(div)
        zoomInButton.onclick = () => map.zoomIn()
        zoomOutButton.onclick = () => map.zoomOut()
        fitButton.onclick = () => fitMapToScene(map)
        fullscreenButton.onclick = () => {
          void mapContainerRef.current?.requestFullscreen?.()
        }

        return div
      }
      stageControl.addTo(map)

      fitMapToScene(map)

      mapRef.current = map
      layersRef.current = {
        stage: stageLayerGroup,
        zones: zonesLayerGroup,
        flood: floodLayerGroup,
        velocity: velocityLayerGroup,
        sensors: sensorsLayerGroup,
        routes: routesLayerGroup,
        keyPoints: keyPointsLayerGroup,
        legend
      }
    } catch (error) {
      console.error('Leaflet 场景地图初始化失败', error)
    }
  }, [])

  useEffect(() => {
    if (!layersRef.current) {
      return
    }

    const zonesLayerGroup = layersRef.current.zones
    zonesLayerGroup.clearLayers()

    riskZones?.features.forEach((feature) => {
      const latLngRings = feature.geometry.coordinates.map((ring) =>
        ring.map(([lng, lat]) => [lat, lng] as [number, number])
      )
      const borderColor = getRiskBorderColor(feature.properties.risk_level)

      const polygon = L.polygon(latLngRings, {
        color: borderColor,
        weight: feature.properties.risk_level === 'extreme' ? 1.8 : 1.1,
        opacity: 0.62,
        fillColor: feature.properties.color,
        fillOpacity: feature.properties.risk_level === 'extreme' ? 0.14 : 0.08,
        dashArray: feature.properties.risk_level === 'extreme' ? undefined : '8, 7',
        className: `risk-zone-overlay zone-${feature.properties.risk_level}`
      })

      polygon.bindPopup(buildRiskZonePopup(feature.properties.risk_level, feature.properties.area_km2), {
        offset: [0, -6],
        className: 'leaflet-screen-popup'
      })
      zonesLayerGroup.addLayer(polygon)
    })
  }, [riskZones])

  useEffect(() => {
    if (!layersRef.current) {
      return
    }

    const floodLayerGroup = layersRef.current.flood
    floodLayerGroup.clearLayers()

    floodGrid.forEach((point) => {
      if (!point.flooded) {
        return
      }

      const risk = RISK_COPY[point.risk_level]
      const bounds = L.latLngBounds(
        [point.lat - GRID_SIZE / 2, point.lng - GRID_SIZE / 2],
        [point.lat + GRID_SIZE / 2, point.lng + GRID_SIZE / 2]
      )

      const rectangle = L.rectangle(bounds, {
        color: risk.color,
        weight: 0.45,
        opacity: 0.36,
        fillColor: risk.color,
        fillOpacity:
          point.risk_level === 'extreme' ? 0.24 : point.risk_level === 'high' ? 0.19 : point.risk_level === 'medium' ? 0.14 : 0.08,
        className: `flood-rect ${risk.className}`
      })

      rectangle.bindPopup(buildFloodPopup(point), {
        offset: [0, -6],
        className: 'leaflet-screen-popup'
      })
      floodLayerGroup.addLayer(rectangle)

      if (point.risk_level === 'high' || point.risk_level === 'extreme') {
        floodLayerGroup.addLayer(
          L.circleMarker([point.lat, point.lng], {
            radius: point.risk_level === 'extreme' ? 8 : 6,
            color: point.risk_level === 'extreme' ? '#ff5c6f' : '#ffb85f',
            weight: 0.9,
            opacity: 0.52,
            fillColor: point.risk_level === 'extreme' ? '#ff475d' : '#ffc864',
            fillOpacity: 0.12,
            className: `risk-hotspot hotspot-${point.risk_level}`
          })
        )
      }
    })
  }, [floodGrid])

  useEffect(() => {
    if (!layersRef.current) {
      return
    }

    const velocityLayerGroup = layersRef.current.velocity
    velocityLayerGroup.clearLayers()

    if (!showVelocity) {
      return
    }

    floodGrid.forEach((point) => {
      if (!point.flooded) {
        return
      }

      const velocity = formatVelocity(point)
      if (velocity < 0.3) {
        return
      }

      const angle = Math.atan2(point.vel_v, point.vel_u) * (180 / Math.PI)
      const arrowLength = Math.min(velocity * 0.01, 0.05)
      const endLat = point.lat + (arrowLength * Math.cos((angle * Math.PI) / 180)) / 111
      const endLng = point.lng + (arrowLength * Math.sin((angle * Math.PI) / 180)) / (111 * Math.cos((point.lat * Math.PI) / 180))

      const arrowStyle = {
        color: '#8fe8ff',
        weight: 2,
        opacity: 0.9,
        dashArray: '5, 5',
        className: 'velocity-arrow'
      }

      velocityLayerGroup.addLayer(
        L.polyline(
          [
            [point.lat, point.lng],
            [endLat, endLng]
          ],
          arrowStyle
        )
      )

      const arrowSize = 0.02
      const headLat1 = endLat - (arrowSize * Math.cos(((angle - 30) * Math.PI) / 180)) / 111
      const headLng1 = endLng - (arrowSize * Math.sin(((angle - 30) * Math.PI) / 180)) / (111 * Math.cos((endLat * Math.PI) / 180))
      const headLat2 = endLat - (arrowSize * Math.cos(((angle + 30) * Math.PI) / 180)) / 111
      const headLng2 = endLng - (arrowSize * Math.sin(((angle + 30) * Math.PI) / 180)) / (111 * Math.cos((endLat * Math.PI) / 180))

      velocityLayerGroup.addLayer(L.polyline([[endLat, endLng], [headLat1, headLng1]], arrowStyle))
      velocityLayerGroup.addLayer(L.polyline([[endLat, endLng], [headLat2, headLng2]], arrowStyle))
    })
  }, [floodGrid, showVelocity])

  useEffect(() => {
    if (!layersRef.current) {
      return
    }

    const sensorsLayerGroup = layersRef.current.sensors
    sensorsLayerGroup.clearLayers()

    sensors.forEach((sensor) => {
      const status = SENSOR_STATUS_COPY[sensor.status]
      const icon = L.divIcon({
        className: `sensor-marker sensor-${sensor.status}`,
        html: `
          <div class="sensor-halo" style="box-shadow: 0 0 20px ${status.color};"></div>
          <div class="sensor-dot" style="background-color: ${status.color}; box-shadow: 0 0 12px ${status.color};"></div>
        `,
        iconSize: [22, 22],
        iconAnchor: [11, 11]
      })

      const marker = L.marker([sensor.lat, sensor.lng], { icon })
      marker.bindPopup(buildSensorPopup(sensor), {
        offset: [0, -6],
        className: 'leaflet-screen-popup'
      })
      marker.on('click', () => onStationSelect?.(sensor))
      sensorsLayerGroup.addLayer(marker)
    })
  }, [sensors, onStationSelect])

  useEffect(() => {
    if (!layersRef.current) {
      return
    }

    const keyPointsLayerGroup = layersRef.current.keyPoints
    keyPointsLayerGroup.clearLayers()

    keyPoints.forEach((point) => {
      if (typeof point.lat !== 'number' || typeof point.lng !== 'number') {
        return
      }

      const color =
        point.risk_level === 'extreme'
          ? '#ff6673'
          : point.risk_level === 'high'
            ? '#ff9858'
            : point.risk_level === 'medium'
              ? '#ffd56f'
              : '#45f5b0'

      const icon = L.divIcon({
        className: `key-point-marker key-point-${point.risk_level} ${selectedKeyPointId === point.id ? 'is-selected' : ''}`,
        html: `<div class="key-point-core" style="border-color:${color}; box-shadow:0 0 18px ${color}66;">${point.type.slice(0, 1)}</div>`,
        iconSize: [28, 28],
        iconAnchor: [14, 14]
      })

      const marker = L.marker([point.lat, point.lng], { icon })
      marker.bindPopup(
        `
        <div class="screen-popup sensor-popup">
          <div class="popup-title-row">
            <div>
              <div class="popup-title">${point.name}</div>
              <div class="popup-subtitle">${point.type}</div>
            </div>
            <div class="popup-badge" style="border-color:${color}; color:${color};">${point.risk_level}</div>
          </div>
          <div class="popup-grid">
            <div class="popup-grid-item"><span>积水深度</span><strong>${point.water_depth.toFixed(2)} m</strong></div>
            <div class="popup-grid-item"><span>对象类别</span><strong>${point.type}</strong></div>
          </div>
        </div>
        `,
        {
          offset: [0, -6],
          className: 'leaflet-screen-popup'
        }
      )
      marker.on('click', () => onKeyPointSelect?.(point))
      keyPointsLayerGroup.addLayer(marker)
    })
  }, [keyPoints, onKeyPointSelect, selectedKeyPointId])

  useEffect(() => {
    if (!layersRef.current) {
      return
    }

    const routesLayerGroup = layersRef.current.routes
    routesLayerGroup.clearLayers()

    if (!showRoutes) {
      return
    }

    evacuationRoutes.forEach((route) => {
      const routeStyle = ROUTE_STATUS_COPY[route.status]
      const pathLine = L.polyline(
        [
          [route.origin.lat, route.origin.lng],
          ...route.waypoints.map((waypoint) => [waypoint.lat, waypoint.lng] as [number, number]),
          [route.destination.lat, route.destination.lng]
        ],
        {
          color: routeStyle.color,
          weight: 3,
          opacity: 0.9,
          dashArray: routeStyle.dashArray,
          className: `evacuation-route route-${route.status}`
        }
      )

      const midPoint = route.waypoints[Math.floor(route.waypoints.length / 2)] || {
        lat: (route.origin.lat + route.destination.lat) / 2,
        lng: (route.origin.lng + route.destination.lng) / 2
      }

      pathLine.bindPopup(buildRoutePopup(route), {
        autoClose: false,
        offset: [0, -6],
        className: 'leaflet-screen-popup'
      })

      pathLine.on('mouseover', () => {
        pathLine.openPopup(midPoint)
        pathLine.setStyle({ weight: 4.5, opacity: 1 })
      })

      pathLine.on('mouseout', () => {
        pathLine.closePopup()
        pathLine.setStyle({ weight: 3, opacity: 0.9 })
      })

      routesLayerGroup.addLayer(pathLine)

      const originIcon = L.divIcon({
        className: 'route-marker origin-marker',
        html: '<div class="marker-dot">起</div>',
        iconSize: [26, 26],
        iconAnchor: [13, 13]
      })

      const destinationIcon = L.divIcon({
        className: 'route-marker dest-marker',
        html: '<div class="marker-dot">终</div>',
        iconSize: [26, 26],
        iconAnchor: [13, 13]
      })

      routesLayerGroup.addLayer(L.marker([route.origin.lat, route.origin.lng], { icon: originIcon }))
      routesLayerGroup.addLayer(L.marker([route.destination.lat, route.destination.lng], { icon: destinationIcon }))
    })
  }, [evacuationRoutes, showRoutes])

  useEffect(() => {
    if (!mapRef.current) {
      return
    }

    if (sensors.length >= 2) {
      mapRef.current.fitBounds(L.latLngBounds(sensors.map((sensor) => [sensor.lat, sensor.lng] as [number, number])), {
        padding: [44, 44],
        maxZoom: 12.5
      })
      return
    }

    fitMapToScene(mapRef.current)
  }, [sensors])

  useEffect(() => {
    if (!mapRef.current || !selectedStationId) {
      return
    }

    const station = sensors.find((item) => item.station_id === selectedStationId)
    if (!station) {
      return
    }

    mapRef.current.flyTo([station.lat, station.lng], Math.max(mapRef.current.getZoom(), 12.5), {
      duration: 0.6
    })
  }, [selectedStationId, sensors])

  useEffect(() => {
    if (!mapRef.current || !selectedRouteId) {
      return
    }

    const route = evacuationRoutes.find((item) => item.id === selectedRouteId)
    if (!route) {
      return
    }

    const points: [number, number][] = [
      [route.origin.lat, route.origin.lng],
      ...route.waypoints.map((waypoint) => [waypoint.lat, waypoint.lng] as [number, number]),
      [route.destination.lat, route.destination.lng]
    ]

    mapRef.current.fitBounds(L.latLngBounds(points), {
      padding: [60, 60],
      maxZoom: 13
    })
  }, [evacuationRoutes, selectedRouteId])

  useEffect(() => {
    if (!mapRef.current || !selectedKeyPointId) {
      return
    }

    const point = keyPoints.find((item) => item.id === selectedKeyPointId && typeof item.lat === 'number' && typeof item.lng === 'number')
    if (!point || typeof point.lat !== 'number' || typeof point.lng !== 'number') {
      return
    }

    mapRef.current.flyTo([point.lat, point.lng], Math.max(mapRef.current.getZoom(), 12.8), {
      duration: 0.6
    })
  }, [keyPoints, selectedKeyPointId])

  useEffect(() => {
    return () => {
      if (mapRef.current) {
        mapRef.current.remove()
        mapRef.current = null
        layersRef.current = null
      }
    }
  }, [])

  return <div ref={mapContainerRef} className="flood-map-container" />
}

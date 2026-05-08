import React, { useEffect, useMemo, useRef } from 'react'
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

type LatLng = [number, number]

type ContextLine = {
  name: string
  points: LatLng[]
}

type Settlement = {
  name: string
  type: string
  lat: number
  lng: number
}

type MapContext = {
  id: 'sanggan' | 'oroville'
  title: string
  subtitle: string
  source: string
  center: LatLng
  zoom: number
  bounds: LatLng[]
  waterBodies: LatLng[][]
  rivers: ContextLine[]
  roads: ContextLine[]
  settlements: Settlement[]
  dam: {
    name: string
    lat: number
    lng: number
    axis: LatLng[]
  }
}

const SANGGAN_CONTEXT: MapContext = {
  id: 'sanggan',
  title: '桑干河怀仁段 10年一遇洪水淹没范围图',
  subtitle: '遥感底图 / DEM 模型网格 / 河道与村镇专题要素',
  source: 'Imagery: Esri World Imagery · Context: OSM + local case dataset',
  center: [39.805, 113.39],
  zoom: 11,
  bounds: [
    [39.878, 113.278],
    [39.878, 113.505],
    [39.704, 113.505],
    [39.704, 113.278]
  ],
  waterBodies: [
    [
      [39.858, 113.288],
      [39.848, 113.315],
      [39.831, 113.345],
      [39.807, 113.388],
      [39.775, 113.452],
      [39.766, 113.461],
      [39.779, 113.407],
      [39.802, 113.356],
      [39.828, 113.318],
      [39.850, 113.286]
    ]
  ],
  rivers: [
    {
      name: '桑干河主槽',
      points: [
        [39.860, 113.290],
        [39.848, 113.312],
        [39.842, 113.322],
        [39.820, 113.355],
        [39.800, 113.400],
        [39.768, 113.455]
      ]
    },
    {
      name: '南侧支沟',
      points: [
        [39.825, 113.305],
        [39.807, 113.342],
        [39.790, 113.386],
        [39.772, 113.430]
      ]
    }
  ],
  roads: [
    {
      name: 'S212 大繁线',
      points: [
        [39.803, 113.249],
        [39.806, 113.285],
        [39.818, 113.302],
        [39.837, 113.291],
        [39.861, 113.290],
        [39.913, 113.289]
      ]
    },
    {
      name: 'S502 大浑线',
      points: [
        [39.873, 113.485],
        [39.858, 113.526],
        [39.844, 113.545],
        [39.826, 113.551],
        [39.813, 113.554]
      ]
    },
    {
      name: '河谷联络线',
      points: [
        [39.702, 113.291],
        [39.717, 113.304],
        [39.744, 113.295],
        [39.785, 113.308],
        [39.842, 113.322]
      ]
    }
  ],
  settlements: [
    { name: '怀仁城区', type: 'city', lat: 39.829, lng: 113.381 },
    { name: '吉家庄乡', type: 'town', lat: 39.851, lng: 113.456 },
    { name: '马辛庄村', type: 'village', lat: 39.838, lng: 113.294 },
    { name: '王皓疃村', type: 'village', lat: 39.764, lng: 113.332 },
    { name: '上西河村', type: 'village', lat: 39.779, lng: 113.361 },
    { name: '金沙滩镇', type: 'town', lat: 39.827, lng: 113.376 }
  ],
  dam: {
    name: '怀仁段控制断面',
    lat: 39.842,
    lng: 113.322,
    axis: [
      [39.846, 113.316],
      [39.838, 113.328]
    ]
  }
}

const OROVILLE_CONTEXT: MapContext = {
  id: 'oroville',
  title: 'Oroville Dam 10-year Flood Inundation Map',
  subtitle: 'Remote imagery / Feather River corridor / model-derived inundation',
  source: 'Imagery: Esri World Imagery · Context: OpenStreetMap via Overpass',
  center: [39.515, -121.545],
  zoom: 12,
  bounds: [
    [39.602, -121.682],
    [39.602, -121.388],
    [39.416, -121.388],
    [39.416, -121.682]
  ],
  waterBodies: [
    [
      [39.592, -121.448],
      [39.575, -121.405],
      [39.535, -121.392],
      [39.505, -121.428],
      [39.514, -121.478],
      [39.537, -121.494],
      [39.565, -121.485]
    ]
  ],
  rivers: [
    {
      name: 'Feather River',
      points: [
        [39.590, -121.430],
        [39.565, -121.465],
        [39.537, -121.486],
        [39.522, -121.548],
        [39.513, -121.556],
        [39.496, -121.552],
        [39.470, -121.615],
        [39.445, -121.638]
      ]
    },
    {
      name: 'Campbell Creek',
      points: [
        [39.596, -121.520],
        [39.570, -121.500],
        [39.548, -121.486],
        [39.522, -121.548]
      ]
    },
    {
      name: 'Little Cottonwood Creek',
      points: [
        [39.565, -121.430],
        [39.540, -121.455],
        [39.515, -121.478],
        [39.498, -121.505]
      ]
    }
  ],
  roads: [
    {
      name: 'Oroville Dam Blvd E',
      points: [
        [39.537, -121.486],
        [39.524, -121.505],
        [39.515, -121.533],
        [39.512, -121.557]
      ]
    },
    {
      name: 'Oroville-Quincy Hwy',
      points: [
        [39.570, -121.470],
        [39.545, -121.505],
        [39.525, -121.545],
        [39.515, -121.570]
      ]
    },
    {
      name: 'Nelson Ave',
      points: [
        [39.495, -121.615],
        [39.500, -121.575],
        [39.503, -121.542]
      ]
    }
  ],
  settlements: [
    { name: 'Oroville', type: 'town', lat: 39.5138, lng: -121.5564 },
    { name: 'Thermalito', type: 'village', lat: 39.5113, lng: -121.5869 },
    { name: 'South Oroville', type: 'hamlet', lat: 39.4966, lng: -121.5522 },
    { name: 'Palermo', type: 'village', lat: 39.435, lng: -121.547 },
    { name: 'Oroville Junction', type: 'hamlet', lat: 39.5096, lng: -121.6505 },
    { name: 'Wyandotte', type: 'hamlet', lat: 39.4579, lng: -121.4677 }
  ],
  dam: {
    name: 'Oroville Dam',
    lat: 39.537193,
    lng: -121.485565,
    axis: [
      [39.5374, -121.4975],
      [39.5367, -121.4745]
    ]
  }
}

const RISK_COPY: Record<FloodGridPoint['risk_level'], { label: string; color: string }> = {
  low: { label: '低风险', color: '#2cb7ff' },
  medium: { label: '中风险', color: '#35d7ff' },
  high: { label: '高风险', color: '#ffb14d' },
  extreme: { label: '极高风险', color: '#ff4d62' }
}

const SENSOR_STATUS_COPY: Record<SensorStation['status'], { label: string; color: string }> = {
  normal: { label: '正常', color: '#52f6b9' },
  warning: { label: '预警', color: '#ffd166' },
  danger: { label: '危险', color: '#ff5d73' }
}

const ROUTE_STATUS_COPY: Record<EvacuationRoute['status'], { color: string; dashArray: string }> = {
  safe: { color: '#52f6b9', dashArray: '12, 7' },
  caution: { color: '#ffd166', dashArray: '10, 7' },
  dangerous: { color: '#ff5d73', dashArray: '4, 8' }
}

const asLatLngBounds = (points: LatLng[]) => L.latLngBounds(points.map(([lat, lng]) => L.latLng(lat, lng)))

const uniqueSorted = (values: number[]) => [...new Set(values.map((value) => Number(value.toFixed(6))))].sort((a, b) => a - b)

const inferGridStep = (values: number[], fallback: number) => {
  const sorted = uniqueSorted(values)
  const deltas = sorted
    .slice(1)
    .map((value, index) => Math.abs(value - sorted[index]))
    .filter((delta) => delta > 0.00001)
  return deltas.length > 0 ? Math.min(...deltas) : fallback
}

const resolveContext = (floodGrid: FloodGridPoint[], sensors: SensorStation[], keyPoints: AffectedKeyPoint[]) => {
  const lngValues = [
    ...floodGrid.map((point) => point.lng),
    ...sensors.map((station) => station.lng),
    ...keyPoints.map((point) => point.lng).filter((value): value is number => typeof value === 'number')
  ]

  return lngValues.some((lng) => lng < 0) ? OROVILLE_CONTEXT : SANGGAN_CONTEXT
}

const buildFloodEnvelope = (points: FloodGridPoint[], minDepth: number, latStep: number, lngStep: number): LatLng[] | null => {
  const flooded = points.filter((point) => point.flooded && point.depth >= minDepth)
  if (flooded.length === 0) {
    return null
  }

  const groups = new Map<number, { lng: number; minLat: number; maxLat: number }>()
  flooded.forEach((point) => {
    const key = Math.round(point.lng / Math.max(lngStep, 0.00001))
    const current = groups.get(key)
    if (!current) {
      groups.set(key, { lng: point.lng, minLat: point.lat, maxLat: point.lat })
      return
    }
    current.minLat = Math.min(current.minLat, point.lat)
    current.maxLat = Math.max(current.maxLat, point.lat)
  })

  const columns = [...groups.values()].sort((left, right) => left.lng - right.lng)
  const latPad = latStep * 0.56
  const lngPad = lngStep * 0.52

  if (columns.length === 1) {
    const column = columns[0]
    return [
      [column.maxLat + latPad, column.lng - lngPad],
      [column.maxLat + latPad, column.lng + lngPad],
      [column.minLat - latPad, column.lng + lngPad],
      [column.minLat - latPad, column.lng - lngPad]
    ]
  }

  const upperEdge = columns.map((column, index) => {
    const endPad = index === 0 ? -lngPad : index === columns.length - 1 ? lngPad : 0
    return [column.maxLat + latPad, column.lng + endPad] as LatLng
  })
  const lowerEdge = [...columns].reverse().map((column, index) => {
    const endPad = index === 0 ? lngPad : index === columns.length - 1 ? -lngPad : 0
    return [column.minLat - latPad, column.lng + endPad] as LatLng
  })

  return [...upperEdge, ...lowerEdge]
}

const buildVelocitySegment = (point: FloodGridPoint): [LatLng, LatLng] => {
  const speed = Math.sqrt(point.vel_u ** 2 + point.vel_v ** 2)
  const angle = Math.atan2(point.vel_v, point.vel_u)
  const length = Math.min(speed * 0.004, 0.014)
  return [
    [point.lat, point.lng],
    [point.lat + Math.cos(angle) * length, point.lng + Math.sin(angle) * length]
  ]
}

const buildFloodPopup = (depth: number, areaLabel: string) => `
  <div class="map-popup">
    <strong>${areaLabel}</strong>
    <span>模型推演最大水深 ${depth.toFixed(2)} m</span>
    <span>蓝色连续面由当前洪水网格实时聚合生成</span>
  </div>
`

const buildSensorPopup = (sensor: SensorStation) => {
  const status = SENSOR_STATUS_COPY[sensor.status]
  return `
    <div class="map-popup">
      <strong>${sensor.name}</strong>
      <span style="color:${status.color}">${status.label}</span>
      <span>水位 ${sensor.water_level.toFixed(2)} m · 降雨 ${sensor.rainfall.toFixed(1)} mm/h</span>
      <span>流速 ${sensor.flow_rate.toFixed(2)} m/s · ${new Date(sensor.last_update).toLocaleTimeString('zh-CN', { hour12: false })}</span>
    </div>
  `
}

const buildKeyPointPopup = (point: AffectedKeyPoint) => `
  <div class="map-popup">
    <strong>${point.name}</strong>
    <span>${point.type} · ${RISK_COPY[point.risk_level].label}</span>
    <span>影响水深 ${point.water_depth.toFixed(2)} m</span>
  </div>
`

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
  const scaleControlRef = useRef<L.Control.Scale | null>(null)
  const layersRef = useRef<{
    context: L.LayerGroup
    zones: L.LayerGroup
    flood: L.LayerGroup
    velocity: L.LayerGroup
    sensors: L.LayerGroup
    routes: L.LayerGroup
    keyPoints: L.LayerGroup
  } | null>(null)

  const context = useMemo(() => resolveContext(floodGrid, sensors, keyPoints), [floodGrid, sensors, keyPoints])
  const floodedPoints = useMemo(() => floodGrid.filter((point) => point.flooded), [floodGrid])
  const maxDepth = useMemo(() => floodedPoints.reduce((max, point) => Math.max(max, point.depth), 0), [floodedPoints])
  const gridMetrics = useMemo(
    () => ({
      latStep: inferGridStep(floodGrid.map((point) => point.lat), 0.0055),
      lngStep: inferGridStep(floodGrid.map((point) => point.lng), 0.0055)
    }),
    [floodGrid]
  )
  const floodedAreaLabel = useMemo(() => {
    if (floodedPoints.length === 0) {
      return '0.0 km²'
    }
    const meanLat = floodedPoints.reduce((sum, point) => sum + point.lat, 0) / floodedPoints.length
    const cellAreaKm2 = Math.abs(gridMetrics.latStep * 111 * gridMetrics.lngStep * 111 * Math.cos((meanLat * Math.PI) / 180))
    return `${(cellAreaKm2 * floodedPoints.length).toFixed(1)} km²`
  }, [floodedPoints, gridMetrics])
  const floodRenderState = useMemo(
    () => ({
      floodEnvelope: buildFloodEnvelope(floodGrid, 0.02, gridMetrics.latStep, gridMetrics.lngStep),
      deepEnvelope: buildFloodEnvelope(floodGrid, 1.0, gridMetrics.latStep, gridMetrics.lngStep),
      extremeEnvelope: buildFloodEnvelope(floodGrid, 2.0, gridMetrics.latStep, gridMetrics.lngStep),
      hotSpots: floodedPoints
        .filter((point) => point.risk_level === 'high' || point.risk_level === 'extreme')
        .sort((left, right) => right.depth - left.depth)
        .slice(0, 18)
    }),
    [floodGrid, floodedPoints, gridMetrics]
  )
  const velocitySegments = useMemo(() => {
    if (!showVelocity) {
      return []
    }
    return floodedPoints
      .map((point) => ({ point, speed: Math.sqrt(point.vel_u ** 2 + point.vel_v ** 2) }))
      .filter((item) => item.speed >= 0.35)
      .sort((left, right) => right.speed - left.speed)
      .slice(0, 22)
      .map((item) => buildVelocitySegment(item.point))
  }, [floodedPoints, showVelocity])

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) {
      return
    }

    const container = mapContainerRef.current as HTMLDivElement & { _leaflet_id?: number }
    if (container._leaflet_id) {
      delete container._leaflet_id
    }

    const map = L.map(mapContainerRef.current, {
      zoomControl: false,
      attributionControl: true,
      preferCanvas: true,
      renderer: L.canvas({ padding: 0.35 }),
      markerZoomAnimation: false,
      wheelDebounceTime: 50,
      zoomSnap: 0.25,
      minZoom: 8,
      maxZoom: 17
    }).setView(context.center, context.zoom)

    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
      maxZoom: 17,
      keepBuffer: 1,
      updateWhenIdle: true,
      updateWhenZooming: false,
      attribution: 'Tiles © Esri · Source: Esri, Maxar, Earthstar Geographics and GIS User Community'
    }).addTo(map)

    const contextLayerGroup = L.layerGroup().addTo(map)
    const zonesLayerGroup = L.layerGroup().addTo(map)
    const floodLayerGroup = L.layerGroup().addTo(map)
    const velocityLayerGroup = L.layerGroup().addTo(map)
    const sensorsLayerGroup = L.layerGroup().addTo(map)
    const routesLayerGroup = L.layerGroup().addTo(map)
    const keyPointsLayerGroup = L.layerGroup().addTo(map)

    const zoomControl = new L.Control({ position: 'topright' })
    zoomControl.onAdd = () => {
      const div = L.DomUtil.create('div', 'map-topic-tools')
      div.innerHTML = `
        <button type="button" class="map-tool-btn map-zoom-in">+</button>
        <button type="button" class="map-tool-btn map-zoom-out">-</button>
        <button type="button" class="map-tool-btn map-fit">复位</button>
        <button type="button" class="map-tool-btn map-fullscreen">全屏</button>
      `
      L.DomEvent.disableClickPropagation(div)
      ;(div.querySelector('.map-zoom-in') as HTMLButtonElement).onclick = () => map.zoomIn()
      ;(div.querySelector('.map-zoom-out') as HTMLButtonElement).onclick = () => map.zoomOut()
      ;(div.querySelector('.map-fit') as HTMLButtonElement).onclick = () => map.fitBounds(asLatLngBounds(context.bounds), { padding: [26, 26] })
      ;(div.querySelector('.map-fullscreen') as HTMLButtonElement).onclick = () => {
        void mapContainerRef.current?.parentElement?.requestFullscreen?.()
      }
      return div
    }
    zoomControl.addTo(map)

    scaleControlRef.current = L.control.scale({ position: 'bottomleft', metric: true, imperial: false }).addTo(map)

    mapRef.current = map
    layersRef.current = {
      context: contextLayerGroup,
      zones: zonesLayerGroup,
      flood: floodLayerGroup,
      velocity: velocityLayerGroup,
      sensors: sensorsLayerGroup,
      routes: routesLayerGroup,
      keyPoints: keyPointsLayerGroup
    }
  }, [context.bounds, context.center, context.zoom])

  useEffect(() => {
    const map = mapRef.current
    const layers = layersRef.current
    if (!map || !layers) {
      return
    }

    layers.context.clearLayers()

    layers.context.addLayer(
      L.polygon(context.bounds, {
        color: '#fff1b8',
        weight: 2,
        opacity: 0.92,
        fillColor: '#102d1e',
        fillOpacity: 0.08,
        dashArray: '10, 8',
        className: 'study-boundary'
      })
    )

    context.waterBodies.forEach((polygon) => {
      layers.context.addLayer(
        L.polygon(polygon, {
          color: '#77d9ff',
          weight: 1.4,
          opacity: 0.84,
          fillColor: '#005cbd',
          fillOpacity: 0.28,
          className: 'water-body-layer'
        })
      )
    })

    context.roads.forEach((road) => {
      layers.context.addLayer(
        L.polyline(road.points, {
          color: '#fff4c7',
          weight: 2.2,
          opacity: 0.72,
          className: 'context-road'
        }).bindTooltip(road.name, { sticky: true, className: 'topic-tooltip' })
      )
    })

    context.rivers.forEach((river) => {
      layers.context.addLayer(
        L.polyline(river.points, {
          color: '#19c9ff',
          weight: river.name.includes('主') || river.name.includes('Feather') ? 5 : 3,
          opacity: 0.96,
          className: 'context-river'
        }).bindTooltip(river.name, { sticky: true, className: 'topic-tooltip' })
      )
    })

    layers.context.addLayer(
      L.polyline(context.dam.axis, {
        color: '#ffdf7d',
        weight: 7,
        opacity: 0.95,
        className: 'dam-axis-line'
      }).bindTooltip(context.dam.name, { sticky: true, className: 'topic-tooltip' })
    )

    const damIcon = L.divIcon({
      className: 'topic-dam-marker',
      html: '<div>坝</div>',
      iconSize: [34, 34],
      iconAnchor: [17, 17]
    })
    layers.context.addLayer(L.marker([context.dam.lat, context.dam.lng], { icon: damIcon }).bindTooltip(context.dam.name, { className: 'topic-tooltip' }))

    context.settlements.forEach((settlement) => {
      const icon = L.divIcon({
        className: `topic-place-marker topic-place-${settlement.type}`,
        html: `<span></span><strong>${settlement.name}</strong>`,
        iconSize: [118, 26],
        iconAnchor: [8, 13]
      })
      layers.context.addLayer(L.marker([settlement.lat, settlement.lng], { icon, interactive: false }))
    })

    map.fitBounds(asLatLngBounds(context.bounds), { padding: [24, 24], animate: false })
  }, [context])

  useEffect(() => {
    const layers = layersRef.current
    if (!layers) {
      return
    }

    layers.zones.clearLayers()

    riskZones?.features.forEach((feature) => {
      const rings = feature.geometry.coordinates.map((ring) => ring.map(([lng, lat]) => [lat, lng] as LatLng))
      layers.zones.addLayer(
        L.polygon(rings, {
          color: feature.properties.risk_level === 'extreme' ? '#ff5d73' : '#76e5ff',
          weight: feature.properties.risk_level === 'extreme' ? 2 : 1,
          opacity: 0.42,
          fillColor: '#0878ff',
          fillOpacity: 0.05,
          dashArray: '8, 9',
          className: 'risk-contour-layer'
        })
      )
    })
  }, [riskZones])

  useEffect(() => {
    const layers = layersRef.current
    if (!layers) {
      return
    }

    layers.flood.clearLayers()

    const { floodEnvelope, deepEnvelope, extremeEnvelope, hotSpots } = floodRenderState

    if (floodEnvelope) {
      layers.flood.addLayer(
        L.polygon(floodEnvelope, {
          color: '#0428d8',
          weight: 1.8,
          opacity: 0.88,
          fillColor: '#082be8',
          fillOpacity: 0.62,
          className: 'inundation-surface inundation-main'
        }).bindPopup(buildFloodPopup(maxDepth, '模拟洪水淹没范围'), { className: 'topic-popup-shell' })
      )
    }

    if (deepEnvelope) {
      layers.flood.addLayer(
        L.polygon(deepEnvelope, {
          color: '#4fd9ff',
          weight: 1.2,
          opacity: 0.74,
          fillColor: '#009dff',
          fillOpacity: 0.24,
          className: 'inundation-surface inundation-deep'
        }).bindPopup(buildFloodPopup(maxDepth, '深水影响区'), { className: 'topic-popup-shell' })
      )
    }

    if (extremeEnvelope) {
      layers.flood.addLayer(
        L.polygon(extremeEnvelope, {
          color: '#ff5570',
          weight: 1.2,
          opacity: 0.76,
          fillColor: '#ff3d5a',
          fillOpacity: 0.18,
          className: 'inundation-surface inundation-extreme'
        }).bindPopup(buildFloodPopup(maxDepth, '极高风险核心区'), { className: 'topic-popup-shell' })
      )
    }

    hotSpots.forEach((point) => {
        layers.flood.addLayer(
          L.circleMarker([point.lat, point.lng], {
            radius: point.risk_level === 'extreme' ? 4.8 : 3.6,
            color: RISK_COPY[point.risk_level].color,
            weight: 1,
            opacity: 0.86,
            fillColor: RISK_COPY[point.risk_level].color,
            fillOpacity: 0.8,
            className: 'risk-dot'
          }).bindPopup(buildFloodPopup(point.depth, RISK_COPY[point.risk_level].label), { className: 'topic-popup-shell' })
        )
      })
  }, [floodRenderState, maxDepth])

  useEffect(() => {
    const layers = layersRef.current
    if (!layers) {
      return
    }

    layers.velocity.clearLayers()
    velocitySegments.forEach(([start, end]) => {
        layers.velocity.addLayer(
          L.polyline(
            [start, end],
            {
              color: '#d7f9ff',
              weight: 1.5,
              opacity: 0.62,
              dashArray: '5, 6',
              className: 'velocity-thread'
            }
          )
        )
      })
  }, [velocitySegments])

  useEffect(() => {
    const layers = layersRef.current
    if (!layers) {
      return
    }

    layers.sensors.clearLayers()

    sensors.forEach((sensor) => {
      const status = SENSOR_STATUS_COPY[sensor.status]
      const isSelected = sensor.station_id === selectedStationId
      const icon = L.divIcon({
        className: `topic-sensor-marker ${isSelected ? 'is-selected' : ''}`,
        html: `<i style="background:${status.color}; box-shadow:0 0 16px ${status.color};"></i><span>${sensor.name}</span>`,
        iconSize: [150, 30],
        iconAnchor: [12, 15]
      })
      const marker = L.marker([sensor.lat, sensor.lng], { icon })
      marker.bindPopup(buildSensorPopup(sensor), { className: 'topic-popup-shell' })
      marker.on('click', () => onStationSelect?.(sensor))
      layers.sensors.addLayer(marker)
    })
  }, [onStationSelect, selectedStationId, sensors])

  useEffect(() => {
    const layers = layersRef.current
    if (!layers) {
      return
    }

    layers.keyPoints.clearLayers()

    keyPoints.forEach((point) => {
      if (typeof point.lat !== 'number' || typeof point.lng !== 'number') {
        return
      }
      const isSelected = point.id === selectedKeyPointId
      const risk = RISK_COPY[point.risk_level]
      const icon = L.divIcon({
        className: `topic-keypoint-marker ${isSelected ? 'is-selected' : ''}`,
        html: `<i style="border-color:${risk.color}; color:${risk.color};">${point.type.slice(0, 1).toUpperCase()}</i><span>${point.name}</span>`,
        iconSize: [142, 30],
        iconAnchor: [12, 15]
      })
      const marker = L.marker([point.lat, point.lng], { icon })
      marker.bindPopup(buildKeyPointPopup(point), { className: 'topic-popup-shell' })
      marker.on('click', () => onKeyPointSelect?.(point))
      layers.keyPoints.addLayer(marker)
    })
  }, [keyPoints, onKeyPointSelect, selectedKeyPointId])

  useEffect(() => {
    const layers = layersRef.current
    if (!layers) {
      return
    }

    layers.routes.clearLayers()
    if (!showRoutes) {
      return
    }

    evacuationRoutes.forEach((route) => {
      const style = ROUTE_STATUS_COPY[route.status]
      const isSelected = route.id === selectedRouteId
      layers.routes.addLayer(
        L.polyline(
          [
            [route.origin.lat, route.origin.lng],
            ...route.waypoints.map((waypoint) => [waypoint.lat, waypoint.lng] as LatLng),
            [route.destination.lat, route.destination.lng]
          ],
          {
            color: style.color,
            weight: isSelected ? 4 : 2.4,
            opacity: isSelected ? 0.96 : 0.62,
            dashArray: style.dashArray,
            className: 'evacuation-route-line'
          }
        ).bindTooltip(`${route.origin.name} → ${route.destination.name}`, { sticky: true, className: 'topic-tooltip' })
      )
    })
  }, [evacuationRoutes, selectedRouteId, showRoutes])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !selectedStationId) {
      return
    }
    const station = sensors.find((item) => item.station_id === selectedStationId)
    if (station) {
      map.flyTo([station.lat, station.lng], Math.max(map.getZoom(), 12.5), { duration: 0.55 })
    }
  }, [selectedStationId, sensors])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !selectedKeyPointId) {
      return
    }
    const point = keyPoints.find((item) => item.id === selectedKeyPointId && typeof item.lat === 'number' && typeof item.lng === 'number')
    if (point && typeof point.lat === 'number' && typeof point.lng === 'number') {
      map.flyTo([point.lat, point.lng], Math.max(map.getZoom(), 12.5), { duration: 0.55 })
    }
  }, [keyPoints, selectedKeyPointId])

  useEffect(() => {
    return () => {
      if (scaleControlRef.current && mapRef.current) {
        scaleControlRef.current.remove()
      }
      if (mapRef.current) {
        mapRef.current.remove()
        mapRef.current = null
        layersRef.current = null
      }
    }
  }, [])

  return (
    <div className="flood-map-container">
      <div ref={mapContainerRef} className="flood-leaflet-host" />

      <div className="topic-map-title">
        <span>FLOOD INUNDATION THEMATIC MAP</span>
        <strong>{context.title}</strong>
        <em>{context.subtitle}</em>
      </div>

      <div className="topic-map-compass" aria-label="north arrow">
        <span>N</span>
        <i />
      </div>

      <div className="topic-map-stats">
        <div>
          <span>淹没面积</span>
          <strong>{floodedAreaLabel}</strong>
        </div>
        <div>
          <span>最大水深</span>
          <strong>{maxDepth.toFixed(2)} m</strong>
        </div>
      </div>

      <div className="topic-map-legend">
        <strong>图例</strong>
        <span><i className="legend-flood" />模拟淹没范围</span>
        <span><i className="legend-deep" />深水影响区</span>
        <span><i className="legend-river" />河道 / 水系</span>
        <span><i className="legend-road" />主要道路</span>
        <span><i className="legend-point" />监测点 / 关键对象</span>
      </div>

      <div className="topic-map-source">{context.source}</div>
    </div>
  )
}

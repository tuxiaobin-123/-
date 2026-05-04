import axios, { AxiosError, AxiosInstance } from 'axios'
import {
  CaseProfile,
  EvacuationRoute,
  FloodGridPoint,
  PredictionData,
  RealDataStatus,
  RiskZoneCollection,
  RiskStats,
  SensorStation,
  SimulationParams,
  SimulationStatus,
  StationHistory,
  SystemInfo
} from '../types'

type BackendFloodGridResponse = {
  points: Array<{
    lat: number
    lng: number
    depth: number
    velocity_u: number
    velocity_v: number
    flooded: boolean
  }>
}

type BackendSensorsResponse = {
  stations: Array<{
    station_id: string
    name: string
    lat: number
    lng: number
    water_level: number
    rainfall: number
    flow_rate: number
    battery: number
    signal_quality: number
    last_update: string
  }>
}

type BackendPredictionResponse = {
  points: Array<{
    timestamp: string
    predicted_level: number
    confidence_upper: number
    confidence_lower: number
  }>
  statistics: {
    risk_trend?: string[]
  }
}

type BackendRiskAssessmentResponse = {
  global_risk_level: 'low' | 'medium' | 'high' | 'critical'
  risk_score: number
  statistics: {
    total_flooded_area_km2: number
    estimated_affected_population: number
  }
  zones: Array<{ id: string; risk_level: string; area_km2: number; population: number }>
  affected_key_points: Array<{
    id: string
    name: string
    type: string
    risk_level: 'low' | 'medium' | 'high' | 'critical'
    water_depth: number
  }>
}

type BackendRiskZonesResponse = {
  type: 'FeatureCollection'
  features: Array<{
    type: 'Feature'
    properties: {
      risk_level: 'low' | 'medium' | 'high' | 'critical'
      color: string
      area_km2: number
    }
    geometry: {
      type: 'Polygon'
      coordinates: number[][][]
    }
  }>
}

type BackendEvacuationRoutesResponse = {
  routes: Array<{
    route_id: number
    origin: string
    destination: string
    waypoints: Array<{ lat: number; lng: number }>
    distance_km: number
    risk_score: number
    estimated_minutes: number
    status: 'safe' | 'warning' | 'dangerous'
  }>
}

type BackendSystemInfo = {
  app_name: string
  version: string
  uptime_seconds: number
  current_time: string
  model_state: string
}

type BackendEarlyWarningResponse = {
  should_warn: boolean
  warning_level: 'none' | 'yellow' | 'orange' | 'red'
  affected_population: number
  critical_area_km2: number
  affected_key_points: number
  message: string
}

const normalizeRiskLevel = (level: string): 'low' | 'medium' | 'high' | 'extreme' => {
  if (level === 'critical') {
    return 'extreme'
  }
  if (level === 'low' || level === 'medium' || level === 'high') {
    return level
  }
  return 'low'
}

const getSensorStatus = (waterLevel: number): SensorStation['status'] => {
  if (waterLevel > 200) {
    if (waterLevel >= 275) {
      return 'danger'
    }
    if (waterLevel >= 270) {
      return 'warning'
    }
    return 'normal'
  }

  if (waterLevel > 80) {
    if (waterLevel >= 120) {
      return 'danger'
    }
    if (waterLevel >= 112) {
      return 'warning'
    }
    return 'normal'
  }

  if (waterLevel >= 55) {
    return 'danger'
  }
  if (waterLevel >= 50) {
    return 'warning'
  }
  return 'normal'
}

const getFloodPointRisk = (depth: number): FloodGridPoint['risk_level'] => {
  if (depth > 2) {
    return 'extreme'
  }
  if (depth > 1) {
    return 'high'
  }
  if (depth > 0.5) {
    return 'medium'
  }
  return 'low'
}

const apiClient: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

apiClient.interceptors.request.use(
  (config) => config,
  (error: AxiosError) => Promise.reject(error)
)

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response) {
      console.error(`API Error ${error.response.status}:`, error.response.data)
    } else if (error.request) {
      console.error('No response received:', error.request)
    } else {
      console.error('Error:', error.message)
    }
    return Promise.reject(error)
  }
)

export const getFloodGrid = async (): Promise<FloodGridPoint[]> => {
  const response = await apiClient.get<BackendFloodGridResponse>('/flood/grid')
  return response.data.points.map((point) => ({
    lat: point.lat,
    lng: point.lng,
    depth: point.depth,
    vel_u: point.velocity_u,
    vel_v: point.velocity_v,
    flooded: point.flooded,
    risk_level: getFloodPointRisk(point.depth)
  }))
}

export const getSimulationStatus = async (): Promise<SimulationStatus> => {
  const response = await apiClient.get<SimulationStatus>('/flood/status')
  return response.data
}

export const getActiveCase = async (): Promise<CaseProfile> => {
  const response = await apiClient.get<CaseProfile>('/flood/case')
  return response.data
}

export const getRealDataStatus = async (): Promise<RealDataStatus> => {
  const response = await apiClient.get<RealDataStatus>('/flood/real-data/status')
  return response.data
}

export const startSimulation = async (
  params: SimulationParams
): Promise<{
  status: string
  total_steps: number
  duration_hours: number
  rainfall_mm_h: number
  upstream_inflow_m3s: number
  gate_release_m3s: number
  downstream_level_m: number
  reservoir_level_m: number
  dam_name: string
}> => {
  const response = await apiClient.post('/flood/simulate', {
    rainfall_mm_h: params.rainfall_intensity,
    upstream_m3s: params.upstream_inflow,
    duration_hours: params.duration_hours,
    gate_release_m3s: params.gate_release,
    downstream_level_m: params.downstream_level,
    reservoir_level_m: params.reservoir_level
  })
  return response.data
}

export const stepSimulation = async (): Promise<{
  current_step: number
  total_steps: number
  is_complete: boolean
}> => {
  const response = await apiClient.post('/flood/simulate/step')
  return response.data
}

export const resetSimulation = async (): Promise<{
  status: string
  dam_name: string
}> => {
  const response = await apiClient.post('/flood/simulate/reset')
  return response.data
}

export const startHistoricalReplay = async (): Promise<{
  status: string
  total_steps: number
  duration_hours: number
  rainfall_mm_h: number
  upstream_inflow_m3s: number
  gate_release_m3s: number
  downstream_level_m: number
  reservoir_level_m: number
  dam_name: string
  history_label: string
}> => {
  const response = await apiClient.post('/flood/simulate/historical/oroville-2017')
  return response.data
}

export const getFloodHistory = async (stationId: string, hours: number = 24): Promise<StationHistory> => {
  const response = await apiClient.get<StationHistory>(`/flood/history/${stationId}`, {
    params: { hours }
  })
  return response.data
}

export const getSensorData = async (): Promise<SensorStation[]> => {
  const response = await apiClient.get<BackendSensorsResponse>('/sensors/realtime')
  return response.data.stations.map((station) => ({
    ...station,
    status: getSensorStatus(station.water_level)
  }))
}

export const getSensorHistory = async (
  stationId: string,
  hours: number = 24
): Promise<{
  station_id: string
  timestamps: string[]
  water_levels: number[]
  rainfall: number[]
  flow_rates: number[]
}> => {
  const response = await apiClient.get(`/sensors/history/${stationId}`, {
    params: { hours }
  })
  return response.data
}

export const getPrediction = async (stationId: string = 'urban_a', hours: number = 24): Promise<PredictionData> => {
  const response = await apiClient.get<BackendPredictionResponse>('/predict/flood', {
    params: {
      station_id: stationId,
      hours
    }
  })
  return {
    timestamps: response.data.points.map((point) => point.timestamp),
    predicted_levels: response.data.points.map((point) => point.predicted_level),
    confidence_upper: response.data.points.map((point) => point.confidence_upper),
    confidence_lower: response.data.points.map((point) => point.confidence_lower),
    risk_trend: (response.data.statistics.risk_trend || []).map(normalizeRiskLevel)
  }
}

export const getRiskTrend = async (
  hours: number = 24
): Promise<{
  timestamps: string[]
  zones: Array<{
    zone_name: string
    risk_levels: string[]
  }>
}> => {
  const response = await apiClient.get('/predict/risk-trend', {
    params: { hours }
  })
  return response.data
}

export const getRiskAssessment = async (): Promise<RiskStats> => {
  const [assessmentResponse, warningResponse] = await Promise.all([
    apiClient.get<BackendRiskAssessmentResponse>('/risk/assessment'),
    apiClient.get<BackendEarlyWarningResponse>('/risk/early-warning')
  ])
  const response = assessmentResponse.data
  const warning = warningResponse.data
  const zoneRiskBreakdown = response.zones.reduce<NonNullable<RiskStats['risk_breakdown']>>((accumulator, zone) => {
    accumulator[zone.id] = {
      level: normalizeRiskLevel(zone.risk_level),
      population: zone.population,
      area_km2: zone.area_km2
    }
    return accumulator
  }, {})

  return {
    overall_level: normalizeRiskLevel(response.global_risk_level),
    risk_score: response.risk_score,
    affected_area_km2: response.statistics.total_flooded_area_km2,
    affected_population: response.statistics.estimated_affected_population,
    high_risk_zones: response.zones.filter((zone) => ['high', 'critical'].includes(zone.risk_level)).length,
    evacuation_recommended: ['high', 'critical'].includes(response.global_risk_level),
    warning_level: warning.warning_level,
    warning_message: warning.message,
    affected_key_points: response.affected_key_points.map((point) => ({
      ...point,
      risk_level: normalizeRiskLevel(point.risk_level)
    })),
    risk_breakdown: zoneRiskBreakdown
  }
}

export const getRiskZones = async (): Promise<RiskZoneCollection> => {
  const response = await apiClient.get<BackendRiskZonesResponse>('/risk/zones')
  return {
    type: 'FeatureCollection',
    features: response.data.features.map((feature) => ({
      type: 'Feature',
      properties: {
        ...feature.properties,
        risk_level: normalizeRiskLevel(feature.properties.risk_level)
      },
      geometry: feature.geometry
    }))
  }
}

export const getEvacuationRoutes = async (): Promise<EvacuationRoute[]> => {
  const response = await apiClient.get<BackendEvacuationRoutesResponse>('/risk/evacuation/routes')
  return response.data.routes.map((route) => ({
    id: String(route.route_id),
    origin: {
      lat: route.waypoints[0]?.lat ?? 0,
      lng: route.waypoints[0]?.lng ?? 0,
      name: route.origin
    },
    destination: {
      lat: route.waypoints[route.waypoints.length - 1]?.lat ?? 0,
      lng: route.waypoints[route.waypoints.length - 1]?.lng ?? 0,
      name: route.destination
    },
    waypoints: route.waypoints.map((waypoint) => ({ lat: waypoint.lat, lng: waypoint.lng })),
    risk_score: route.risk_score,
    distance: route.distance_km,
    estimated_minutes: route.estimated_minutes,
    status: route.status === 'warning' ? 'caution' : route.status
  }))
}

export const getSystemInfo = async (): Promise<SystemInfo> => {
  const response = await apiClient.get<BackendSystemInfo>('/system/info')
  return {
    status: response.data.model_state === 'running' ? 'running' : 'error',
    simulation_running: response.data.model_state === 'running',
    current_time: response.data.current_time,
    uptime_seconds: response.data.uptime_seconds,
    data_points_processed: 0
  }
}

export default apiClient

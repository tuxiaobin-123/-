export interface FloodGridPoint {
  lat: number
  lng: number
  depth: number
  vel_u: number
  vel_v: number
  flooded: boolean
  risk_level: 'low' | 'medium' | 'high' | 'extreme'
}

export interface RiskZoneFeature {
  type: 'Feature'
  properties: {
    risk_level: 'low' | 'medium' | 'high' | 'extreme'
    color: string
    area_km2: number
  }
  geometry: {
    type: 'Polygon'
    coordinates: number[][][]
  }
}

export interface RiskZoneCollection {
  type: 'FeatureCollection'
  features: RiskZoneFeature[]
}

export interface SensorStation {
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
  status: 'normal' | 'warning' | 'danger'
}

export interface PredictionData {
  timestamps: string[]
  predicted_levels: number[]
  confidence_upper: number[]
  confidence_lower: number[]
  risk_trend: string[]
}

export interface EvacuationRoute {
  id: string
  origin: {
    lat: number
    lng: number
    name: string
  }
  destination: {
    lat: number
    lng: number
    name: string
  }
  waypoints: Array<{ lat: number; lng: number }>
  risk_score: number
  distance: number
  estimated_minutes: number
  status: 'safe' | 'caution' | 'dangerous'
}

export interface RiskStats {
  overall_level: 'low' | 'medium' | 'high' | 'extreme'
  risk_score: number
  affected_area_km2: number
  affected_population: number
  high_risk_zones: number
  evacuation_recommended: boolean
  warning_level?: 'none' | 'yellow' | 'orange' | 'red'
  warning_message?: string
  affected_key_points?: AffectedKeyPoint[]
  risk_breakdown?: {
    [zone: string]: {
      level: 'low' | 'medium' | 'high' | 'extreme'
      population: number
      area_km2: number
    }
  }
}

export interface AffectedKeyPoint {
  id: string
  name: string
  lat?: number
  lng?: number
  type: string
  risk_level: 'low' | 'medium' | 'high' | 'extreme'
  water_depth: number
}

export interface WSMessage {
  type: 'update' | 'alert' | 'heartbeat'
  timestamp: string
  data?: {
    water_level?: number
    rainfall?: number
    risk_level?: string
    alert_message?: string
    station_id?: string
  }
}

export interface SystemInfo {
  status: 'running' | 'stopped' | 'error'
  simulation_running: boolean
  current_time: string
  uptime_seconds: number
  data_points_processed: number
}

export interface SimulationParams {
  rainfall_intensity: number
  upstream_inflow: number
  duration_hours: number
  gate_release?: number
  downstream_level?: number
  reservoir_level?: number
}

export interface SimulationStatus {
  is_running: boolean
  current_time_step: number
  total_steps: number
  elapsed_minutes: number
  rainfall_rate: number
  upstream_inflow: number
  gate_release: number
  downstream_level: number
  reservoir_level: number
  progress_percent: number
  dam_name: string
}

export interface StationHistoryPoint {
  timestamp: string
  water_level: number
  rainfall: number
  flow_rate: number
}

export interface StationHistory {
  station_id: string
  hours: number
  entries: Array<{
    timestamp: string
    time_step: number
    station_id: string
    water_level: number
    rainfall: number
    flow_rate: number
  }>
}

export interface CaseProfile {
  case_id: string
  dam: {
    name: string
    owner?: string
    river?: string
    lat?: number
    lng?: number
    crest_elevation_m?: number
    normal_reservoir_level_m?: number
  }
  grid: {
    rows: number
    cols: number
    base_lat: number
    base_lng: number
    dx_deg: number
    dy_deg: number
  }
  sensor_stations: Record<
    string,
    {
      name: string
      lat: number
      lng: number
      type: string
      source?: string
    }
  >
  key_points: Record<
    string,
    {
      name: string
      lat: number
      lng: number
      type: string
      population?: number
      capacity?: number
      priority?: number
    }
  >
  dem_control_points: Array<{
    id: string
    lat: number
    lng: number
    elevation_m: number
    source: string
  }>
  dem_grid_cache?: {
    path?: string
    enabled: boolean
    mode?: string
  }
  data_sources: string[]
}

export interface ModelCapabilities {
  focus: string
  title: string
  model_runtime: {
    current_engine: string
    baseline_solver: string
    accelerated_candidate: string
    ai_prediction: string
    runtime_note: string
  }
  innovation_points: {
    physics_ai_fusion: {
      label: string
      evidence: string[]
    }
    dam_boundary_conditions: {
      label: string
      evidence: string[]
    }
    monitor_simulate_warn_respond_loop: {
      label: string
      evidence: string[]
    }
  }
  boundary_conditions: Record<string, string | number | number[]>
  decision_loop: string[]
  case_evidence: {
    case_id: string
    dam_name: string
    river?: string
    sensor_count: number
    key_object_count: number
    data_sources: string[]
  }
}

export interface RuntimeBenchmark {
  requested_engine: string
  actual_engine: string
  grid: {
    rows: number
    cols: number
    cells: number
  }
  steps: number
  elapsed_ms: number
  ms_per_step: number
  torch_available: boolean
}

export interface ToceBenchmark {
  benchmark: string
  status: 'scored' | 'data_not_loaded'
  saved_to?: string
  expected_file?: string
  required_columns?: string[]
  station_count?: number
  metrics?: {
    peak_depth_rmse_m: {
      this_model: number
      mike21: number
    }
    arrival_time_rmse_s: {
      this_model: number
      mike21: number
    }
  }
  rows?: Array<Record<string, string | number>>
}

export interface RealDataStatus {
  case_id: string
  checked_at: string
  dem: {
    status: string
    path?: string
    mode: string
  }
  usgs: {
    status: 'live' | 'cached' | 'unavailable' | 'offline_seed'
    fetched_at: string
    endpoint: string
    last_error?: string
    series: Array<{
      provider: string
      station_id: string
      station_name: string
      parameter_code: string
      parameter_name: string
      count: number
      latest_time: string | null
      latest_value: number | null
      min: number | null
      max: number | null
    }>
  }
  historical_event: {
    event_id: string
    name: string
    period: {
      start: string
      end: string
    }
    known_milestones: Array<{
      time: string
      label: string
    }>
    calibration_targets: string[]
    limitations: string[]
    starter_simulation: {
      rainfall_mm_h: number
      upstream_m3s: number
      gate_release_m3s: number
      downstream_level_m: number
      reservoir_level_m: number
      duration_hours: number
    }
    milestone_count: number
    calibration_target_count: number
  }
  next_steps: string[]
}

export interface ApiResponse<T> {
  code: number
  message: string
  data: T
  timestamp: string
}

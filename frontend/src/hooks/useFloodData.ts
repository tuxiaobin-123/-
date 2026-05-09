import { startTransition, useCallback, useEffect, useRef, useState } from 'react'
import {
  CaseProfile,
  EvacuationRoute,
  FloodGridPoint,
  ModelCapabilities,
  PredictionData,
  RealDataStatus,
  RiskStats,
  RiskZoneCollection,
  SensorStation,
  SimulationStatus
} from '../types'
import {
  getActiveCase,
  getEvacuationRoutes,
  getFloodGrid,
  getModelCapabilities,
  getPrediction,
  getRealDataStatus,
  getRiskAssessment,
  getRiskZones,
  getSensorData,
  getSimulationStatus
} from '../api/client'

interface UseFloodDataReturn {
  floodGrid: FloodGridPoint[]
  sensors: SensorStation[]
  prediction: PredictionData | null
  riskStats: RiskStats | null
  riskZones: RiskZoneCollection | null
  evacuationRoutes: EvacuationRoute[]
  simulationStatus: SimulationStatus | null
  caseProfile: CaseProfile | null
  modelCapabilities: ModelCapabilities | null
  realDataStatus: RealDataStatus | null
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
  refetchRealtime: () => Promise<void>
}

export const useFloodData = (selectedStationId?: string | null): UseFloodDataReturn => {
  const [floodGrid, setFloodGrid] = useState<FloodGridPoint[]>([])
  const [sensors, setSensors] = useState<SensorStation[]>([])
  const [prediction, setPrediction] = useState<PredictionData | null>(null)
  const [riskStats, setRiskStats] = useState<RiskStats | null>(null)
  const [riskZones, setRiskZones] = useState<RiskZoneCollection | null>(null)
  const [evacuationRoutes, setEvacuationRoutes] = useState<EvacuationRoute[]>([])
  const [simulationStatus, setSimulationStatus] = useState<SimulationStatus | null>(null)
  const [caseProfile, setCaseProfile] = useState<CaseProfile | null>(null)
  const [modelCapabilities, setModelCapabilities] = useState<ModelCapabilities | null>(null)
  const [realDataStatus, setRealDataStatus] = useState<RealDataStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const initializedRef = useRef(false)
  const realtimeRequestInFlightRef = useRef(false)
  const staticLayerRefreshAtRef = useRef(0)

  const fetchRealtimeData = useCallback(async (options: { includeStaticLayers?: boolean } = {}) => {
    if (realtimeRequestInFlightRef.current) {
      return
    }

    realtimeRequestInFlightRef.current = true
    try {
      const now = Date.now()
      const staticLayerInterval = simulationStatus?.is_running ? 6000 : 15000
      const shouldRefreshStaticLayers =
        options.includeStaticLayers || now - staticLayerRefreshAtRef.current > staticLayerInterval

      const [gridData, sensorData, statusData, riskData] = await Promise.all([
        getFloodGrid(),
        getSensorData(),
        getSimulationStatus(),
        getRiskAssessment()
      ])
      const [routesData, zonesData] = shouldRefreshStaticLayers
        ? await Promise.all([getEvacuationRoutes(), getRiskZones()])
        : [null, null]

      if (shouldRefreshStaticLayers) {
        staticLayerRefreshAtRef.current = now
      }

      startTransition(() => {
        setFloodGrid(gridData)
        setSensors(sensorData)
        setSimulationStatus(statusData)
        setRiskStats(riskData)
        if (routesData) {
          setEvacuationRoutes(routesData)
        }
        if (zonesData) {
          setRiskZones(zonesData)
        }
        setError(null)
      })
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '获取实时数据失败'
      setError(errorMsg)
      console.error('Failed to fetch realtime data:', err)
    } finally {
      realtimeRequestInFlightRef.current = false
    }
  }, [simulationStatus?.is_running])

  const fetchInitialData = useCallback(async () => {
    try {
      const [caseData, capabilityData, realStatus, predData] = await Promise.all([
        getActiveCase(),
        getModelCapabilities(),
        getRealDataStatus(),
        getPrediction(selectedStationId || 'usgs_11407000')
      ])
      startTransition(() => {
        setCaseProfile(caseData)
        setModelCapabilities(capabilityData)
        setRealDataStatus(realStatus)
        setPrediction(predData)
      })
    } catch (err) {
      console.error('Failed to fetch initial data:', err)
    }
  }, [selectedStationId])

  const refetch = useCallback(async () => {
    setLoading(true)
    try {
      await fetchRealtimeData({ includeStaticLayers: true })

      if (!initializedRef.current) {
        await fetchInitialData()
        initializedRef.current = true
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '数据加载失败'
      setError(errorMsg)
    } finally {
      setLoading(false)
    }
  }, [fetchInitialData, fetchRealtimeData])

  useEffect(() => {
    void refetch()
  }, [refetch])

  useEffect(() => {
    let cancelled = false

    const refreshPrediction = async () => {
      try {
        const predData = await getPrediction(selectedStationId || 'usgs_11407000')
        if (!cancelled) {
          setPrediction(predData)
        }
      } catch (err) {
        console.error('Failed to refresh focused prediction:', err)
      }
    }

    if (initializedRef.current) {
      void refreshPrediction()
    }

    return () => {
      cancelled = true
    }
  }, [selectedStationId])

  useEffect(() => {
    const poll = () => {
      void fetchRealtimeData()
    }

    pollIntervalRef.current = setInterval(poll, simulationStatus?.is_running ? 1500 : 5000)

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
      }
    }
  }, [fetchRealtimeData, simulationStatus?.is_running])

  const refetchRealtime = useCallback(() => fetchRealtimeData({ includeStaticLayers: true }), [fetchRealtimeData])

  return {
    floodGrid,
    sensors,
    prediction,
    riskStats,
    riskZones,
    evacuationRoutes,
    simulationStatus,
    caseProfile,
    modelCapabilities,
    realDataStatus,
    loading,
    error,
    refetch,
    refetchRealtime
  }
}

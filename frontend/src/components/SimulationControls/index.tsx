import React, { useCallback } from 'react'
import { DeleteOutlined, PlayCircleOutlined } from '@ant-design/icons'
import { Button, Progress, Slider, Space, message } from 'antd'
import { SimulationParams, SimulationStatus } from '../../types'

interface ScenarioPreset {
  key: string
  name: string
  description: string
  params: SimulationParams
}

interface SimulationControlsProps {
  simulationRunning: boolean
  rainfallIntensity: number
  upstreamInflow: number
  simulationDuration: number
  gateRelease: number
  downstreamLevel: number
  reservoirLevel: number
  simulationStatus: SimulationStatus | null
  scenarioPresets: ScenarioPreset[]
  activeScenarioKey?: string | null
  launchingScenarioKey?: string | null
  onRainfallChange: (value: number) => void
  onUpstreamChange: (value: number) => void
  onDurationChange: (value: number) => void
  onGateReleaseChange: (value: number) => void
  onDownstreamLevelChange: (value: number) => void
  onReservoirLevelChange: (value: number) => void
  onSimulationStarted: () => Promise<{ total_steps: number; dam_name: string }>
  onScenarioLaunch: (params: SimulationParams) => Promise<{ total_steps: number; dam_name: string }>
  onReset: () => Promise<void>
}

export const SimulationControls: React.FC<SimulationControlsProps> = ({
  simulationRunning,
  rainfallIntensity,
  upstreamInflow,
  simulationDuration,
  gateRelease,
  downstreamLevel,
  reservoirLevel,
  simulationStatus,
  scenarioPresets,
  activeScenarioKey,
  launchingScenarioKey,
  onRainfallChange,
  onUpstreamChange,
  onDurationChange,
  onGateReleaseChange,
  onDownstreamLevelChange,
  onReservoirLevelChange,
  onSimulationStarted,
  onScenarioLaunch,
  onReset
}) => {
  const handleStart = useCallback(async () => {
    try {
      const result = await onSimulationStarted()
      message.success(`${result.dam_name} 模拟已启动，共 ${result.total_steps} 步`)
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '启动模拟失败'
      message.error(errorMsg)
    }
  }, [onSimulationStarted])

  const handleReset = useCallback(async () => {
    try {
      await onReset()
      message.info('模拟参数已重置')
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '重置模拟失败'
      message.error(errorMsg)
    }
  }, [onReset])

  const handleScenarioLaunch = useCallback(
    async (params: SimulationParams, name: string) => {
      try {
        const result = await onScenarioLaunch(params)
        message.success(`${name}已启动，${result.dam_name} 正在按预设工况推演`)
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : `${name}启动失败`
        message.error(errorMsg)
      }
    },
    [onScenarioLaunch]
  )

  return (
    <>
      <div className="control-title">坝区模拟控制</div>

      <div className="control-group">
        <label>一键情景推演</label>
        <div className="scenario-grid">
          {scenarioPresets.map((preset) => (
            <div key={preset.key} className={`scenario-card ${activeScenarioKey === preset.key ? 'is-active' : ''}`}>
              <div className="scenario-card-head">
                <strong>{preset.name}</strong>
                <Button
                  size="small"
                  type="primary"
                  ghost
                  loading={launchingScenarioKey === preset.key}
                  onClick={() => void handleScenarioLaunch(preset.params, preset.name)}
                >
                  {activeScenarioKey === preset.key && simulationRunning ? '运行中' : simulationRunning ? '切换' : '运行'}
                </Button>
              </div>
              <div className="scenario-description">{preset.description}</div>
            </div>
          ))}
        </div>
      </div>

      <details className="advanced-controls">
        <summary>高级边界条件</summary>

        <div className="control-group">
          <label>降雨强度 (mm/h)</label>
          <div className="slider-container">
            <Slider min={0} max={200} value={rainfallIntensity} onChange={onRainfallChange} disabled={simulationRunning} />
            <span className="slider-value">{rainfallIntensity}</span>
          </div>
        </div>

        <div className="control-group">
          <label>上游来流 (m³/s)</label>
          <div className="slider-container">
            <Slider min={0} max={5000} step={100} value={upstreamInflow} onChange={onUpstreamChange} disabled={simulationRunning} />
            <span className="slider-value">{upstreamInflow}</span>
          </div>
        </div>

        <div className="control-group">
          <label>泄洪流量 (m³/s)</label>
          <div className="slider-container">
            <Slider min={0} max={4200} step={100} value={gateRelease} onChange={onGateReleaseChange} disabled={simulationRunning} />
            <span className="slider-value">{gateRelease}</span>
          </div>
        </div>

        <div className="control-group">
          <label>库区水位 (m)</label>
          <div className="slider-container">
            <Slider min={250} max={276} step={0.5} value={reservoirLevel} onChange={onReservoirLevelChange} disabled={simulationRunning} />
            <span className="slider-value">{reservoirLevel.toFixed(1)}</span>
          </div>
        </div>

        <div className="control-group">
          <label>下游控制水位 (m)</label>
          <div className="slider-container">
            <Slider min={40} max={60} step={0.5} value={downstreamLevel} onChange={onDownstreamLevelChange} disabled={simulationRunning} />
            <span className="slider-value">{downstreamLevel.toFixed(1)}</span>
          </div>
        </div>

        <div className="control-group">
          <label>模拟时长 (小时)</label>
          <div className="slider-container">
            <Slider min={1} max={72} value={simulationDuration} onChange={onDurationChange} disabled={simulationRunning} />
            <span className="slider-value">{simulationDuration}h</span>
          </div>
        </div>
      </details>

      {simulationStatus && (
        <div className="control-group">
          <label>{simulationStatus.dam_name} 运行状态</label>
          <Progress
            percent={Number(simulationStatus.progress_percent.toFixed(1))}
            status={simulationStatus.is_running ? 'active' : 'normal'}
            strokeColor="#38cfff"
            trailColor="rgba(84, 144, 184, 0.16)"
          />
          <div className="simulation-running">
            <span>步数 {simulationStatus.current_time_step} / {simulationStatus.total_steps}</span>
            <span>历时 {simulationStatus.elapsed_minutes.toFixed(1)} 分钟</span>
          </div>
        </div>
      )}

      <Space className="control-buttons">
        <Button
          type="primary"
          icon={<PlayCircleOutlined />}
          onClick={handleStart}
          loading={simulationRunning}
          size="large"
          className="start-btn"
        >
          启动模拟
        </Button>
        <Button icon={<DeleteOutlined />} onClick={() => void handleReset()} className="reset-btn">
          重置
        </Button>
      </Space>

      {simulationRunning && <div className="simulation-running">模型正在自动推进，请观察地图、风险区和站点历史的联动变化。</div>}
    </>
  )
}

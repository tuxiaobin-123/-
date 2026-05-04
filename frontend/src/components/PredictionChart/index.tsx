import React, { useMemo, useState } from 'react'
import ReactEChartsCore from 'echarts-for-react/lib/core'
import * as echarts from 'echarts/core'
import { LineChart, HeatmapChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, VisualMapComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { Tabs } from 'antd'
import { PredictionData, SensorStation, StationHistory } from '../../types'
import './PredictionChart.css'

echarts.use([LineChart, HeatmapChart, GridComponent, TooltipComponent, VisualMapComponent, CanvasRenderer])

interface PredictionChartProps {
  prediction: PredictionData | null
  sensors: SensorStation[]
  stationHistory: StationHistory | null
  focusedStationName?: string | null
}

type TabKey = 'waterLevel' | 'riskTrend'

export const PredictionChart: React.FC<PredictionChartProps> = ({ prediction, sensors, stationHistory, focusedStationName }) => {
  const [activeTab, setActiveTab] = useState<TabKey>('waterLevel')

  const waterLevelChartOption = useMemo(() => {
    if (!prediction || prediction.timestamps.length === 0) {
      return {}
    }

    const timeLabels = prediction.timestamps.map((timestamp) => {
      const date = new Date(timestamp)
      return `${date.getHours()}:00`
    })

    const historyLevels = stationHistory?.entries.map((entry) => entry.water_level) ?? []
    const historyLabels =
      stationHistory?.entries.map((entry) =>
        new Date(entry.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
      ) ?? []

    return {
      color: ['#00d4ff', '#8ef3ff', '#ff735d', '#ff4d4f'],
      backgroundColor: 'transparent',
      textStyle: { fontFamily: 'Microsoft YaHei, sans-serif', color: '#a7bbcf' },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(10, 22, 40, 0.92)',
        borderColor: 'rgba(0, 212, 255, 0.3)',
        textStyle: { color: '#e0e0e0', fontSize: 12 }
      },
      grid: {
        left: '54px',
        right: '16px',
        top: '28px',
        bottom: '42px'
      },
      xAxis: [
        {
          type: 'category',
          data: timeLabels,
          boundaryGap: false,
          axisLine: { lineStyle: { color: 'rgba(0, 212, 255, 0.14)' } },
          axisLabel: { fontSize: 11, color: '#8ca6bc' }
        },
        {
          type: 'category',
          data: historyLabels,
          boundaryGap: false,
          show: false
        }
      ],
      yAxis: {
        type: 'value',
        name: '水位(m)',
        nameTextStyle: { color: '#8ca6bc', fontSize: 11 },
        axisLine: { lineStyle: { color: 'rgba(0, 212, 255, 0.14)' } },
        axisLabel: { fontSize: 11, color: '#8ca6bc' },
        splitLine: { show: true, lineStyle: { color: 'rgba(0, 212, 255, 0.08)', type: 'dashed' } }
      },
      series: [
        {
          name: '未来预测',
          type: 'line',
          data: prediction.predicted_levels,
          smooth: 0.36,
          itemStyle: { color: '#00d4ff' },
          lineStyle: { color: '#00d4ff', width: 3 },
          areaStyle: { color: 'rgba(0, 212, 255, 0.12)' },
          symbolSize: 6,
          showSymbol: false
        },
        {
          name: '置信上界',
          type: 'line',
          data: prediction.confidence_upper,
          smooth: 0.36,
          lineStyle: { color: 'rgba(137, 239, 255, 0.45)', type: 'dashed', width: 2 },
          symbol: 'none'
        },
        {
          name: '置信下界',
          type: 'line',
          data: prediction.confidence_lower,
          smooth: 0.36,
          lineStyle: { color: 'rgba(137, 239, 255, 0.28)', type: 'dashed', width: 2 },
          symbol: 'none'
        },
        {
          name: '实时回灌',
          type: 'line',
          xAxisIndex: 1,
          data: historyLevels,
          smooth: 0.24,
          lineStyle: { color: '#ff735d', width: 2.5 },
          itemStyle: { color: '#ff9a62' },
          showSymbol: historyLevels.length <= 12
        }
      ]
    }
  }, [prediction, stationHistory])

  const riskTrendChartOption = useMemo(() => {
    if (!prediction || sensors.length === 0) {
      return {}
    }

    const riskLevelMap: Record<string, number> = { low: 1, medium: 2, high: 3, extreme: 4 }
    const sensorNames = sensors.slice(0, 5).map((sensor) => sensor.name)
    const riskData: [number, number, number][] = []

    for (let i = 0; i < sensorNames.length; i += 1) {
      for (let j = 0; j < Math.min(prediction.risk_trend.length, 24); j += 1) {
        const riskValue = riskLevelMap[prediction.risk_trend[j]] || 1
        riskData.push([j, i, riskValue])
      }
    }

    return {
      backgroundColor: 'transparent',
      textStyle: { fontFamily: 'Microsoft YaHei, sans-serif', color: '#a7bbcf' },
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(10, 22, 40, 0.92)',
        borderColor: 'rgba(0, 212, 255, 0.3)',
        textStyle: { color: '#e0e0e0', fontSize: 12 }
      },
      grid: {
        left: '92px',
        right: '20px',
        top: '26px',
        bottom: '44px'
      },
      xAxis: {
        type: 'category',
        data: Array.from({ length: 24 }, (_, index) => `${index}:00`),
        axisLine: { lineStyle: { color: 'rgba(0, 212, 255, 0.14)' } },
        axisLabel: { fontSize: 10, color: '#8ca6bc', interval: 2 }
      },
      yAxis: {
        type: 'category',
        data: sensorNames,
        axisLine: { lineStyle: { color: 'rgba(0, 212, 255, 0.14)' } },
        axisLabel: { fontSize: 11, color: '#8ca6bc' }
      },
      visualMap: {
        min: 1,
        max: 4,
        inRange: { color: ['#00ff88', '#ffa500', '#ff7a45', '#ff4d4d'] },
        textStyle: { color: '#8ca6bc' },
        right: '18px'
      },
      series: [
        {
          name: '风险等级',
          type: 'heatmap',
          data: riskData,
          itemStyle: {
            borderColor: 'rgba(0, 212, 255, 0.1)',
            borderWidth: 1
          }
        }
      ]
    }
  }, [prediction, sensors])

  return (
    <div className="prediction-chart-container">
      <div style={{ marginBottom: 10, color: '#8ca6bc', fontSize: 12 }}>
        当前联动对象：<strong style={{ color: '#e6f7ff' }}>{focusedStationName || '默认监测站'}</strong>
      </div>
      <Tabs
        items={[
          {
            key: 'waterLevel',
            label: '预测与回灌',
            children: <ReactEChartsCore echarts={echarts} option={waterLevelChartOption} style={{ height: '280px' }} notMerge lazyUpdate />
          },
          {
            key: 'riskTrend',
            label: '风险热力',
            children: <ReactEChartsCore echarts={echarts} option={riskTrendChartOption} style={{ height: '280px' }} notMerge lazyUpdate />
          }
        ]}
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as TabKey)}
        className="prediction-tabs"
      />
    </div>
  )
}

<template>
  <div class="chart-container">
    <v-chart
      :option="chartOption"
      :style="{ width: '100%', height: '500px' }"
      autoresize
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { HeatmapChart as EHeatmapChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  VisualMapComponent,
  GridComponent
} from 'echarts/components'
import VChart from 'vue-echarts'

use([
  CanvasRenderer,
  EHeatmapChart,
  TitleComponent,
  TooltipComponent,
  VisualMapComponent,
  GridComponent
])

interface Props {
  data: Array<Record<string, any>>
  xAxis?: string
  yAxis?: string
  valueKey?: string
  title?: string
}

const props = withDefaults(defineProps<Props>(), {
  title: ''
})

const chartOption = computed(() => {
  if (!props.data || props.data.length === 0) {
    return {}
  }

  const firstRow = props.data[0] || {}
  const keys = Object.keys(firstRow)
  
  const xAxisKey = props.xAxis || keys[0] || ''
  const yAxisKey = props.yAxis || keys[1] || ''
  const valueKey = props.valueKey || keys[2] || keys[1] || ''

  // 고유한 x, y 값 추출
  const xValues = new Set<string>()
  const yValues = new Set<string>()
  
  props.data.forEach((row) => {
    const xVal = row[xAxisKey]
    const yVal = row[yAxisKey]
    if (xVal !== null && xVal !== undefined) {
      xValues.add(String(xVal))
    }
    if (yVal !== null && yVal !== undefined) {
      yValues.add(String(yVal))
    }
  })

  const xAxisData = Array.from(xValues).sort()
  const yAxisData = Array.from(yValues).sort()

  // 데이터를 맵으로 변환하여 집계
  const dataMap = new Map<string, number>()
  
  props.data.forEach((row) => {
    const xVal = String(row[xAxisKey] ?? '')
    const yVal = String(row[yAxisKey] ?? '')
    const key = `${xVal}|${yVal}`
    const value = typeof row[valueKey] === 'number' 
      ? row[valueKey] 
      : parseFloat(String(row[valueKey])) || 0
    
    if (dataMap.has(key)) {
      dataMap.set(key, dataMap.get(key)! + value)
    } else {
      dataMap.set(key, value)
    }
  })

  // 히트맵 데이터 형식으로 변환 [xIndex, yIndex, value]
  const heatmapData: Array<[number, number, number]> = []
  
  xAxisData.forEach((xVal, xIdx) => {
    yAxisData.forEach((yVal, yIdx) => {
      const key = `${xVal}|${yVal}`
      const value = dataMap.get(key) || 0
      heatmapData.push([xIdx, yIdx, value])
    })
  })

  // 최대값과 최소값 계산
  const values = heatmapData.map(item => item[2])
  const maxValue = Math.max(...values, 1)
  const minValue = Math.min(...values, 0)

  return {
    title: props.title
      ? {
          text: props.title,
          left: 'center',
          textStyle: {
            fontSize: 16,
            fontWeight: 'bold'
          }
        }
      : undefined,
    tooltip: {
      position: 'top',
      formatter: (params: any) => {
        const xVal = xAxisData[params.data[0]]
        const yVal = yAxisData[params.data[1]]
        const value = params.data[2]
        return `${xAxisKey}: ${xVal}<br/>${yAxisKey}: ${yVal}<br/>${valueKey}: ${value.toLocaleString()}`
      }
    },
    grid: {
      height: '60%',
      top: '15%',
      left: '15%',
      right: '10%'
    },
    xAxis: {
      type: 'category',
      data: xAxisData,
      splitArea: {
        show: true
      },
      axisLabel: {
        rotate: xAxisData.length > 10 ? 45 : 0,
        interval: 0,
        formatter: (value: string) => {
          if (value.length > 10) {
            return value.substring(0, 10) + '...'
          }
          return value
        }
      }
    },
    yAxis: {
      type: 'category',
      data: yAxisData,
      splitArea: {
        show: true
      },
      axisLabel: {
        formatter: (value: string) => {
          if (value.length > 10) {
            return value.substring(0, 10) + '...'
          }
          return value
        }
      }
    },
    visualMap: {
      min: minValue,
      max: maxValue,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: '5%',
      inRange: {
        color: ['#e0f2fe', '#0284c7', '#0c4a6e']
      },
      textStyle: {
        color: '#333'
      }
    },
    series: [
      {
        name: valueKey,
        type: 'heatmap',
        data: heatmapData,
        label: {
          show: true,
          formatter: (params: any) => {
            const value = params.data[2]
            return value > 0 ? value.toLocaleString() : ''
          },
          fontSize: 10
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
  }
})
</script>

<style scoped>
.chart-container {
  width: 100%;
  padding: 0rem;
}
</style>


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
import { ScatterChart as EScatterChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from 'echarts/components'
import VChart from 'vue-echarts'

use([
  CanvasRenderer,
  EScatterChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
])

interface Props {
  data: Array<Record<string, any>>
  xAxis?: string
  yAxis?: string
  sizeKey?: string
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
  const sizeKey = props.sizeKey

  // 산점도 데이터 추출
  const scatterData = props.data
    .map((row) => {
      const xVal = row[xAxisKey]
      const yVal = row[yAxisKey]
      const sizeVal = sizeKey ? row[sizeKey] : undefined

      const x = typeof xVal === 'number' ? xVal : parseFloat(String(xVal))
      const y = typeof yVal === 'number' ? yVal : parseFloat(String(yVal))
      const size = sizeVal !== undefined 
        ? (typeof sizeVal === 'number' ? sizeVal : parseFloat(String(sizeVal)) || 10)
        : 10

      if (isNaN(x) || isNaN(y)) {
        return null
      }

      return [x, y, size]
    })
    .filter((item): item is [number, number, number] => item !== null)

  if (scatterData.length === 0) {
    return {}
  }

  // 최대값과 최소값 계산
  const xValues = scatterData.map(item => item[0])
  const yValues = scatterData.map(item => item[1])
  const sizes = scatterData.map(item => item[2])

  const xMin = Math.min(...xValues)
  const xMax = Math.max(...xValues)
  const yMin = Math.min(...yValues)
  const yMax = Math.max(...yValues)
  const sizeMax = Math.max(...sizes, 10)
  const sizeMin = Math.min(...sizes, 1)

  // 크기 정규화 (10-50 범위)
  const normalizedData = scatterData.map(([x, y, size]) => {
    const normalizedSize = sizeMax !== sizeMin
      ? 10 + ((size - sizeMin) / (sizeMax - sizeMin)) * 40
      : 20
    return [x, y, normalizedSize]
  })

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
      trigger: 'item',
      formatter: (params: any) => {
        const data = params.data as [number, number, number]
        const sizeInfo = sizeKey ? `<br/>${sizeKey}: ${data[2].toLocaleString()}` : ''
        return `${xAxisKey}: ${data[0].toLocaleString()}<br/>${yAxisKey}: ${data[1].toLocaleString()}${sizeInfo}`
      }
    },
    grid: {
      left: '10%',
      right: '10%',
      bottom: '15%',
      top: props.title ? '15%' : '10%',
      containLabel: true
    },
    xAxis: {
      type: 'value',
      name: xAxisKey,
      nameLocation: 'middle',
      nameGap: 30,
      scale: true,
      axisLabel: {
        formatter: (value: number) => {
          if (value >= 1000000) {
            return (value / 1000000).toFixed(1) + 'M'
          }
          if (value >= 1000) {
            return (value / 1000).toFixed(1) + 'K'
          }
          return value.toString()
        }
      }
    },
    yAxis: {
      type: 'value',
      name: yAxisKey,
      nameLocation: 'middle',
      nameGap: 50,
      scale: true,
      axisLabel: {
        formatter: (value: number) => {
          if (value >= 1000000) {
            return (value / 1000000).toFixed(1) + 'M'
          }
          if (value >= 1000) {
            return (value / 1000).toFixed(1) + 'K'
          }
          return value.toString()
        }
      }
    },
    series: [
      {
        name: '데이터 포인트',
        type: 'scatter',
        data: normalizedData,
        symbolSize: (data: [number, number, number]) => data[2],
        itemStyle: {
          color: '#2563eb',
          opacity: 0.6
        },
        emphasis: {
          itemStyle: {
            color: '#1e40af',
            opacity: 0.8,
            borderColor: '#fff',
            borderWidth: 2
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


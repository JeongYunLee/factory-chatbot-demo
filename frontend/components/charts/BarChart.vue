<template>
  <div class="chart-container">
    <v-chart
      :option="chartOption"
      :style="{ width: '100%', height: '400px' }"
      autoresize
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart as EBarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from 'echarts/components'
import VChart from 'vue-echarts'

use([
  CanvasRenderer,
  EBarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
])

interface Props {
  data: Array<Record<string, any>>
  xAxis?: string
  yAxis?: string
  orientation?: 'horizontal' | 'vertical'
  title?: string
}

const props = withDefaults(defineProps<Props>(), {
  orientation: 'vertical',
  title: ''
})

const chartOption = computed(() => {
  if (!props.data || props.data.length === 0) {
    return {}
  }

  const xAxisKey = props.xAxis || Object.keys(props.data[0])[0]
  const yAxisKey = props.yAxis || Object.keys(props.data[0])[1]

  const xData = props.data.map((row) => {
    const value = row[xAxisKey]
    return value !== null && value !== undefined ? String(value) : ''
  })

  const yData = props.data.map((row) => {
    const value = row[yAxisKey]
    return typeof value === 'number' ? value : parseFloat(String(value)) || 0
  })

  const isHorizontal = props.orientation === 'horizontal'

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
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      },
      formatter: (params: any) => {
        const param = Array.isArray(params) ? params[0] : params
        return `${param.name}<br/>${param.seriesName}: ${param.value.toLocaleString()}`
      }
    },
    grid: {
      left: isHorizontal ? '20%' : '10%',
      right: '10%',
      bottom: isHorizontal ? '10%' : '15%',
      top: props.title ? '15%' : '10%',
      containLabel: true
    },
    xAxis: {
      type: isHorizontal ? 'value' : 'category',
      data: isHorizontal ? undefined : xData,
      axisLabel: {
        rotate: isHorizontal ? 0 : xData.length > 10 ? 45 : 0,
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
      type: isHorizontal ? 'category' : 'value',
      data: isHorizontal ? xData : undefined,
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
        name: yAxisKey,
        type: 'bar',
        data: yData,
        itemStyle: {
          color: '#2563eb'
        },
        label: {
          show: yData.length <= 20,
          position: isHorizontal ? 'right' : 'top',
          formatter: (params: any) => {
            return params.value.toLocaleString()
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
  padding: 1rem;
}
</style>


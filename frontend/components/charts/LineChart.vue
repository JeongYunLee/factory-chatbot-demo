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
import { LineChart as ELineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from 'echarts/components'
import VChart from 'vue-echarts'

use([
  CanvasRenderer,
  ELineChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
])

interface Props {
  data: Array<Record<string, any>>
  xAxis?: string
  yAxis?: string
  title?: string
}

const props = withDefaults(defineProps<Props>(), {
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
      formatter: (params: any) => {
        const param = Array.isArray(params) ? params[0] : params
        return `${param.name}<br/>${param.seriesName}: ${param.value.toLocaleString()}`
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
      type: 'category',
      data: xData,
      axisLabel: {
        rotate: xData.length > 10 ? 45 : 0,
        interval: 0
      }
    },
    yAxis: {
      type: 'value',
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
        type: 'line',
        data: yData,
        smooth: true,
        itemStyle: {
          color: '#2563eb'
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              {
                offset: 0,
                color: 'rgba(37, 99, 235, 0.3)'
              },
              {
                offset: 1,
                color: 'rgba(37, 99, 235, 0.05)'
              }
            ]
          }
        },
        label: {
          show: yData.length <= 15,
          position: 'top',
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
  padding: 0rem;
}
</style>


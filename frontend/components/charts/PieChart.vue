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
import { PieChart as EPieChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent
} from 'echarts/components'
import VChart from 'vue-echarts'

use([
  CanvasRenderer,
  EPieChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent
])

interface Props {
  data: Array<Record<string, any>>
  nameKey?: string
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

  const nameKey = props.nameKey || Object.keys(props.data[0])[0]
  const valueKey = props.valueKey || Object.keys(props.data[0])[1]

  const chartData = props.data.map((row) => {
    const name = row[nameKey] !== null && row[nameKey] !== undefined ? String(row[nameKey]) : ''
    const value = typeof row[valueKey] === 'number' ? row[valueKey] : parseFloat(String(row[valueKey])) || 0
    return { name, value }
  })

  // 상위 10개만 표시 (나머지는 기타로 합침)
  const sortedData = [...chartData].sort((a, b) => b.value - a.value)
  const topData = sortedData.slice(0, 10)
  const others = sortedData.slice(10).reduce((sum, item) => sum + item.value, 0)
  
  const finalData = others > 0 
    ? [...topData, { name: '기타', value: others }]
    : topData

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
        const percent = ((params.value / chartData.reduce((sum, item) => sum + item.value, 0)) * 100).toFixed(1)
        return `${params.name}<br/>${params.seriesName}: ${params.value.toLocaleString()} (${percent}%)`
      }
    },
    legend: {
      orient: 'vertical',
      left: 'left',
      top: 'middle',
      formatter: (name: string) => {
        const item = finalData.find((d) => d.name === name)
        if (item) {
          const total = chartData.reduce((sum, item) => sum + item.value, 0)
          const percent = ((item.value / total) * 100).toFixed(1)
          return `${name} (${percent}%)`
        }
        return name
      }
    },
    series: [
      {
        name: valueKey,
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['60%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 8,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: true,
          formatter: (params: any) => {
            const percent = ((params.value / chartData.reduce((sum, item) => sum + item.value, 0)) * 100).toFixed(1)
            return `${params.name}\n${percent}%`
          }
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 14,
            fontWeight: 'bold'
          }
        },
        data: finalData
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


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
import { MapChart as EMapChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  VisualMapComponent,
  GeoComponent
} from 'echarts/components'
import VChart from 'vue-echarts'

use([
  CanvasRenderer,
  EMapChart,
  TitleComponent,
  TooltipComponent,
  VisualMapComponent,
  GeoComponent
])

interface Props {
  data: Array<Record<string, any>>
  locationKey?: string
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
  const locationKey = props.locationKey || Object.keys(firstRow)[0] || ''
  const valueKey = props.valueKey || Object.keys(firstRow)[1] || ''

  // 데이터를 지역별로 집계
  const locationMap = new Map<string, number>()
  
  props.data.forEach((row) => {
    const location = row[locationKey]
    const value = row[valueKey]
    
    if (location !== null && location !== undefined) {
      const locationStr = String(location).trim()
      const numValue = typeof value === 'number' ? value : parseFloat(String(value)) || 0
      
      if (locationMap.has(locationStr)) {
        locationMap.set(locationStr, locationMap.get(locationStr)! + numValue)
      } else {
        locationMap.set(locationStr, numValue)
      }
    }
  })

  // ECharts 맵 데이터 형식으로 변환
  const mapData = Array.from(locationMap.entries()).map(([name, value]) => ({
    name,
    value
  }))

  // 최대값과 최소값 계산
  const values = mapData.map(item => item.value)
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
      trigger: 'item',
      formatter: (params: any) => {
        if (params.data) {
          return `${params.data.name}<br/>${valueKey}: ${params.data.value.toLocaleString()}`
        }
        return `${params.name}<br/>값 없음`
      }
    },
    visualMap: {
      min: minValue,
      max: maxValue,
      left: 'left',
      top: 'bottom',
      text: ['높음', '낮음'],
      calculable: true,
      inRange: {
        color: ['#e0f2fe', '#0284c7', '#0c4a6e']
      },
      textStyle: {
        color: '#333'
      }
    },
    geo: {
      map: 'korea',
      roam: true,
      label: {
        show: true,
        fontSize: 10
      },
      itemStyle: {
        borderColor: '#fff',
        borderWidth: 1,
        areaColor: '#f0f0f0'
      },
      emphasis: {
        itemStyle: {
          areaColor: '#0284c7'
        },
        label: {
          show: true,
          fontSize: 12,
          fontWeight: 'bold'
        }
      }
    },
    series: [
      {
        name: valueKey,
        type: 'map',
        map: 'korea',
        geoIndex: 0,
        data: mapData,
        label: {
          show: true,
          fontSize: 10,
          formatter: (params: any) => {
            return params.data?.name || params.name
          }
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 12,
            fontWeight: 'bold'
          },
          itemStyle: {
            areaColor: '#0284c7'
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





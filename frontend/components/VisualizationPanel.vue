<template>
  <div class="visualization-panel">
    <div v-if="!visualizationMeta || visualizationMeta.chart_type === 'none'" class="no-visualization">
      <p>이 데이터에 대한 시각화를 생성할 수 없습니다.</p>
    </div>

    <div v-else class="chart-wrapper">
      <!-- 바 차트 -->
      <BarChart
        v-if="visualizationMeta.chart_type === 'bar_chart'"
        :data="chartData"
        :x-axis="xAxis"
        :y-axis="yAxis"
        :orientation="barOrientation"
        :title="chartTitle"
      />

      <!-- 라인 차트 -->
      <LineChart
        v-else-if="visualizationMeta.chart_type === 'line_chart'"
        :data="chartData"
        :x-axis="xAxis"
        :y-axis="yAxis"
        :title="chartTitle"
      />

      <!-- 파이 차트 -->
      <PieChart
        v-else-if="visualizationMeta.chart_type === 'pie_chart'"
        :data="chartData"
        :name-key="xAxis"
        :value-key="yAxis"
        :title="chartTitle"
      />

      <!-- 지도 시각화 (추후 구현) -->
      <div v-else-if="visualizationMeta.chart_type === 'map'" class="map-placeholder">
        <p>지도 시각화는 곧 추가될 예정입니다.</p>
      </div>

      <!-- 기타 차트 타입 -->
      <div v-else class="unsupported-chart">
        <p>이 차트 타입은 아직 지원되지 않습니다: {{ visualizationMeta.chart_type }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import BarChart from './charts/BarChart.vue'
import LineChart from './charts/LineChart.vue'
import PieChart from './charts/PieChart.vue'

interface VisualizationMeta {
  chart_type: string
  x_axis?: string | null
  y_axis?: string | null
  orientation?: string | null
  has_location?: boolean
  group_by?: string | null
  time_series?: boolean
}

interface Props {
  data: Array<Record<string, any>>
  visualizationMeta?: VisualizationMeta | null
  title?: string
}

const props = withDefaults(defineProps<Props>(), {
  visualizationMeta: null,
  title: ''
})

const chartData = computed(() => props.data || [])
const chartTitle = computed(() => props.title || '')

const xAxis = computed(() => {
  const value = props.visualizationMeta?.x_axis
  return value ?? undefined
})

const yAxis = computed(() => {
  const value = props.visualizationMeta?.y_axis
  return value ?? undefined
})

const barOrientation = computed(() => {
  const value = props.visualizationMeta?.orientation
  if (value === 'horizontal' || value === 'vertical') {
    return value
  }
  return 'vertical'
})
</script>

<style scoped>
.visualization-panel {
  width: 100%;
  min-height: 400px;
}

.no-visualization,
.map-placeholder,
.unsupported-chart {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 400px;
  color: #64748b;
  font-size: 0.9rem;
}

.chart-wrapper {
  width: 100%;
}
</style>


<script setup>
import { computed } from "vue";

import { createLineChartModel } from "../../lib/chart/createLineChartModel";

const props = defineProps({
  values: {
    type: Array,
    default: () => [],
  },
  title: {
    type: String,
    default: "Time-series chart",
  },
});

const chartModel = computed(() => createLineChartModel(props.values));
</script>

<template>
  <div class="time-series-chart">
    <svg
      class="chart-svg"
      viewBox="0 0 720 280"
      preserveAspectRatio="none"
      role="img"
      :aria-label="title"
    >
      <g v-for="tick in chartModel.yTicks" :key="`y-${tick.value}`">
        <line
          class="chart-grid-line"
          :x1="chartModel.bounds.left"
          :x2="chartModel.bounds.right"
          :y1="tick.y"
          :y2="tick.y"
        />
        <text class="chart-axis-label" :x="chartModel.bounds.left - 12" :y="tick.y + 4">
          {{ tick.label }}
        </text>
      </g>

      <g v-for="tick in chartModel.xTicks" :key="`x-${tick.value}`">
        <line
          class="chart-grid-line chart-grid-line-vertical"
          :x1="tick.x"
          :x2="tick.x"
          :y1="chartModel.bounds.top"
          :y2="chartModel.bounds.bottom"
        />
        <text class="chart-axis-label" :x="tick.x" :y="chartModel.bounds.bottom + 20">
          {{ tick.label }}
        </text>
      </g>

      <path class="chart-area" :d="chartModel.areaPath" />
      <path class="chart-line" :d="chartModel.linePath" />
    </svg>
  </div>
</template>

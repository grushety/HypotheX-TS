<script setup>
import { computed } from 'vue';

import { buildPreviewModel } from '../../lib/alignment/createAlignWarpPanelState.js';

const props = defineProps({
  method: { type: String, default: 'dtw' },
  warpingBand: { type: Number, default: 0.1 },
  referenceValues: { type: Array, default: () => [] },
  segmentValues: { type: Array, default: () => [] },
});

const VIEW_W = 280;
const VIEW_H = 100;
const GRID_W = 100;
const GRID_H = 100;

function buildSeriesPath(values, width, height) {
  if (!Array.isArray(values) || values.length < 2) return '';
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of values) {
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  if (hi === lo) hi = lo + 1;
  const span = hi - lo;
  const n = values.length;
  return (
    'M ' +
    values
      .map((v, i) => {
        const x = (i / (n - 1)) * width;
        const y = height - ((v - lo) / span) * height;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' L ')
  );
}

const refPath = computed(() =>
  buildSeriesPath(props.referenceValues, VIEW_W, VIEW_H),
);
const segPath = computed(() =>
  buildSeriesPath(props.segmentValues, VIEW_W, VIEW_H),
);

const preview = computed(() =>
  buildPreviewModel({ method: props.method, warpingBand: props.warpingBand }),
);

const diagonalPath = computed(() => {
  const pts = preview.value.diagonal;
  if (!pts || pts.length === 0) return '';
  return (
    'M ' +
    pts
      .map((p) => `${(p.x * GRID_W).toFixed(1)},${(GRID_H - p.y * GRID_H).toFixed(1)}`)
      .join(' L ')
  );
});

const bandPath = computed(() => {
  // Sakoe-Chiba band as a stripe ±band around the diagonal.
  if (preview.value.method !== 'dtw') return '';
  const pts = preview.value.diagonal;
  if (!pts || pts.length === 0) return '';
  const half = preview.value.bandHalfWidth;
  const upper = pts.map((p) => ({ x: p.x, y: Math.min(1, p.y + half) }));
  const lower = pts.map((p) => ({ x: p.x, y: Math.max(0, p.y - half) }));
  const upperStr = upper
    .map((p) => `${(p.x * GRID_W).toFixed(1)},${(GRID_H - p.y * GRID_H).toFixed(1)}`)
    .join(' L ');
  const lowerStr = lower
    .reverse()
    .map((p) => `${(p.x * GRID_W).toFixed(1)},${(GRID_H - p.y * GRID_H).toFixed(1)}`)
    .join(' L ');
  return `M ${upperStr} L ${lowerStr} Z`;
});

const methodCaption = computed(() => {
  if (preview.value.method === 'dtw') {
    return `DTW path with Sakoe-Chiba band (±${Math.round(preview.value.bandHalfWidth * 100)} %).`;
  }
  if (preview.value.method === 'soft_dtw') {
    return 'Soft-DTW: smooth diagonal warp (band relaxed).';
  }
  return 'ShapeDBA: barycenter at the diagonal midline.';
});
</script>

<template>
  <div class="alignment-preview" aria-label="Alignment preview">
    <svg
      class="alignment-preview__series"
      :viewBox="`0 0 ${VIEW_W} ${VIEW_H}`"
      :width="VIEW_W"
      :height="VIEW_H"
      role="img"
      aria-label="Reference (solid) versus selected segment (dashed)"
    >
      <path v-if="refPath" :d="refPath" stroke="#41526a" stroke-width="1.4" fill="none" />
      <path
        v-if="segPath"
        :d="segPath"
        stroke="#0a3d91"
        stroke-width="1.4"
        fill="none"
        stroke-dasharray="4 2"
      />
    </svg>

    <div class="alignment-preview__panel">
      <svg
        class="alignment-preview__grid"
        :viewBox="`0 0 ${GRID_W} ${GRID_H}`"
        :width="GRID_W"
        :height="GRID_H"
        role="img"
        :aria-label="`Schematic alignment path for ${preview.method}`"
      >
        <rect
          x="0"
          y="0"
          :width="GRID_W"
          :height="GRID_H"
          fill="rgba(0, 0, 0, 0.03)"
          stroke="rgba(0, 0, 0, 0.15)"
          stroke-width="0.5"
        />
        <path
          v-if="bandPath"
          :d="bandPath"
          fill="rgba(10, 61, 145, 0.15)"
          stroke="none"
        />
        <path
          v-if="diagonalPath"
          :d="diagonalPath"
          stroke="#0a3d91"
          stroke-width="1.5"
          fill="none"
          :stroke-dasharray="preview.barycenter ? '3 2' : null"
        />
      </svg>
      <p class="alignment-preview__caption">{{ methodCaption }}</p>
    </div>
  </div>
</template>

<style scoped>
.alignment-preview {
  display: grid;
  grid-template-columns: 1fr max-content;
  gap: 12px;
  align-items: stretch;
}
.alignment-preview__series {
  width: 100%;
  height: 100px;
  background: rgba(0, 0, 0, 0.02);
  border-radius: 4px;
}
.alignment-preview__panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
.alignment-preview__grid {
  border-radius: 4px;
}
.alignment-preview__caption {
  margin: 0;
  font-size: 0.74rem;
  color: #6b6f8d;
  max-width: 110px;
  text-align: center;
}
</style>

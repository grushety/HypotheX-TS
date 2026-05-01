<script setup>
import { ref } from 'vue';

import { sketchpadToSeries } from '../../lib/donors/sketchpadToSeries.js';

const props = defineProps({
  targetLength: { type: Number, default: 64 },
  amplitudeRange: {
    type: Object,
    default: () => ({ min: 0, max: 1 }),
  },
});

const emit = defineEmits(['update:values']);

const CANVAS_WIDTH = 320;
const CANVAS_HEIGHT = 120;

const canvasRef = ref(null);
const points = ref([]);
const isDrawing = ref(false);
let redrawHandle = 0;

function scheduleRedraw() {
  if (redrawHandle) return;
  const raf = typeof requestAnimationFrame === 'function'
    ? requestAnimationFrame
    : (cb) => setTimeout(cb, 16);
  redrawHandle = raf(() => {
    redrawHandle = 0;
    redraw();
  });
}

function getCoords(event) {
  const canvas = canvasRef.value;
  if (!canvas) return null;
  const rect = canvas.getBoundingClientRect();
  const source = event.touches ? event.touches[0] : event;
  if (!source) return null;
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  return {
    x: (source.clientX - rect.left) * scaleX,
    y: (source.clientY - rect.top) * scaleY,
  };
}

function redraw() {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (points.value.length < 2) return;
  ctx.strokeStyle = '#0a3d91';
  ctx.lineWidth = 2;
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';
  ctx.beginPath();
  ctx.moveTo(points.value[0].x, points.value[0].y);
  for (let i = 1; i < points.value.length; i += 1) {
    ctx.lineTo(points.value[i].x, points.value[i].y);
  }
  ctx.stroke();
}

function emitSeries() {
  const series = sketchpadToSeries(
    points.value,
    props.targetLength,
    props.amplitudeRange,
  );
  emit('update:values', series);
}

function handlePointerDown(event) {
  event.preventDefault();
  const c = getCoords(event);
  if (!c) return;
  isDrawing.value = true;
  points.value = [c];
  redraw();
}

function handlePointerMove(event) {
  if (!isDrawing.value) return;
  event.preventDefault();
  const c = getCoords(event);
  if (!c) return;
  points.value = [...points.value, c];
  scheduleRedraw();
}

function handlePointerUp(event) {
  if (!isDrawing.value) return;
  event.preventDefault();
  isDrawing.value = false;
  redraw();
  emitSeries();
}

function handleClear() {
  points.value = [];
  redraw();
  emit('update:values', null);
}
</script>

<template>
  <div class="donor-sketchpad" aria-label="Donor sketch pad">
    <canvas
      ref="canvasRef"
      class="donor-sketchpad__canvas"
      :width="CANVAS_WIDTH"
      :height="CANVAS_HEIGHT"
      role="img"
      aria-label="Drag to sketch a donor curve"
      @mousedown="handlePointerDown"
      @mousemove="handlePointerMove"
      @mouseup="handlePointerUp"
      @mouseleave="handlePointerUp"
      @touchstart="handlePointerDown"
      @touchmove="handlePointerMove"
      @touchend="handlePointerUp"
    />
    <div class="donor-sketchpad__actions">
      <button type="button" class="donor-sketchpad__clear" @click="handleClear">
        Clear
      </button>
      <p class="donor-sketchpad__hint">
        Drag from left to right to sketch a donor curve. The amplitude is
        rescaled to the original segment's min/max.
      </p>
    </div>
  </div>
</template>

<style scoped>
.donor-sketchpad {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.donor-sketchpad__canvas {
  width: 100%;
  height: 120px;
  border: 1px dashed var(--border-subtle, #d0d7de);
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.02);
  touch-action: none;
  cursor: crosshair;
}
.donor-sketchpad__actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.donor-sketchpad__clear {
  font: inherit;
  padding: 4px 10px;
  border: 1px solid var(--border-subtle, #d0d7de);
  border-radius: 4px;
  background: var(--surface, #ffffff);
  cursor: pointer;
}
.donor-sketchpad__hint {
  margin: 0;
  font-size: 0.78rem;
  color: #6b6f8d;
}
</style>

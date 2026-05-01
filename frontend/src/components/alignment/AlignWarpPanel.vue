<script setup>
import { computed, ref, watch } from 'vue';

import {
  COMPAT_STATUS,
  DEFAULT_METHOD,
  DEFAULT_WARPING_BAND,
  MAX_WARPING_BAND,
  MIN_WARPING_BAND,
  buildAlignWarpPayload,
  createAlignWarpPanelState,
} from '../../lib/alignment/createAlignWarpPanelState.js';
import AlignmentPreview from './AlignmentPreview.vue';
import TemplateLibraryPicker from './TemplateLibraryPicker.vue';

const props = defineProps({
  segments: { type: Array, default: () => [] },
  selectedSegmentIds: { type: Array, default: () => [] },
  initialReferenceSegmentId: { type: String, default: null },
  templateOptions: { type: Array, default: () => [] },
  seriesValues: { type: Array, default: () => [] },
});

const emit = defineEmits(['op-invoked', 'select-reference']);

const referenceSegmentId = ref(props.initialReferenceSegmentId);
const method = ref(DEFAULT_METHOD);
const warpingBand = ref(DEFAULT_WARPING_BAND);
const selectedTemplateId = ref(null);

watch(
  () => props.initialReferenceSegmentId,
  (id) => {
    referenceSegmentId.value = id;
  },
);

const state = computed(() =>
  createAlignWarpPanelState({
    segments: props.segments,
    referenceSegmentId: referenceSegmentId.value,
    selectedSegmentIds: props.selectedSegmentIds,
    method: method.value,
    warpingBand: warpingBand.value,
    templateOptions: props.templateOptions,
  }),
);

function sliceSegmentValues(segment) {
  if (!segment || !Array.isArray(props.seriesValues)) return [];
  const start = Number(segment.start ?? 0);
  const end = Number(segment.end ?? props.seriesValues.length - 1);
  if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return [];
  return props.seriesValues.slice(start, end + 1);
}

const referenceValues = computed(() => sliceSegmentValues(state.value.referenceSegment));
const focusSegment = computed(() => state.value.segmentsToAlign[0] ?? null);
const focusSegmentValues = computed(() => sliceSegmentValues(focusSegment.value));

function handlePickReference(segmentId) {
  referenceSegmentId.value = segmentId;
  emit('select-reference', segmentId);
}

function handleSelectTemplate(templateId) {
  selectedTemplateId.value = templateId;
}

function handleApply() {
  if (!state.value.canApply) return;
  const payload = buildAlignWarpPayload({
    referenceSegmentId: state.value.referenceSegmentId,
    segmentIds: state.value.segmentsToAlign.map((s) => s.id),
    method: state.value.methodKey,
    warpingBand: state.value.warpingBand,
  });
  emit('op-invoked', payload);
}
</script>

<template>
  <section class="align-warp-panel" aria-label="Align / warp panel">
    <header class="align-warp-panel__header">
      <p class="section-label">Tier-3 — Align / warp</p>
      <h3>Reference picker</h3>
    </header>

    <div class="align-warp-panel__columns">
      <section class="align-warp-panel__series" aria-label="Pick reference segment">
        <p class="section-label">Click a segment to pick reference</p>
        <ul class="align-warp-panel__segment-list">
          <li
            v-for="seg in props.segments"
            :key="seg.id"
            class="align-warp-panel__segment-item"
            :class="{
              'align-warp-panel__segment-item--reference': seg.id === state.referenceSegmentId,
              'align-warp-panel__segment-item--to-align': props.selectedSegmentIds.includes(seg.id) && seg.id !== state.referenceSegmentId,
            }"
          >
            <button
              type="button"
              class="align-warp-panel__segment-button"
              :aria-pressed="seg.id === state.referenceSegmentId"
              @click="handlePickReference(seg.id)"
            >
              <span class="align-warp-panel__segment-id">{{ seg.id }}</span>
              <span class="align-warp-panel__segment-label">{{ seg.label }}</span>
            </button>
          </li>
        </ul>
      </section>

      <TemplateLibraryPicker
        :templates="state.templateOptions"
        :selected-template-id="selectedTemplateId"
        @select-template="handleSelectTemplate"
      />
    </div>

    <fieldset class="align-warp-panel__methods" aria-label="Alignment method">
      <legend class="section-label">Method</legend>
      <label
        v-for="m in state.methods"
        :key="m"
        class="align-warp-panel__method-option"
      >
        <input
          type="radio"
          name="align-method"
          :value="m"
          :checked="state.methodKey === m"
          @change="method = m"
        />
        <span>
          <strong>{{ state.methodLabels[m] }}</strong>
          <small>{{ state.methodDescriptions[m] }}</small>
        </span>
      </label>
    </fieldset>

    <label class="align-warp-panel__band">
      <span class="sidebar-label">
        Warping band: {{ state.warpingBandPercent }}% of segment length
      </span>
      <input
        type="range"
        class="align-warp-panel__slider"
        :min="MIN_WARPING_BAND"
        :max="MAX_WARPING_BAND"
        step="0.01"
        :value="state.warpingBand"
        aria-label="Sakoe-Chiba warping band as fraction of segment length"
        @input="warpingBand = Number($event.target.value)"
      />
    </label>

    <AlignmentPreview
      :method="state.methodKey"
      :warping-band="state.warpingBand"
      :reference-values="referenceValues"
      :segment-values="focusSegmentValues"
    />

    <p
      v-if="state.compat.status === COMPAT_STATUS.APPROX && state.compat.message"
      class="align-warp-panel__warning align-warp-panel__warning--approx"
      role="status"
    >
      ⚠ {{ state.compat.message }}
    </p>
    <p
      v-else-if="state.compat.status === COMPAT_STATUS.INCOMPATIBLE && state.compat.message"
      class="align-warp-panel__warning align-warp-panel__warning--incompatible"
      role="alert"
    >
      ✗ {{ state.compat.message }}
    </p>

    <footer class="align-warp-panel__footer">
      <button
        type="button"
        class="align-warp-panel__apply"
        :disabled="!state.canApply"
        :title="state.canApply ? null : state.applyDisabledReason"
        @click="handleApply"
      >
        Apply align/warp
      </button>
    </footer>
  </section>
</template>

<style scoped>
.align-warp-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid var(--border-subtle, #d0d7de);
  border-radius: 8px;
  background: var(--surface, #ffffff);
  font-size: 0.9rem;
}
.align-warp-panel__header h3 {
  margin: 0;
  font-size: 1rem;
}
.align-warp-panel__columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.align-warp-panel__segment-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
  max-height: 180px;
  overflow-y: auto;
}
.align-warp-panel__segment-button {
  width: 100%;
  font: inherit;
  text-align: left;
  padding: 4px 8px;
  border: 1px solid var(--border-subtle, #d0d7de);
  border-radius: 4px;
  background: var(--surface, #ffffff);
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  gap: 8px;
}
.align-warp-panel__segment-item--reference .align-warp-panel__segment-button {
  border-color: var(--focus-ring, #0a3d91);
  background: rgba(10, 61, 145, 0.08);
  font-weight: 600;
}
.align-warp-panel__segment-item--to-align .align-warp-panel__segment-button {
  border-color: #2b6f8d;
  background: rgba(43, 111, 141, 0.06);
}
.align-warp-panel__segment-id {
  font-family: var(--font-mono, ui-monospace, "SFMono-Regular", Consolas, monospace);
  font-size: 0.78rem;
}
.align-warp-panel__segment-label {
  font-size: 0.78rem;
  color: #6b6f8d;
}
.align-warp-panel__methods {
  border: 0;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.align-warp-panel__method-option {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 8px;
  align-items: baseline;
}
.align-warp-panel__method-option small {
  display: block;
  color: #6b6f8d;
  font-size: 0.78rem;
}
.align-warp-panel__band {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.align-warp-panel__slider {
  width: 100%;
}
.align-warp-panel__warning {
  margin: 0;
  padding: 6px 8px;
  border-radius: 6px;
  font-size: 0.82rem;
}
.align-warp-panel__warning--approx {
  background: #fff8c5;
  border: 1px solid #d4a72c;
  color: #9a6700;
}
.align-warp-panel__warning--incompatible {
  background: #ffebe9;
  border: 1px solid #ff8182;
  color: #cf222e;
}
.align-warp-panel__footer {
  display: flex;
  justify-content: flex-end;
}
.align-warp-panel__apply {
  font: inherit;
  padding: 6px 14px;
  border: 1px solid #0a3d91;
  border-radius: 6px;
  background: #0a3d91;
  color: #fff;
  cursor: pointer;
}
.align-warp-panel__apply:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>

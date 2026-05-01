<script setup>
import { computed, onMounted, ref, watch } from 'vue';

import {
  DEFAULT_BACKEND,
  DEFAULT_CROSSFADE_WIDTH,
  MAX_CROSSFADE_WIDTH,
  MIN_CROSSFADE_WIDTH,
  USER_DRAWN_BACKEND,
  buildAcceptPayload,
  createDonorPickerState,
} from '../../lib/donors/createDonorPickerState.js';
import { proposeDonor } from '../../services/api/donorApi.js';
import DonorCard from './DonorCard.vue';
import DonorSketchpad from './DonorSketchpad.vue';

const props = defineProps({
  segmentValues: { type: Array, default: () => [] },
  targetClass: { type: String, default: '' },
  segmentId: { type: String, default: null },
  fetchImpl: { type: Function, default: null },
});

const emit = defineEmits(['op-invoked', 'close']);

const selectedBackend = ref(DEFAULT_BACKEND);
const candidates = ref([]);
const selectedCandidateId = ref(null);
const crossfadeWidth = ref(DEFAULT_CROSSFADE_WIDTH);
const sketchpadValues = ref(null);
const loading = ref(false);
const error = ref(null);
const excludeIds = ref([]);
const kIndex = ref(0);

const state = computed(() =>
  createDonorPickerState({
    selectedBackend: selectedBackend.value,
    candidates: candidates.value,
    selectedCandidateId: selectedCandidateId.value,
    crossfadeWidth: crossfadeWidth.value,
    sketchpadValues: sketchpadValues.value,
    loading: loading.value,
    error: error.value,
  }),
);

const amplitudeRange = computed(() => {
  if (!props.segmentValues?.length) return { min: 0, max: 1 };
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of props.segmentValues) {
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  if (!Number.isFinite(lo) || !Number.isFinite(hi) || lo === hi) {
    return { min: 0, max: 1 };
  }
  return { min: lo, max: hi };
});

const COMPARISON_WIDTH = 320;
const COMPARISON_HEIGHT = 80;

function buildPath(values) {
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
  const pts = values.map((v, i) => {
    const x = (i / (n - 1)) * COMPARISON_WIDTH;
    const y = COMPARISON_HEIGHT - ((v - lo) / span) * COMPARISON_HEIGHT;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  return `M ${pts.join(' L ')}`;
}

const originalPath = computed(() => buildPath(props.segmentValues));
const donorPath = computed(() => buildPath(state.value.selectedCandidate?.values ?? []));

async function loadCandidates() {
  if (state.value.isUserDrawn) return;
  if (!props.segmentValues?.length || !props.targetClass) {
    error.value = 'Select a target class and segment before fetching donors.';
    candidates.value = [];
    return;
  }
  loading.value = true;
  error.value = null;
  try {
    const fetcher = props.fetchImpl ?? undefined;
    const result = await proposeDonor(
      {
        backend: selectedBackend.value,
        segmentValues: props.segmentValues,
        targetClass: props.targetClass,
        k: kIndex.value,
        excludeIds: excludeIds.value,
      },
      fetcher,
    );
    candidates.value = result.candidates ?? [];
    selectedCandidateId.value = candidates.value[0]?.donor_id ?? null;
  } catch (err) {
    candidates.value = [];
    selectedCandidateId.value = null;
    error.value = err instanceof Error ? err.message : 'Failed to load donors.';
  } finally {
    loading.value = false;
  }
}

function handleSelectBackend(event) {
  selectedBackend.value = event.target.value;
  candidates.value = [];
  selectedCandidateId.value = null;
  excludeIds.value = [];
  kIndex.value = 0;
  error.value = null;
  if (selectedBackend.value !== USER_DRAWN_BACKEND) {
    loadCandidates();
  }
}

function handleSelectCandidate(donorId) {
  selectedCandidateId.value = donorId;
}

function handleAccept(donorId) {
  const candidate = state.value.candidates.find((c) => c.donor_id === donorId);
  if (!candidate) return;
  const payload = buildAcceptPayload({
    backend: selectedBackend.value,
    candidate,
    crossfadeWidth: crossfadeWidth.value,
  });
  emit('op-invoked', payload);
}

function handleAcceptSelected() {
  if (state.value.selectedCandidate) {
    handleAccept(state.value.selectedCandidate.donor_id);
  }
}

function handleReject() {
  if (!state.value.canReject) return;
  const current = state.value.selectedCandidate;
  if (current?.donor_id) {
    excludeIds.value = [...excludeIds.value, current.donor_id];
  }
  kIndex.value += 1;
  loadCandidates();
}

function handleSketchpadValues(values) {
  sketchpadValues.value = values;
  selectedCandidateId.value = values && values.length > 1 ? 'user-drawn' : null;
}

watch(
  () => props.segmentId,
  () => {
    candidates.value = [];
    selectedCandidateId.value = null;
    excludeIds.value = [];
    kIndex.value = 0;
    error.value = null;
    sketchpadValues.value = null;
    if (!state.value.isUserDrawn) loadCandidates();
  },
);

onMounted(() => {
  if (!state.value.isUserDrawn) loadCandidates();
});
</script>

<template>
  <section class="donor-picker" aria-label="Donor picker">
    <header class="donor-picker__header">
      <p class="section-label">Replace from library</p>
      <h3>Donor picker</h3>
      <button
        type="button"
        class="donor-picker__close"
        aria-label="Close donor picker"
        @click="emit('close')"
      >
        ✕
      </button>
    </header>

    <label class="donor-picker__field">
      <span class="sidebar-label">Backend</span>
      <select
        class="donor-picker__select"
        :value="state.backendKey"
        aria-label="Donor backend"
        @change="handleSelectBackend"
      >
        <option
          v-for="opt in state.options"
          :key="opt.key"
          :value="opt.key"
          :disabled="!opt.supported"
        >
          {{ opt.label }}<template v-if="!opt.supported"> (coming soon)</template>
        </option>
      </select>
    </label>

    <p v-if="!state.backendSupported" class="donor-picker__warning" role="alert">
      The {{ state.backendLabel }} backend is not yet implemented; pick another.
    </p>

    <DonorSketchpad
      v-if="state.isUserDrawn"
      :target-length="props.segmentValues?.length || 64"
      :amplitude-range="amplitudeRange"
      @update:values="handleSketchpadValues"
    />

    <div v-else class="donor-picker__candidates" aria-live="polite">
      <p v-if="state.loading" class="donor-picker__meta">Loading donors…</p>
      <p v-else-if="state.error" class="donor-picker__error" role="alert">
        {{ state.error }}
      </p>
      <p v-else-if="state.candidates.length === 0" class="donor-picker__meta">
        No donors yet. Pick a backend or hit Reject to fetch the next.
      </p>
      <DonorCard
        v-for="cand in state.candidates"
        :key="cand.donor_id"
        :candidate="cand"
        :metric-label="state.metricLabel"
        :selected="cand.donor_id === state.selectedCandidateId"
        @select="handleSelectCandidate"
        @accept="handleAccept"
      />
    </div>

    <section v-if="state.selectedCandidate" class="donor-picker__compare" aria-label="Side-by-side comparison">
      <p class="section-label">Side-by-side</p>
      <svg
        class="donor-picker__compare-chart"
        :viewBox="`0 0 ${COMPARISON_WIDTH} ${COMPARISON_HEIGHT}`"
        :width="COMPARISON_WIDTH"
        :height="COMPARISON_HEIGHT"
        role="img"
        aria-label="Original segment versus selected donor"
      >
        <path
          v-if="originalPath"
          :d="originalPath"
          fill="none"
          stroke="#41526a"
          stroke-width="1.4"
        />
        <path
          v-if="donorPath"
          :d="donorPath"
          fill="none"
          stroke="#0a3d91"
          stroke-width="1.4"
          stroke-dasharray="4 2"
        />
      </svg>

      <label class="donor-picker__field">
        <span class="sidebar-label">
          Crossfade width: {{ state.crossfadeWidth.toFixed(2) }}
        </span>
        <input
          type="range"
          class="donor-picker__slider"
          :min="MIN_CROSSFADE_WIDTH"
          :max="MAX_CROSSFADE_WIDTH"
          step="0.01"
          :value="state.crossfadeWidth"
          aria-label="Crossfade width as fraction of segment length"
          @input="crossfadeWidth = Number($event.target.value)"
        />
      </label>
    </section>

    <footer class="donor-picker__footer">
      <button
        type="button"
        class="donor-picker__reject"
        :disabled="!state.canReject"
        @click="handleReject"
      >
        Reject &amp; next
      </button>
      <button
        type="button"
        class="donor-picker__accept"
        :disabled="!state.canAccept"
        @click="handleAcceptSelected"
      >
        Accept
      </button>
    </footer>
  </section>
</template>

<style scoped>
.donor-picker {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid var(--border-subtle, #d0d7de);
  border-radius: 8px;
  background: var(--surface, #ffffff);
  font-size: 0.9rem;
}
.donor-picker__header {
  position: relative;
  margin: 0;
}
.donor-picker__header h3 {
  margin: 0;
  font-size: 1rem;
}
.donor-picker__close {
  position: absolute;
  top: 0;
  right: 0;
  font: inherit;
  border: 0;
  background: transparent;
  cursor: pointer;
  font-size: 1rem;
  color: #6b6f8d;
}
.donor-picker__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.donor-picker__select {
  font: inherit;
  padding: 6px 8px;
  border: 1px solid var(--border-subtle, #d0d7de);
  border-radius: 6px;
  background: var(--surface, #ffffff);
  color: inherit;
}
.donor-picker__candidates {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 240px;
  overflow-y: auto;
}
.donor-picker__meta {
  margin: 0;
  color: #6b6f8d;
  font-size: 0.85rem;
}
.donor-picker__warning,
.donor-picker__error {
  margin: 0;
  padding: 6px 8px;
  border-radius: 6px;
  background: #ffebe9;
  border: 1px solid #ff8182;
  color: #cf222e;
  font-size: 0.82rem;
}
.donor-picker__compare {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-top: 4px;
  border-top: 1px solid var(--border-subtle, #d0d7de);
}
.donor-picker__compare-chart {
  width: 100%;
  height: 80px;
  background: rgba(0, 0, 0, 0.02);
  border-radius: 4px;
}
.donor-picker__slider {
  width: 100%;
}
.donor-picker__footer {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.donor-picker__reject,
.donor-picker__accept {
  font: inherit;
  padding: 6px 14px;
  border: 1px solid var(--border-subtle, #d0d7de);
  border-radius: 6px;
  background: var(--surface, #ffffff);
  cursor: pointer;
}
.donor-picker__accept {
  background: #0a3d91;
  color: #fff;
  border-color: #0a3d91;
}
.donor-picker__accept:disabled,
.donor-picker__reject:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}
</style>

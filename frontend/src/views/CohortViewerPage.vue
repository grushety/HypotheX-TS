<script setup>
import { computed, ref } from "vue";

import { applyCohort } from "../services/api/cohortApi.js";
import { createCohortResultModel } from "../lib/cohort/createCohortResultModel.js";

const props = defineProps({
  dataset: { type: String, default: "" },
  artifactId: { type: String, default: "" },
  split: { type: String, default: "test" },
  maxSampleIndex: { type: Number, default: 0 },
});

const emit = defineEmits(["pin"]);

function buildPinPayload() {
  const summary = cohortResult.value
    ? `flip rate ${model.value.summary.flipRateLabel} · mean Δ ${model.value.summary.meanDeltaLabel}pp · ${model.value.summary.total} samples`
    : "";
  return {
    title: `Cohort · ${opName.value} on ${cohortResult.value?.dataset_name ?? props.dataset}`,
    summary,
    dataset: cohortResult.value?.dataset_name ?? props.dataset,
    op_name: cohortResult.value?.op_name ?? opName.value,
    op_params: cohortResult.value?.op_params ?? null,
    method: cohortResult.value?.method ?? null,
    reference: cohortResult.value?.reference ?? null,
    aggregates: cohortResult.value?.aggregates ?? null,
    per_series: cohortResult.value?.per_series ?? [],
  };
}

function handlePinClick() {
  if (!cohortResult.value) return;
  emit("pin", buildPinPayload());
}

const cohortSize = ref(Math.min(8, Math.max(1, props.maxSampleIndex + 1)));
const opName = ref("amplify");
const alpha = ref(2.0);
const delta = ref(0.5);

const cohortResult = ref(null);
const cohortLoading = ref(false);
const cohortError = ref(null);
let cohortRequestId = 0;

const model = computed(() => createCohortResultModel(cohortResult.value));

const sampleIndices = computed(() => {
  const cap = props.maxSampleIndex >= 0 ? props.maxSampleIndex + 1 : 0;
  const requested = Math.min(cohortSize.value, cap);
  return Array.from({ length: requested }, (_, index) => index);
});

const canApply = computed(
  () =>
    Boolean(props.artifactId) &&
    Boolean(props.dataset) &&
    sampleIndices.value.length > 0 &&
    !cohortLoading.value,
);

async function handleApply() {
  if (!canApply.value) return;
  const requestId = ++cohortRequestId;
  cohortLoading.value = true;
  cohortError.value = null;
  try {
    const payload = await applyCohort({
      artifactId: props.artifactId,
      dataset: props.dataset,
      split: props.split,
      sampleIndices: sampleIndices.value,
      opName: opName.value,
      opParams:
        opName.value === "amplify"
          ? { alpha: Number(alpha.value) }
          : { delta: Number(delta.value) },
    });
    if (requestId !== cohortRequestId) return;
    cohortResult.value = payload;
  } catch (requestError) {
    if (requestId !== cohortRequestId) return;
    cohortResult.value = null;
    cohortError.value =
      requestError instanceof Error ? requestError.message : "Cohort apply failed.";
  } finally {
    if (requestId === cohortRequestId) {
      cohortLoading.value = false;
    }
  }
}

function signedPp(value) {
  if (!Number.isFinite(value)) return "—";
  const sign = value >= 0 ? "+" : "−";
  return `${sign}${Math.abs(value * 100).toFixed(1)}pp`;
}

// Dumbbell geometry — each row is plotted on the probability axis [0, 1]
// with the decision boundary at 0.5. Baseline and current are dots
// connected by a segment. Pure presentation math; no DOM access.
const dumbbell = computed(() => {
  if (!model.value.hasData) return null;
  const width = 100;
  return model.value.rows.map((row) => {
    const baselineX = row.baselineProb * width;
    const currentX = row.currentProb * width;
    return {
      sampleIndex: row.sampleIndex,
      baselineX,
      currentX,
      baselineProb: row.baselineProb,
      currentProb: row.currentProb,
      delta: row.delta,
      deltaLabel: row.deltaLabel,
      flipped: row.flipped,
      isBiggestMover: row.isBiggestMover,
      direction: currentX >= baselineX ? "right" : "left",
      lineLeft: Math.min(baselineX, currentX),
      lineWidth: Math.abs(currentX - baselineX),
    };
  });
});
</script>

<template>
  <section class="cohort-view" aria-label="Cohort confirmation">
    <!-- Selector strip -->
    <header class="cohort-config">
      <div class="cohort-field">
        <span class="mlabel">Cohort size</span>
        <input
          type="number"
          min="1"
          :max="Math.max(1, maxSampleIndex + 1)"
          v-model.number="cohortSize"
          class="cohort-input"
        />
        <span class="cohort-sub">of {{ Math.max(0, maxSampleIndex + 1) }} available</span>
      </div>
      <div class="cohort-field">
        <span class="mlabel">Operation</span>
        <select v-model="opName" class="cohort-input">
          <option value="amplify">Amplify (×α)</option>
          <option value="shift">Shift (+δ)</option>
        </select>
      </div>
      <div v-if="opName === 'amplify'" class="cohort-field">
        <span class="mlabel">α</span>
        <input type="number" step="0.1" v-model.number="alpha" class="cohort-input" />
      </div>
      <div v-else class="cohort-field">
        <span class="mlabel">δ</span>
        <input type="number" step="0.1" v-model.number="delta" class="cohort-input" />
      </div>
      <button
        type="button"
        class="cohort-apply"
        :disabled="!canApply"
        @click="handleApply"
      >
        <span v-if="cohortLoading" class="spin" aria-hidden="true" />
        {{ cohortLoading ? "Applying…" : "Apply to cohort" }}
      </button>
    </header>

    <p v-if="cohortError" class="cohort-error" role="alert">{{ cohortError }}</p>

    <!-- Results -->
    <template v-if="model.hasData">
      <div class="cohort-results-head">
        <span class="mlabel">Outcome</span>
        <button
          type="button"
          class="cohort-pin-btn"
          aria-label="Pin cohort outcome to shoebox"
          @click="handlePinClick"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M12 17v5" />
            <path d="M9 2h6" />
            <path d="M10 2v6l-3 4v3h10v-3l-3-4V2" />
          </svg>
          Pin outcome
        </button>
      </div>
      <!-- Summary cards -->
      <div class="cohort-cards">
        <div class="cohort-card">
          <span class="mlabel">Flip rate</span>
          <div class="cohort-stat">
            <strong class="cohort-stat-value">{{ model.summary.flipRateLabel }}</strong>
            <span class="cohort-stat-count">
              {{ model.summary.flippedCount }} / {{ model.summary.total }}
            </span>
          </div>
          <div class="cohort-ci">
            CI {{ Math.round(model.summary.flipRateCi.confidence * 100) }}%
            [{{ model.summary.flipRateCi.lowerLabel }},
            {{ model.summary.flipRateCi.upperLabel }}]
          </div>
        </div>
        <div class="cohort-card">
          <span class="mlabel">Mean Δ</span>
          <strong
            class="cohort-stat-value"
            :class="model.summary.meanDelta >= 0 ? 'pos' : 'neg'"
          >{{ model.summary.meanDeltaLabel }}pp</strong>
          <div class="cohort-ci">
            CI {{ Math.round(model.summary.meanDeltaCi.confidence * 100) }}%
            [{{ model.summary.meanDeltaCi.lowerLabel }},
            {{ model.summary.meanDeltaCi.upperLabel }}]
          </div>
        </div>
        <div class="cohort-card">
          <span class="mlabel">Biggest mover</span>
          <strong class="cohort-stat-value">
            sample {{ model.summary.biggestMoverIndex ?? "—" }}
          </strong>
          <div class="cohort-ci">held class · sorted by signed Δ</div>
        </div>
      </div>

      <!-- Cherry-picking caveat -->
      <p v-if="model.cherryPickingWarning" class="cohort-caveat" role="status">
        ⚠ {{ model.cherryPickingWarning }}
      </p>

      <!-- Dumbbell plot -->
      <section class="cohort-dumbbell" aria-label="Per-series dumbbell plot">
        <header class="cohort-dumbbell-head">
          <span class="mlabel">Per-series Δ · {{ model.rows.length }} samples</span>
          <span class="cohort-dumbbell-legend">
            <span class="leg-dot baseline" /> baseline
            <span class="leg-dot current" /> after op
            <span class="leg-boundary">↕</span> decision boundary
          </span>
        </header>
        <ol class="cohort-dumbbell-list">
          <li
            v-for="row in dumbbell"
            :key="row.sampleIndex"
            class="cohort-dumbbell-row"
            :class="{ flipped: row.flipped, biggest: row.isBiggestMover }"
          >
            <span class="cohort-dumbbell-name">#{{ row.sampleIndex }}</span>
            <div class="cohort-dumbbell-track">
              <span class="cohort-dumbbell-boundary" aria-hidden="true" />
              <span
                class="cohort-dumbbell-segment"
                :class="row.flipped ? 'flip' : 'noflip'"
                :style="{ left: `${row.lineLeft}%`, width: `${row.lineWidth}%` }"
              />
              <span
                class="cohort-dumbbell-baseline-dot"
                :style="{ left: `calc(${row.baselineX}% - 5px)` }"
                :title="`baseline P = ${(row.baselineProb * 100).toFixed(0)}%`"
              />
              <span
                class="cohort-dumbbell-current-dot"
                :class="row.flipped ? 'flip' : 'noflip'"
                :style="{ left: `calc(${row.currentX}% - 5px)` }"
                :title="`current P = ${(row.currentProb * 100).toFixed(0)}%`"
              />
            </div>
            <span class="cohort-dumbbell-delta" :class="row.delta >= 0 ? 'pos' : 'neg'">
              {{ row.deltaLabel }}pp
            </span>
            <span v-if="row.flipped" class="cohort-dumbbell-flip-tag">FLIP</span>
            <span v-else class="cohort-dumbbell-flip-tag-empty" />
          </li>
        </ol>
      </section>

      <!-- Δ-magnitude histogram -->
      <section v-if="model.histogram" class="cohort-histogram" aria-label="Δ magnitude histogram">
        <header class="cohort-histogram-head">
          <span class="mlabel">Δ distribution</span>
          <span class="cohort-histogram-meta" :title="model.reference">{{ model.method }}</span>
        </header>
        <div class="cohort-histogram-bars" role="presentation">
          <span
            v-for="(bin, index) in model.histogram"
            :key="`bin-${index}`"
            class="cohort-histogram-bin"
            :class="{ zero: bin.containsZero }"
            :title="`[${(bin.left * 100).toFixed(0)}pp, ${(bin.right * 100).toFixed(0)}pp]: ${bin.count}`"
          >
            <span
              class="cohort-histogram-bar"
              :style="{ height: `${bin.heightPct}%` }"
            />
            <span class="cohort-histogram-bin-count">{{ bin.count }}</span>
          </span>
        </div>
      </section>
    </template>

    <div v-else-if="!cohortLoading && !cohortError" class="cohort-empty">
      Pick a cohort size + operation, then click <b>Apply to cohort</b> to evaluate.
    </div>
  </section>
</template>

<style scoped>
.cohort-view {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px 18px;
  overflow: auto;
}

.cohort-config {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px;
  padding: 9px 11px;
  background: var(--bg-bar);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
}
.cohort-field { display: flex; flex-direction: column; gap: 3px; min-width: 110px; }
.cohort-field .mlabel {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.13em;
  text-transform: uppercase;
  color: var(--ink-3);
}
.cohort-input {
  padding: 5px 9px;
  border: 1px solid var(--line-2);
  border-radius: var(--r-sm);
  background: var(--bg-panel);
  font: inherit;
  font-size: 12px;
  min-height: 28px;
  width: 100%;
}
.cohort-sub { font-size: 10.5px; color: var(--ink-4); }

.cohort-apply {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  background: var(--ink);
  color: #fff;
  border: 1px solid var(--ink);
  border-radius: var(--r-sm);
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.cohort-apply:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.cohort-apply:hover:not(:disabled) { background: #000; }

.spin {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.35);
  border-top-color: #fff;
  border-radius: 50%;
  animation: ch-spin 0.7s linear infinite;
}
@keyframes ch-spin { to { transform: rotate(360deg); } }

.cohort-error {
  margin: 0;
  padding: 7px 10px;
  background: var(--st-fail-bg);
  border: 1px solid #e8a6a6;
  border-radius: var(--r-sm);
  color: var(--st-fail);
  font-size: 12px;
}

/* Outcome header + pin button */
.cohort-results-head {
  display: flex;
  align-items: center;
  gap: 9px;
}
.cohort-pin-btn {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border: 1px solid var(--line-2);
  background: var(--bg-panel);
  color: var(--ink-2);
  border-radius: var(--r-sm);
  font: inherit;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
}
.cohort-pin-btn:hover {
  background: var(--bg-hover);
  border-color: var(--ink-3);
  color: var(--ink);
}
.cohort-pin-btn svg { width: 12px; height: 12px; }

/* Summary cards */
.cohort-cards { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.cohort-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  background: var(--bg-panel);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
}
.cohort-card .mlabel {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.13em;
  text-transform: uppercase;
  color: var(--ink-3);
}
.cohort-stat {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.cohort-stat-value {
  font-family: var(--font-mono);
  font-size: 22px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--ink);
}
.cohort-stat-value.pos { color: #1d6b32; }
.cohort-stat-value.neg { color: #a81f1f; }
.cohort-stat-count {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--ink-3);
}
.cohort-ci {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--ink-3);
}

.cohort-caveat {
  margin: 0;
  padding: 7px 11px;
  background: var(--st-warn-bg);
  border: 1px solid #e8c98f;
  border-radius: var(--r-sm);
  color: #b3650a;
  font-size: 12px;
}

/* Dumbbell */
.cohort-dumbbell {
  background: var(--bg-panel);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  padding: 10px 12px;
}
.cohort-dumbbell-head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 8px; }
.mlabel {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.13em;
  text-transform: uppercase;
  color: var(--ink-3);
}
.cohort-dumbbell-legend {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 10.5px;
  color: var(--ink-3);
}
.leg-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; }
.leg-dot.baseline { background: var(--ink-3); }
.leg-dot.current { background: var(--ink); }
.leg-boundary { font-family: var(--font-mono); font-weight: 700; }

.cohort-dumbbell-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 5px; }
.cohort-dumbbell-row {
  display: grid;
  grid-template-columns: 46px minmax(0, 1fr) 64px 40px;
  align-items: center;
  gap: 8px;
  padding: 4px 6px;
  border-radius: var(--r-sm);
}
.cohort-dumbbell-row.biggest {
  background: var(--bg-hover);
  box-shadow: inset 0 0 0 1px var(--line-2);
}
.cohort-dumbbell-name {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--ink-2);
}
.cohort-dumbbell-track {
  position: relative;
  height: 14px;
  background: var(--bg-sunken);
  border-radius: var(--r-sm);
  border: 1px solid var(--line);
}
.cohort-dumbbell-boundary {
  position: absolute;
  top: -1px;
  bottom: -1px;
  left: 50%;
  width: 1px;
  background: var(--ink-3);
}
.cohort-dumbbell-segment {
  position: absolute;
  top: 5px;
  height: 4px;
  border-radius: 2px;
  background: var(--ink-4);
}
.cohort-dumbbell-segment.flip { background: var(--st-warn); }
.cohort-dumbbell-baseline-dot,
.cohort-dumbbell-current-dot {
  position: absolute;
  top: 1px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 1.5px solid var(--bg-panel);
}
.cohort-dumbbell-baseline-dot { background: var(--ink-3); }
.cohort-dumbbell-current-dot.noflip { background: var(--ink); }
.cohort-dumbbell-current-dot.flip { background: var(--st-warn); }

.cohort-dumbbell-delta {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.cohort-dumbbell-delta.pos { color: #1d6b32; }
.cohort-dumbbell-delta.neg { color: #a81f1f; }

.cohort-dumbbell-flip-tag {
  font-family: var(--font-mono);
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--st-warn);
  background: var(--st-warn-bg);
  border-radius: 3px;
  padding: 1px 6px;
  text-align: center;
}
.cohort-dumbbell-flip-tag-empty { display: inline-block; width: 100%; height: 1px; }

/* Histogram */
.cohort-histogram {
  background: var(--bg-panel);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  padding: 10px 12px;
}
.cohort-histogram-head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 8px; }
.cohort-histogram-meta {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--ink-4);
  cursor: help;
}
.cohort-histogram-bars {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(0, 1fr);
  gap: 4px;
  height: 80px;
  align-items: end;
}
.cohort-histogram-bin {
  display: flex;
  flex-direction: column-reverse;
  align-items: center;
  gap: 3px;
  min-height: 0;
}
.cohort-histogram-bar {
  width: 100%;
  background: var(--ink-3);
  border-radius: 3px 3px 0 0;
  min-height: 1px;
  transition: height 0.3s;
}
.cohort-histogram-bin.zero .cohort-histogram-bar { background: var(--ink-4); }
.cohort-histogram-bin-count {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--ink-3);
}

.cohort-empty {
  padding: 24px;
  border: 1px dashed var(--line-2);
  border-radius: var(--r-md);
  text-align: center;
  color: var(--ink-3);
  font-size: 12px;
}
.cohort-empty b { color: var(--ink); }
</style>

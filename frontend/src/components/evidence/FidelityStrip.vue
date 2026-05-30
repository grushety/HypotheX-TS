<script setup>
import { computed, ref } from "vue";

const props = defineProps({
  state: { type: Object, required: true },
  rawValues: { type: Array, default: null },
  modelInputValues: { type: Array, default: null },
});

const expanded = ref(false);

function toggle() {
  expanded.value = !expanded.value;
}

const status = computed(() => props.state?.status ?? "empty");
const isEmpty = computed(() => status.value === "empty");
const isWarn = computed(() => status.value === "warn");

const messages = computed(() => props.state?.compatibility?.messages ?? []);

const overlayInput = computed(() =>
  Array.isArray(props.modelInputValues) && props.modelInputValues.length > 0
    ? props.modelInputValues
    : props.rawValues,
);

// SVG sparkline path for the overlay. Two-line: raw vs model-input.
function sparkPath(series, width, height) {
  if (!Array.isArray(series) || series.length < 2) return "";
  let min = Infinity;
  let max = -Infinity;
  for (const value of series) {
    if (!Number.isFinite(value)) continue;
    if (value < min) min = value;
    if (value > max) max = value;
  }
  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) {
    min = (min || 0) - 1;
    max = (max || 0) + 1;
  }
  const span = max - min;
  const step = width / (series.length - 1);
  return series
    .map((value, index) => {
      const x = (index * step).toFixed(2);
      const y = (height - ((value - min) / span) * height).toFixed(2);
      return `${index === 0 ? "M" : "L"} ${x} ${y}`;
    })
    .join(" ");
}

const SPARK_W = 360;
const SPARK_H = 56;

const rawPath = computed(() => sparkPath(props.rawValues, SPARK_W, SPARK_H));
const modelPath = computed(() => sparkPath(overlayInput.value, SPARK_W, SPARK_H));
const overlayMatches = computed(() => {
  const a = props.rawValues;
  const b = overlayInput.value;
  if (!Array.isArray(a) || !Array.isArray(b)) return false;
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i += 1) {
    if (Math.abs((a[i] ?? 0) - (b[i] ?? 0)) > 1e-9) return false;
  }
  return true;
});
</script>

<template>
  <section
    class="fidelity-strip"
    :class="{ 'is-warn': isWarn, 'is-empty': isEmpty, 'is-open': expanded }"
    aria-label="Model fidelity"
  >
    <button
      type="button"
      class="fid-head"
      :aria-expanded="expanded"
      :disabled="isEmpty"
      @click="toggle"
    >
      <span v-if="!isEmpty" class="fid-caret" :class="{ open: expanded }">▸</span>
      <span class="fid-headline">{{ state.headline }}</span>
      <span class="fid-tone" :class="status">{{ status === "ok" ? "FRESH" : status === "warn" ? "WARN" : "—" }}</span>
    </button>

    <div v-if="expanded && !isEmpty" class="fid-body">
      <div class="fid-block">
        <span class="mlabel">Transforms applied</span>
        <ol v-if="state.transformCount > 0" class="fid-step-list">
          <li v-for="(t, index) in state.transforms" :key="`${t.name}-${index}`" class="fid-step">
            <span class="fid-step-n">{{ index + 1 }}</span>
            <span class="fid-step-label">{{ t.label }}</span>
            <span class="fid-step-caption">{{ t.caption }}</span>
          </li>
        </ol>
        <div v-else class="fid-identity">
          The series reaches the model as-is — no dtype cast, no flatten, no
          windowing. <b>{{ state.modelInputLength ?? "?" }} values</b> in,
          {{ state.modelInputLength ?? "?" }} values out.
        </div>
      </div>

      <div v-if="messages.length > 0" class="fid-block fid-warnings" role="alert">
        <span class="mlabel">Compatibility issues</span>
        <ul class="fid-warn-list">
          <li v-for="(message, index) in messages" :key="index">{{ message }}</li>
        </ul>
      </div>

      <div v-if="Array.isArray(rawValues) && rawValues.length > 1" class="fid-block">
        <span class="mlabel">Edited vs model-input overlay</span>
        <svg
          class="fid-overlay"
          :viewBox="`0 0 ${SPARK_W} ${SPARK_H}`"
          :width="SPARK_W"
          :height="SPARK_H"
          role="img"
          aria-label="Edited vs model input overlay"
        >
          <path
            class="fid-overlay-raw"
            :d="rawPath"
            fill="none"
            stroke="var(--ink-3)"
            stroke-width="1.6"
            stroke-dasharray="3 3"
            stroke-linejoin="round"
          />
          <path
            v-if="overlayInput && modelPath && !overlayMatches"
            class="fid-overlay-model"
            :d="modelPath"
            fill="none"
            stroke="var(--ink)"
            stroke-width="2"
            stroke-linejoin="round"
            stroke-linecap="round"
          />
        </svg>
        <div class="fid-overlay-legend">
          <span class="fid-leg-key">
            <span class="fid-leg-line dashed" /> edited series
          </span>
          <span class="fid-leg-key">
            <span class="fid-leg-line" />
            model input
            <span v-if="overlayMatches" class="fid-identity-tag">identical to edit</span>
          </span>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.fidelity-strip {
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: var(--bg-bar);
  overflow: hidden;
}
.fidelity-strip.is-warn { border-color: #e8c98f; background: var(--st-warn-bg); }
.fidelity-strip.is-empty { opacity: 0.7; }

.fid-head {
  display: flex;
  align-items: center;
  gap: 9px;
  width: 100%;
  padding: 7px 11px;
  background: none;
  border: none;
  font: inherit;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--ink-2);
  cursor: pointer;
  text-align: left;
}
.fid-head:hover:not([disabled]) { background: var(--bg-hover); }
.fid-head[disabled] { cursor: default; }

.fid-caret {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--ink-3);
  transition: transform 0.15s;
}
.fid-caret.open { transform: rotate(90deg); }

.fid-headline { flex: 1 1 auto; min-width: 0; }

.fid-tone {
  font-family: var(--font-mono);
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.06em;
  border-radius: 3px;
  padding: 1px 6px;
}
.fid-tone.ok { color: #1d6b32; background: var(--st-pass-bg); }
.fid-tone.warn { color: #b3650a; background: var(--st-warn-bg); }
.fid-tone.empty { color: var(--ink-4); background: var(--bg-sunken); }

.fid-body {
  border-top: 1px solid var(--line);
  padding: 9px 11px;
  display: flex;
  flex-direction: column;
  gap: 11px;
  background: var(--bg-panel);
}

.fid-block { display: flex; flex-direction: column; gap: 6px; }
.mlabel {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.13em;
  text-transform: uppercase;
  color: var(--ink-3);
}

.fid-step-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.fid-step {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  background: var(--bg-sunken);
  border: 1px solid var(--line);
  border-radius: var(--r-sm);
  font-size: 11.5px;
}
.fid-step-n {
  font-family: var(--font-mono);
  font-size: 9.5px;
  font-weight: 700;
  background: var(--ink);
  color: #fff;
  border-radius: 3px;
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
}
.fid-step-label { font-weight: 600; color: var(--ink); }
.fid-step-caption {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--ink-3);
}

.fid-identity {
  font-size: 11.5px;
  color: var(--ink-2);
  padding: 6px 8px;
  background: var(--st-pass-bg);
  border: 1px solid var(--line);
  border-radius: var(--r-sm);
  line-height: 1.45;
}
.fid-identity b { color: var(--ink); font-variant-numeric: tabular-nums; }

.fid-warn-list {
  margin: 0;
  padding-left: 16px;
  font-size: 11.5px;
  color: var(--ink-2);
  line-height: 1.5;
}
.fid-warnings { background: var(--st-warn-bg); border: 1px solid #e8c98f; border-radius: var(--r-sm); padding: 7px 9px; }
.fid-warnings .mlabel { color: #b3650a; }

.fid-overlay {
  display: block;
  width: 100%;
  height: auto;
  max-height: 56px;
  background: var(--bg-sunken);
  border: 1px solid var(--line);
  border-radius: var(--r-sm);
}
.fid-overlay-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 10.5px;
  color: var(--ink-3);
}
.fid-leg-key { display: inline-flex; align-items: center; gap: 5px; }
.fid-leg-line {
  display: inline-block;
  width: 16px;
  height: 2px;
  background: var(--ink);
  border-radius: 1px;
}
.fid-leg-line.dashed {
  background: repeating-linear-gradient(
    90deg,
    var(--ink-3) 0,
    var(--ink-3) 3px,
    transparent 3px,
    transparent 6px
  );
  height: 2px;
}
.fid-identity-tag {
  font-family: var(--font-mono);
  font-size: 9.5px;
  color: #1d6b32;
  background: var(--st-pass-bg);
  border-radius: 3px;
  padding: 1px 6px;
}
</style>

<script setup>
import { computed } from "vue";

import { OUTPUT_STATE } from "../../lib/output/createOutputPanelState.js";

const props = defineProps({
  state: { type: Object, required: true },
  artifactLabel: { type: String, default: "" },
});

const emit = defineEmits(["request-prediction", "rerun-prediction"]);

const isEmpty = computed(() => props.state.state === OUTPUT_STATE.EMPTY);
const isLoading = computed(() => props.state.state === OUTPUT_STATE.LOADING);
const isError = computed(() => props.state.state === OUTPUT_STATE.ERROR);
const isStale = computed(() => props.state.state === OUTPUT_STATE.STALE);
const showsBody = computed(() =>
  props.state.state === OUTPUT_STATE.NORMAL || props.state.state === OUTPUT_STATE.STALE,
);

const classification = computed(() => props.state.classification);

function pct(value) {
  if (!Number.isFinite(value)) return "0%";
  return `${Math.round(value * 100)}%`;
}

function signedPp(value) {
  if (!Number.isFinite(value)) return "0";
  const sign = value >= 0 ? "+" : "−";
  return `${sign}${Math.abs(value * 100).toFixed(0)}`;
}

const maxAbsDelta = computed(() => {
  const c = classification.value;
  if (!c) return 0.01;
  const max = c.classes.reduce((acc, row) => Math.max(acc, Math.abs(row.delta)), 0);
  return Math.max(max, 0.01);
});

function deltaBarWidthPct(rowDelta) {
  return (Math.abs(rowDelta) / maxAbsDelta.value) * 48;
}

function deltaColorVar(delta) {
  return delta >= 0 ? "var(--st-pass)" : "var(--st-fail)";
}
</script>

<template>
  <div class="out-panel" aria-label="Model output">
    <header class="out-panel-head">
      <span class="out-panel-title">Prediction</span>
      <span v-if="artifactLabel" class="out-panel-artifact">{{ artifactLabel }}</span>
      <span
        class="fresh-chip"
        :class="`fresh-${state.freshChip.tone}`"
        :aria-label="`Output freshness: ${state.freshChip.label}`"
      >
        <span class="dot" />{{ state.freshChip.label }}
      </span>
    </header>

    <div class="out-panel-body">
      <!-- EMPTY -->
      <div v-if="isEmpty" class="out-state empty" role="status">
        <div class="si">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 3v18h18" />
            <path d="M7 14l3-3 3 2 4-5" />
          </svg>
        </div>
        <div>
          <div class="st-title">No prediction yet</div>
          <div class="st-sub">Request a prediction to lock the baseline and start comparing how edits change the model output.</div>
        </div>
        <button class="out-action primary" type="button" @click="emit('request-prediction')">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>
          Request prediction
        </button>
      </div>

      <!-- ERROR -->
      <div v-else-if="isError" class="out-state error" role="alert">
        <div class="si">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z" />
            <path d="M12 9v4" />
            <path d="M12 17h.01" />
          </svg>
        </div>
        <div>
          <div class="st-title">Prediction failed</div>
          <div class="st-sub">{{ state.error || "The model could not score the current series." }}</div>
        </div>
        <button class="out-action" type="button" @click="emit('rerun-prediction')">Retry</button>
      </div>

      <!-- LOADING -->
      <div v-else-if="isLoading" class="out-grid" aria-busy="true">
        <div v-for="i in 3" :key="i" class="out-block" :class="{ sunken: i === 1, delta: i === 3 }">
          <div class="out-bhd"><span class="skeleton sk-bar" style="width: 64px; height: 9px" /></div>
          <div class="skeleton sk-bar" style="width: 100%" />
          <div class="skeleton sk-bar" style="width: 82%" />
          <div v-if="i === 3" class="skeleton sk-bar" style="width: 60%; height: 22px; margin-top: 6px" />
        </div>
      </div>

      <!-- NORMAL / STALE — both render the body; STALE adds a re-run banner -->
      <template v-else-if="showsBody && classification">
        <div class="stale-veil" :class="{ active: isStale }">
          <div class="out-grid">
            <!-- BASELINE -->
            <div class="out-block sunken">
              <div class="out-bhd">
                <svg class="lock" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="5" y="11" width="14" height="9" rx="2" />
                  <path d="M8 11V7a4 4 0 018 0v4" />
                </svg>
                <span class="mlabel">Baseline · locked</span>
              </div>
              <div class="cls-rows">
                <div
                  v-for="row in classification.classes"
                  :key="`base-${row.name}`"
                  class="cls-row"
                  :class="{ pred: row.name === classification.basePred }"
                >
                  <span class="cls-name">
                    <span v-if="row.name === classification.basePred" class="pdot" />
                    {{ row.name }}
                  </span>
                  <span class="cls-track">
                    <span class="cls-fill" :style="{ width: pct(row.base) }" />
                  </span>
                  <span class="cls-pct">{{ pct(row.base) }}</span>
                </div>
              </div>
            </div>

            <!-- CURRENT -->
            <div class="out-block">
              <div class="out-bhd">
                <span class="mlabel">Current</span>
              </div>
              <div class="cls-rows">
                <div
                  v-for="row in classification.classes"
                  :key="`cur-${row.name}`"
                  class="cls-row"
                  :class="{ pred: row.name === classification.curPred }"
                >
                  <span class="cls-name">
                    <span v-if="row.name === classification.curPred" class="pdot" />
                    {{ row.name }}
                  </span>
                  <span class="cls-track">
                    <span class="cls-fill" :style="{ width: pct(row.cur) }" />
                  </span>
                  <span class="cls-pct">{{ pct(row.cur) }}</span>
                </div>
              </div>
            </div>

            <!-- Δ HERO (full-width across the two columns above) -->
            <div class="out-block delta">
              <div class="out-bhd">
                <span class="mlabel" style="color: var(--accent-ink)">Δ Change</span>
              </div>

              <div v-if="classification.flip" class="flip" role="status">
                <span class="fi">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M16 3l4 4-4 4" />
                    <path d="M20 7H8" />
                    <path d="M8 21l-4-4 4-4" />
                    <path d="M4 17h12" />
                  </svg>
                </span>
                <span class="ft">
                  <span class="fl">CLASS FLIP</span>
                  <span class="fc"><s>{{ classification.basePred }}</s> → {{ classification.curPred }}</span>
                </span>
              </div>
              <div v-else class="no-flip">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M20 6L9 17l-5-5" />
                </svg>
                Predicted class unchanged · <b>{{ classification.curPred }}</b>
              </div>

              <div class="delta-big">
                <span
                  class="dv"
                  :style="{ color: deltaColorVar(classification.predDelta) }"
                >
                  {{ signedPp(classification.predDelta) }}<span class="dv-unit">pp</span>
                </span>
              </div>
              <div class="delta-sub">
                confidence in <b>{{ classification.basePred }}</b> (baseline class)
              </div>

              <div class="dvg">
                <div v-for="row in classification.classes" :key="`d-${row.name}`" class="dvg-row">
                  <span class="dvg-name">{{ row.name }}</span>
                  <span class="dvg-track">
                    <span class="dvg-axis" />
                    <span
                      class="dvg-bar"
                      :style="{
                        background: deltaColorVar(row.delta),
                        left: row.delta >= 0 ? '50%' : `calc(50% - ${deltaBarWidthPct(row.delta)}%)`,
                        width: `${deltaBarWidthPct(row.delta)}%`,
                      }"
                    />
                  </span>
                  <span class="dvg-val" :style="{ color: row.delta >= 0 ? '#1d6b32' : '#a81f1f' }">
                    {{ signedPp(row.delta) }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div v-if="isStale" class="stale-banner" role="status">
            <div class="stale-card">
              <span class="sic">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M12 6v6l4 2" />
                  <path d="M12 22a10 10 0 110-20 10 10 0 010 20z" />
                </svg>
              </span>
              <div class="sct">
                <b>Series edited since last run</b>
                <div class="ss">Output below is outdated. Re-run to score the current series.</div>
              </div>
              <button class="out-action primary" type="button" @click="emit('rerun-prediction')">
                Re-run prediction
              </button>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.out-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
}
.out-panel-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.out-panel-title {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.13em;
  text-transform: uppercase;
  color: var(--accent-ink);
}
.out-panel-artifact {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--ink-3);
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid rgba(43, 74, 214, 0.18);
  border-radius: 3px;
  padding: 1px 6px;
}
.fresh-chip {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.05em;
  padding: 2px 8px;
  border-radius: 999px;
}
.fresh-chip .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
.fresh-ok { color: #1d6b32; background: var(--st-pass-bg); }
.fresh-stale { color: #b3650a; background: var(--st-warn-bg); }
.fresh-none { color: var(--ink-3); background: var(--bg-sunken); }
.fresh-err { color: #a81f1f; background: var(--st-fail-bg); }

.out-panel-body {
  flex: 1 1 auto;
  min-height: 0;
}

/* grid: baseline | current side by side; delta spans full width */
.out-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.out-block {
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  padding: 11px 12px;
  background: rgba(255, 255, 255, 0.70);
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.out-block.sunken { background: rgba(255, 255, 255, 0.45); }
.out-block.delta {
  grid-column: 1 / -1;
  background: linear-gradient(180deg, #fff, #f4f6ff);
  border-color: #c4cdf5;
  box-shadow: inset 0 0 0 1px rgba(43, 74, 214, 0.06);
}
.out-bhd {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 9px;
}
.out-bhd .mlabel {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.13em;
  text-transform: uppercase;
  color: var(--ink-3);
}
.out-bhd .lock { color: var(--ink-4); }

/* classification bars */
.cls-rows { display: flex; flex-direction: column; gap: 7px; }
.cls-row {
  display: grid;
  grid-template-columns: 70px 1fr 44px;
  align-items: center;
  gap: 8px;
}
.cls-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--ink-2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: flex;
  align-items: center;
  gap: 5px;
}
.cls-name .pdot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  flex: none;
}
.cls-row.pred .cls-name { color: var(--ink); font-weight: 700; }
.cls-track {
  height: 9px;
  border-radius: 5px;
  background: var(--bg-hover);
  overflow: hidden;
  border: 1px solid var(--line);
}
.cls-fill {
  height: 100%;
  border-radius: 5px;
  background: var(--ink-4);
  transition: width 0.4s cubic-bezier(0.2, 0.8, 0.3, 1);
}
.cls-row.pred .cls-fill { background: var(--accent); }
.cls-pct {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.cls-row.pred .cls-pct { color: var(--accent-ink); }

/* flip badge */
.flip {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 9px 11px;
  border-radius: var(--r-md);
  background: var(--accent);
  color: #fff;
  margin-bottom: 9px;
  box-shadow: 0 4px 14px -4px rgba(43, 74, 214, 0.5);
}
.flip .fi {
  width: 26px;
  height: 26px;
  border-radius: 7px;
  background: rgba(255, 255, 255, 0.18);
  display: grid;
  place-items: center;
  flex: none;
}
.flip .ft { display: flex; flex-direction: column; line-height: 1.25; min-width: 0; }
.flip .fl {
  font-family: var(--font-mono);
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.12em;
  opacity: 0.85;
}
.flip .fc {
  font-size: 13.5px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 6px;
}
.flip .fc s { text-decoration: none; opacity: 0.7; }

.no-flip {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  color: var(--ink-2);
  padding: 7px 9px;
  border-radius: var(--r-md);
  background: var(--bg-sunken);
  margin-bottom: 9px;
  border: 1px solid var(--line);
}
.no-flip svg { color: var(--st-pass); }

/* delta big number */
.delta-big {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.delta-big .dv {
  font-family: var(--font-mono);
  font-size: 30px;
  font-weight: 600;
  line-height: 1;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
}
.delta-big .dv-unit {
  font-size: 16px;
  margin-left: 2px;
}
.delta-sub { font-size: 11px; color: var(--ink-3); margin-top: 3px; }

/* per-class delta bars */
.dvg { margin-top: 10px; display: flex; flex-direction: column; gap: 5px; }
.dvg-row {
  display: grid;
  grid-template-columns: 70px 1fr 54px;
  align-items: center;
  gap: 7px;
}
.dvg-name {
  font-size: 11px;
  color: var(--ink-2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dvg-track {
  position: relative;
  height: 14px;
}
.dvg-axis {
  position: absolute;
  left: 50%;
  top: -1px;
  bottom: -1px;
  width: 1px;
  background: var(--line-2);
}
.dvg-bar {
  position: absolute;
  top: 3px;
  height: 8px;
  border-radius: 3px;
}
.dvg-val {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

/* empty / error / loading state shells */
.out-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 26px 18px;
  gap: 12px;
  min-height: 150px;
}
.out-state .si {
  width: 42px;
  height: 42px;
  border-radius: 11px;
  display: grid;
  place-items: center;
}
.out-state.empty .si { background: var(--bg-sunken); color: var(--ink-4); }
.out-state.error .si { background: var(--st-fail-bg); color: var(--st-fail); }
.out-state .st-title { font-size: 13.5px; font-weight: 600; }
.out-state .st-sub {
  font-size: 12px;
  color: var(--ink-3);
  max-width: 340px;
  line-height: 1.5;
}

/* skeleton loader */
.skeleton {
  position: relative;
  overflow: hidden;
  background: var(--bg-sunken);
  border-radius: 5px;
}
.skeleton::after {
  content: "";
  position: absolute;
  inset: 0;
  transform: translateX(-100%);
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.65), transparent);
  animation: out-shimmer 1.2s infinite;
}
.sk-bar { height: 9px; margin-bottom: 8px; }
@keyframes out-shimmer {
  100% { transform: translateX(100%); }
}

/* stale overlay */
.stale-veil { position: relative; }
.stale-veil.active .out-grid {
  filter: grayscale(0.55) opacity(0.62);
  pointer-events: none;
}
.stale-banner {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
}
.stale-card {
  background: var(--bg-panel);
  border: 1px solid #e8c98f;
  box-shadow: var(--shadow-pop);
  border-radius: var(--r-lg);
  padding: 13px 16px;
  display: flex;
  align-items: center;
  gap: 13px;
  max-width: 92%;
}
.stale-card .sic {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: var(--st-warn-bg);
  color: var(--st-warn);
  display: grid;
  place-items: center;
  flex: none;
}
.stale-card .sct { line-height: 1.3; }
.stale-card .sct b { font-size: 12.5px; }
.stale-card .sct .ss { font-size: 11px; color: var(--ink-3); }

/* buttons */
.out-action {
  border: 1px solid var(--line-2);
  background: #fff;
  color: var(--ink);
  border-radius: var(--r-sm);
  padding: 6px 12px;
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.out-action:hover { background: var(--bg-hover); border-color: var(--line-strong); }
.out-action.primary {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
.out-action.primary:hover { background: #2340c4; border-color: #2340c4; }
</style>

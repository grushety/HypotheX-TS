<script setup>
import { computed } from "vue";

import { createDeltaProvenanceModel } from "../../lib/provenance/createDeltaProvenanceModel.js";

const props = defineProps({
  provenance: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: null },
  hoveredOpId: { type: String, default: null },
});

const emit = defineEmits(["hover-op", "leave"]);

const model = computed(() => createDeltaProvenanceModel(props.provenance));

function signedPp(value) {
  if (!Number.isFinite(value)) return "0";
  const sign = value >= 0 ? "+" : "−";
  return `${sign}${Math.abs(value * 100).toFixed(1)}`;
}
</script>

<template>
  <section class="dprov" aria-label="Delta sources">
    <header class="dprov-head">
      <span class="mlabel">Δ sources</span>
      <span v-if="loading" class="dprov-status">computing…</span>
      <span v-else-if="error" class="dprov-status error">{{ error }}</span>
      <span
        v-else-if="model.hasData"
        class="dprov-meta"
        :title="model.reference"
      >{{ model.method }}</span>
    </header>

    <div v-if="loading" class="dprov-loading" role="status">
      <span class="spin" aria-hidden="true" />
      Attributing per-op contributions…
    </div>

    <div v-else-if="error" class="dprov-error" role="alert">
      Δ-provenance failed · {{ error }}
    </div>

    <div v-else-if="!model.hasData" class="dprov-empty">
      Apply an operation to see how each edit contributed to the Δ.
    </div>

    <template v-else>
      <div class="dprov-summary">
        Total Δ for <b>{{ model.baselineClass }}</b>:
        <span
          class="dprov-total"
          :class="{ neg: model.totalDelta < 0, pos: model.totalDelta >= 0 }"
        >{{ signedPp(model.totalDelta) }}pp</span>
      </div>
      <ol class="dprov-rows">
        <li
          v-for="row in model.rows"
          :key="row.opId"
          class="dprov-row"
          :class="{
            'dprov-row-residual': row.isResidual,
            'dprov-row-hover': row.opId === hoveredOpId,
          }"
          @mouseenter="emit('hover-op', row.opId)"
          @focus="emit('hover-op', row.opId)"
          @mouseleave="emit('leave')"
          @blur="emit('leave')"
          tabindex="0"
        >
          <span class="dprov-name">{{ row.opLabel }}</span>
          <span class="dprov-bar-wrap" aria-hidden="true">
            <span
              class="dprov-bar"
              :class="row.sign"
              :style="{ width: `${row.barWidthPct}%` }"
            />
          </span>
          <span class="dprov-val" :class="row.sign">{{ signedPp(row.contribution) }}</span>
        </li>
      </ol>
      <p class="dprov-caveat" :title="model.reference">
        Leave-one-out is order-dependent and ignores interactions.
        Residual surfaces what the decomposition can't explain.
      </p>
    </template>
  </section>
</template>

<style scoped>
.dprov {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 9px 10px;
  background: var(--bg-panel);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
}

.dprov-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.mlabel {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.13em;
  text-transform: uppercase;
  color: var(--ink-3);
}
.dprov-status {
  font-size: 11px;
  color: var(--ink-3);
}
.dprov-status.error { color: var(--st-fail); }
.dprov-meta {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 9.5px;
  color: var(--ink-4);
  cursor: help;
}

.dprov-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11.5px;
  color: var(--ink-2);
  padding: 6px 8px;
  background: var(--bg-sunken);
  border-radius: var(--r-sm);
}
.dprov-error {
  font-size: 11.5px;
  color: #b3650a;
  padding: 6px 9px;
  background: var(--st-warn-bg);
  border: 1px solid #e8c98f;
  border-radius: var(--r-sm);
}
.dprov-empty {
  font-size: 11.5px;
  color: var(--ink-3);
  font-style: italic;
}

.dprov-summary { font-size: 12px; color: var(--ink-2); }
.dprov-summary b { color: var(--ink); }
.dprov-total {
  font-family: var(--font-mono);
  font-weight: 700;
  margin-left: 6px;
}
.dprov-total.neg { color: var(--st-fail); }
.dprov-total.pos { color: var(--st-pass); }

.dprov-rows {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.dprov-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 90px 48px;
  align-items: center;
  gap: 8px;
  padding: 4px 6px;
  border-radius: var(--r-sm);
  cursor: default;
  transition: background 0.15s;
}
.dprov-row:hover,
.dprov-row.dprov-row-hover {
  background: var(--bg-hover);
}
.dprov-row:focus {
  outline: 2px solid var(--line-2);
  outline-offset: 0;
}
.dprov-row-residual {
  border-top: 1px dashed var(--line-2);
  margin-top: 3px;
  padding-top: 6px;
  color: var(--ink-3);
}

.dprov-name {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--ink-2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dprov-row-residual .dprov-name { color: var(--ink-3); font-weight: 500; }

.dprov-bar-wrap {
  position: relative;
  height: 6px;
  border-radius: 3px;
  background: var(--bg-hover);
  overflow: hidden;
}
.dprov-bar {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  border-radius: 3px;
}
.dprov-bar.positive { background: var(--st-pass); }
.dprov-bar.negative { background: var(--st-fail); }
.dprov-row-residual .dprov-bar { background: var(--ink-4); }

.dprov-val {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.dprov-val.positive { color: #1d6b32; }
.dprov-val.negative { color: #a81f1f; }
.dprov-row-residual .dprov-val { color: var(--ink-3); }

.dprov-caveat {
  margin: 4px 0 0;
  font-size: 10.5px;
  color: var(--ink-4);
  line-height: 1.45;
  cursor: help;
}
</style>

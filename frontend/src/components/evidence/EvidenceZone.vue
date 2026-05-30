<script setup>
import { computed, ref } from "vue";

import PlausibilityGauges from "./PlausibilityGauges.vue";
import WarningPanel from "../warnings/WarningPanel.vue";
import ConstraintBudgetBar from "../constraints/ConstraintBudgetBar.vue";
import AuditLogPanel from "../audit/AuditLogPanel.vue";

const props = defineProps({
  gaugesState: { type: Object, required: true },
  warning: { type: Object, default: null },
  constraintLaw: { type: String, default: null },
  constraintResult: { type: Object, default: null },
  auditEvents: { type: Array, default: () => [] },
  sessionState: { type: Object, required: true },
  probeFlags: {
    type: Object,
    default: () => ({ saliency: false, deltaSources: false, minFlipSearching: false }),
  },
});

const emit = defineEmits([
  "toggle-saliency",
  "toggle-delta-sources",
  "probe-min-flip",
]);

const detailOpen = ref({
  warning: false,
  guardrails: false,
  audit: false,
  layers: false,
  model: false,
});

function toggle(name) {
  detailOpen.value[name] = !detailOpen.value[name];
}

const warningOpen = computed(() => Boolean(props.warning));
</script>

<template>
  <div class="evz-body">
    <!-- 1. Default-visible: plausibility gauges -->
    <PlausibilityGauges :state="gaugesState" />

    <!-- 2. Probe toggle row — REWORK-07/08/09 wire the behaviour -->
    <section class="evz-probes" aria-label="Probes">
      <div class="evz-probes-head">
        <span class="mlabel">Probes</span>
        <span class="evz-probes-note">REWORK-07 / 08 / 09</span>
      </div>
      <div class="evz-probes-row">
        <button
          type="button"
          class="evz-probe-btn"
          :class="{ on: probeFlags.saliency }"
          :aria-pressed="probeFlags.saliency"
          @click="emit('toggle-saliency')"
        >
          <span class="evz-probe-ic" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="3" />
              <path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z" />
            </svg>
          </span>
          Saliency
        </button>
        <button
          type="button"
          class="evz-probe-btn"
          :class="{ on: probeFlags.deltaSources }"
          :aria-pressed="probeFlags.deltaSources"
          @click="emit('toggle-delta-sources')"
        >
          <span class="evz-probe-ic" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M3 12h18" />
              <path d="M3 6h18" />
              <path d="M3 18h12" />
            </svg>
          </span>
          Δ sources
        </button>
        <button
          type="button"
          class="evz-probe-btn"
          :disabled="probeFlags.minFlipSearching"
          @click="emit('probe-min-flip')"
        >
          <span v-if="probeFlags.minFlipSearching" class="evz-probe-spin" />
          <span v-else class="evz-probe-ic" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M5 12h14" />
              <path d="M12 5l7 7-7 7" />
            </svg>
          </span>
          {{ probeFlags.minFlipSearching ? "Probing…" : "Min-flip" }}
        </button>
      </div>
    </section>

    <!-- 3. Fidelity strip slot — REWORK-05 -->
    <section class="evz-fidelity-slot" aria-label="Model fidelity">
      <slot name="fidelity">
        <div class="evz-fidelity-stub mlabel">"Model sees this" fidelity strip — REWORK-05</div>
      </slot>
    </section>

    <hr class="evz-divider" />

    <!-- 4. Caret sections: warnings + constraint + guardrails + audit + layers + model -->
    <section v-if="warningOpen" class="evz-caret" aria-label="Active warnings">
      <button
        type="button"
        class="evz-caret-head"
        :aria-expanded="detailOpen.warning"
        @click="toggle('warning')"
      >
        <span class="evz-caret-mark" :class="{ open: detailOpen.warning }">▸</span>
        <span class="evz-caret-title">Warnings</span>
        <span class="evz-caret-tag" data-tone="warn">{{ warning?.status ?? "active" }}</span>
      </button>
      <div v-show="detailOpen.warning" class="evz-caret-body">
        <WarningPanel :warning="warning" />
      </div>
    </section>

    <section v-if="constraintLaw" class="evz-caret" aria-label="Constraint detail">
      <button
        type="button"
        class="evz-caret-head"
        :aria-expanded="detailOpen.guardrails"
        @click="toggle('guardrails')"
      >
        <span class="evz-caret-mark" :class="{ open: detailOpen.guardrails }">▸</span>
        <span class="evz-caret-title">Constraint budget · {{ constraintLaw }}</span>
      </button>
      <div v-show="detailOpen.guardrails" class="evz-caret-body">
        <ConstraintBudgetBar
          :law="constraintLaw"
          :compensation-mode="constraintResult?.compensation_mode ?? null"
          :initial-residual="constraintResult?.initial_residual ?? null"
          :final-residual="constraintResult?.final_residual ?? null"
          :tolerance="constraintResult?.tolerance ?? null"
        />
      </div>
    </section>

    <section class="evz-caret" aria-label="Operation history">
      <button
        type="button"
        class="evz-caret-head"
        :aria-expanded="detailOpen.audit"
        @click="toggle('audit')"
      >
        <span class="evz-caret-mark" :class="{ open: detailOpen.audit }">▸</span>
        <span class="evz-caret-title">Operation history</span>
        <span class="evz-caret-tag">{{ sessionState.eventCount }} events</span>
      </button>
      <div v-show="detailOpen.audit" class="evz-caret-body">
        <AuditLogPanel :events="auditEvents" :session="sessionState" />
      </div>
    </section>

    <section class="evz-caret" aria-label="Input layers">
      <button
        type="button"
        class="evz-caret-head"
        :aria-expanded="detailOpen.layers"
        @click="toggle('layers')"
      >
        <span class="evz-caret-mark" :class="{ open: detailOpen.layers }">▸</span>
        <span class="evz-caret-title">Layers</span>
        <span class="evz-caret-tag">stub</span>
      </button>
      <div v-show="detailOpen.layers" class="evz-caret-body evz-caret-stub">
        Input layer manager will land in a follow-up. Today the timeline shows a
        single channel; future revisions will surface saliency / decomposition
        residual / ghost overlays here.
      </div>
    </section>

    <section class="evz-caret" aria-label="Model details">
      <button
        type="button"
        class="evz-caret-head"
        :aria-expanded="detailOpen.model"
        @click="toggle('model')"
      >
        <span class="evz-caret-mark" :class="{ open: detailOpen.model }">▸</span>
        <span class="evz-caret-title">Model</span>
        <span class="evz-caret-tag">stub</span>
      </button>
      <div v-show="detailOpen.model" class="evz-caret-body evz-caret-stub">
        Model card (artifact id, training set, architecture summary, version
        history) will populate from <code>/api/benchmarks/models</code> in a
        follow-up. The same payload already drives the top selector.
      </div>
    </section>
  </div>
</template>

<style scoped>
.evz-body {
  display: flex;
  flex-direction: column;
  gap: 11px;
}

.mlabel {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.13em;
  text-transform: uppercase;
  color: var(--ink-3);
}

/* probes */
.evz-probes { display: flex; flex-direction: column; gap: 6px; }
.evz-probes-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.evz-probes-note {
  font-size: 10.5px;
  color: var(--ink-4);
  font-family: var(--font-mono);
}
.evz-probes-row { display: flex; flex-wrap: wrap; gap: 5px; }
.evz-probe-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border: 1px solid var(--line-2);
  background: var(--bg-panel);
  border-radius: var(--r-sm);
  color: var(--ink-2);
  font: inherit;
  font-size: 11.5px;
  font-weight: 600;
  cursor: pointer;
}
.evz-probe-btn:hover:not([disabled]) {
  background: var(--bg-hover);
  border-color: var(--ink-3);
  color: var(--ink);
}
.evz-probe-btn[disabled] { opacity: 0.55; cursor: progress; }
.evz-probe-btn.on {
  border-color: var(--ink-3);
  color: var(--ink);
  background: var(--bg-hover);
}
.evz-probe-ic { display: inline-grid; place-items: center; }
.evz-probe-ic svg { width: 13px; height: 13px; }
.evz-probe-spin {
  width: 12px;
  height: 12px;
  border: 2px solid var(--line-2);
  border-top-color: var(--ink-2);
  border-radius: 50%;
  animation: evz-spin 0.7s linear infinite;
}
@keyframes evz-spin { to { transform: rotate(360deg); } }

/* fidelity slot */
.evz-fidelity-slot {
  display: flex;
  flex-direction: column;
}
.evz-fidelity-stub {
  padding: 7px 10px;
  border: 1px dashed var(--line-2);
  border-radius: var(--r-md);
  background: var(--bg-bar);
  color: var(--ink-4);
  font-size: 10.5px;
}

/* divider */
.evz-divider {
  border: none;
  border-top: 1px solid var(--line);
  margin: 2px 0;
}

/* caret sections */
.evz-caret {
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: var(--bg-panel);
  overflow: hidden;
}
.evz-caret-head {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 7px 10px;
  background: none;
  border: none;
  font: inherit;
  text-align: left;
  cursor: pointer;
  color: var(--ink-2);
}
.evz-caret-head:hover { background: var(--bg-hover); }
.evz-caret-mark {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--ink-3);
  transition: transform 0.15s;
}
.evz-caret-mark.open { transform: rotate(90deg); }
.evz-caret-title {
  font-size: 12px;
  font-weight: 600;
}
.evz-caret-tag {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  color: var(--ink-3);
  background: var(--bg-sunken);
  border: 1px solid var(--line);
  border-radius: 3px;
  padding: 1px 6px;
}
.evz-caret-tag[data-tone="warn"] {
  color: #b3650a;
  background: var(--st-warn-bg);
  border-color: #e8c98f;
}
.evz-caret-body {
  border-top: 1px solid var(--line);
  padding: 10px 12px;
  background: var(--bg-bar);
}
.evz-caret-stub {
  font-size: 11.5px;
  color: var(--ink-3);
  line-height: 1.5;
}
.evz-caret-stub code {
  font-family: var(--font-mono);
  font-size: 10.5px;
  background: var(--bg-sunken);
  padding: 1px 4px;
  border-radius: 3px;
}
</style>

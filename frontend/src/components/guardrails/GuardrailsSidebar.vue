<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue';

import {
  METRIC_CATALOGUE,
  METRIC_KEYS,
  applyCherryPickingUpdate,
  applyCoverageUpdate,
  applyDiversityUpdate,
  applyForkingPathsUpdate,
  applyValidityUpdate,
  createGuardrailsState,
  dismissPulse,
  resetMetric,
  rowTrafficLight,
  setCollapsed,
  setDock,
  setEnabled,
  setUserThreshold,
  visibleRows,
} from '../../lib/guardrails/createGuardrailsState.js';

import CherryPickingRow from './CherryPickingRow.vue';
import CoverageRow from './CoverageRow.vue';
import DiversityRow from './DiversityRow.vue';
import ForkingPathsRow from './ForkingPathsRow.vue';
import GuardrailsSettings from './GuardrailsSettings.vue';
import ValidityRow from './ValidityRow.vue';

/**
 * Lisnic-style Guardrails sidebar.
 *
 * Subscribes to five validation event-bus topics and renders one row
 * per metric. The state machine (``createGuardrailsState``) handles
 * threshold-cross detection, pulse animation, and the aria-live
 * announcement; this component is the thin Vue shell.
 *
 * Event bus contract: a ``subscribe(topic, handler) → unsubscribe()``
 * function. Optional — when omitted, the panel renders in display-only
 * mode (callers can manually call ``apply*Update`` via the exposed
 * methods if they prefer not to use the bus).
 */
const props = defineProps({
  eventBus: { type: Object, default: null },
  initialDock: { type: String, default: 'right' },
  initialCollapsed: { type: Boolean, default: false },
  userThresholds: { type: Object, default: () => ({}) },
  disabledMetrics: { type: Array, default: () => [] },
});

defineEmits(['threshold-crossed']);

const state = reactive(createGuardrailsState({
  collapsed: props.initialCollapsed,
  dock: props.initialDock,
  userThresholds: props.userThresholds,
  disabledMetrics: props.disabledMetrics,
}));

const settingsOpen = ref(false);

const _APPLIERS = {
  [METRIC_CATALOGUE.coverage.topic]: applyCoverageUpdate,
  [METRIC_CATALOGUE.diversity.topic]: applyDiversityUpdate,
  [METRIC_CATALOGUE.validity.topic]: applyValidityUpdate,
  [METRIC_CATALOGUE.cherryPicking.topic]: applyCherryPickingUpdate,
  [METRIC_CATALOGUE.forkingPaths.topic]: applyForkingPathsUpdate,
};

let _unsubscribers = [];

function _attachBus(bus) {
  if (!bus || typeof bus.subscribe !== 'function') return;
  _unsubscribers = Object.entries(_APPLIERS).map(([topic, applier]) => {
    const handler = payload => applier(state, payload);
    const off = bus.subscribe(topic, handler);
    return typeof off === 'function' ? off : () => bus.unsubscribe?.(topic, handler);
  });
}

onMounted(() => _attachBus(props.eventBus));
onUnmounted(() => {
  _unsubscribers.forEach(off => { try { off(); } catch (_) { /* idempotent */ } });
  _unsubscribers = [];
});

const visible = computed(() => visibleRows(state));

function rowComponent(key) {
  switch (key) {
    case 'coverage': return CoverageRow;
    case 'diversity': return DiversityRow;
    case 'validity': return ValidityRow;
    case 'cherryPicking': return CherryPickingRow;
    case 'forkingPaths': return ForkingPathsRow;
    default: return CoverageRow;
  }
}

function lightFor(key) { return rowTrafficLight(state, key); }

function handleDismiss(key) { dismissPulse(state, key); }

function handleToggleCollapsed() { setCollapsed(state, !state.collapsed); }

function handleDockToggle() {
  setDock(state, state.dock === 'right' ? 'bottom' : 'right');
}

function handleSetEnabled(key, enabled) { setEnabled(state, key, enabled); }
function handleSetThreshold(key, override) { setUserThreshold(state, key, override); }
function handleResetMetric(key) { resetMetric(state, key); }

defineExpose({
  applyCoverageUpdate: payload => applyCoverageUpdate(state, payload),
  applyDiversityUpdate: payload => applyDiversityUpdate(state, payload),
  applyValidityUpdate: payload => applyValidityUpdate(state, payload),
  applyCherryPickingUpdate: payload => applyCherryPickingUpdate(state, payload),
  applyForkingPathsUpdate: payload => applyForkingPathsUpdate(state, payload),
  state,
});
</script>

<template>
  <aside
    class="guardrails-sidebar"
    :class="[`dock-${state.dock}`, { collapsed: state.collapsed }]"
    aria-label="Guardrails sidebar"
  >
    <header class="sidebar-header">
      <button
        type="button"
        class="collapse-toggle"
        @click="handleToggleCollapsed"
        :aria-expanded="!state.collapsed"
      >
        <span aria-hidden="true">{{ state.collapsed ? '▸' : '▾' }}</span>
        <span class="sr-only">{{ state.collapsed ? 'Expand' : 'Collapse' }} guardrails</span>
      </button>
      <h2 class="sidebar-title">Guardrails</h2>
      <button
        type="button"
        class="dock-toggle"
        @click="handleDockToggle"
        :aria-label="`Move panel to ${state.dock === 'right' ? 'bottom' : 'right'}`"
      >
        ⇄
      </button>
      <button
        type="button"
        class="settings-toggle"
        @click="settingsOpen = true"
        aria-label="Open guardrails settings"
      >
        ⚙
      </button>
    </header>

    <div v-show="!state.collapsed" class="sidebar-body">
      <div
        class="aria-live-region"
        role="status"
        aria-live="polite"
      >
        {{ state.announcement || '' }}
      </div>
      <component
        v-for="row in visible"
        :is="rowComponent(row.key)"
        :key="row.key"
        :row="row"
        :traffic-light="lightFor(row.key)"
        @dismiss-pulse="handleDismiss"
      />
    </div>

    <GuardrailsSettings
      :state="state"
      :open="settingsOpen"
      @close="settingsOpen = false"
      @set-enabled="handleSetEnabled"
      @set-threshold="handleSetThreshold"
      @reset-metric="handleResetMetric"
    />
  </aside>
</template>

<style scoped>
.guardrails-sidebar {
  display: flex;
  flex-direction: column;
  background: var(--sidebar-bg, #fff);
  border: 1px solid var(--sidebar-border, #d0d0d0);
  font-family: inherit;
  font-size: 0.85rem;
}
.guardrails-sidebar.dock-right {
  width: 280px;
  height: 100%;
  border-left: 1px solid var(--sidebar-border, #d0d0d0);
}
.guardrails-sidebar.dock-bottom {
  width: 100%;
  height: auto;
  max-height: 220px;
  border-top: 1px solid var(--sidebar-border, #d0d0d0);
}
.guardrails-sidebar.collapsed {
  width: auto;
  max-height: none;
  height: auto;
}
.sidebar-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--sidebar-border, #d0d0d0);
}
.sidebar-title {
  flex: 1;
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
}
.collapse-toggle,
.dock-toggle,
.settings-toggle {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.15rem 0.35rem;
  font-size: 0.85rem;
  border-radius: 4px;
}
.collapse-toggle:hover,
.dock-toggle:hover,
.settings-toggle:hover {
  background: var(--btn-hover-bg, #f0f0f0);
}
.sidebar-body {
  padding: 0.5rem 0.75rem;
  overflow-y: auto;
}
.aria-live-region {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
}
</style>

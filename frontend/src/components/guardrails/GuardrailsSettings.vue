<script setup>
import { computed } from 'vue';

import {
  DEFAULT_USER_THRESHOLDS,
  METRIC_KEYS,
} from '../../lib/guardrails/createGuardrailsState.js';

const props = defineProps({
  state: { type: Object, required: true },
  open: { type: Boolean, default: false },
});

const emit = defineEmits(['close', 'set-enabled', 'set-threshold', 'reset-metric']);

const rows = computed(() => METRIC_KEYS.map(k => ({
  key: k,
  label: props.state.rows[k]?.label ?? k,
  enabled: props.state.rows[k]?.enabled ?? true,
  thresholds: props.state.thresholds[k] ?? {},
  defaults: DEFAULT_USER_THRESHOLDS[k] ?? {},
})));

function toggleEnabled(key, ev) {
  emit('set-enabled', key, ev.target.checked);
}

function updateThresholdField(key, field, ev) {
  const raw = ev.target.value;
  const numeric = Number(raw);
  if (raw === '' || Number.isNaN(numeric)) return;
  emit('set-threshold', key, { [field]: numeric });
}
</script>

<template>
  <div
    v-if="open"
    class="guardrails-settings-backdrop"
    role="dialog"
    aria-modal="false"
    aria-label="Guardrails settings"
  >
    <section class="guardrails-settings-panel">
      <header>
        <h3>Guardrails settings</h3>
        <button type="button" class="close-btn" @click="$emit('close')" aria-label="Close settings">
          ✕
        </button>
      </header>
      <p class="settings-hint">
        Enable or disable individual metrics; override threshold values; reset
        per-metric counters. Lisnic 2025: settings are non-blocking.
      </p>
      <ul class="settings-list">
        <li v-for="row in rows" :key="row.key" class="settings-row">
          <label class="settings-toggle">
            <input
              type="checkbox"
              :checked="row.enabled"
              @change="toggleEnabled(row.key, $event)"
            />
            <span>{{ row.label }}</span>
          </label>
          <div class="settings-threshold-grid">
            <label v-for="field in Object.keys(row.thresholds)" :key="field" class="threshold-field">
              <span class="field-label">{{ field }}</span>
              <input
                type="number"
                step="0.1"
                :value="row.thresholds[field]"
                @input="updateThresholdField(row.key, field, $event)"
              />
            </label>
          </div>
          <button
            type="button"
            class="reset-btn"
            @click="$emit('reset-metric', row.key)"
          >
            Reset counters
          </button>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.guardrails-settings-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.25);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.guardrails-settings-panel {
  background: var(--panel-bg, #fff);
  border-radius: 8px;
  padding: 1rem 1.25rem;
  width: min(420px, 90vw);
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
}
.guardrails-settings-panel header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}
.settings-hint {
  font-size: 0.8rem;
  color: var(--text-muted, #555);
  margin: 0 0 0.75rem;
}
.settings-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.settings-row {
  border-top: 1px solid var(--row-border, #e0e0e0);
  padding: 0.5rem 0;
}
.settings-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  font-weight: 500;
}
.settings-threshold-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.25rem 0.5rem;
  margin: 0.25rem 0;
}
.threshold-field {
  display: flex;
  flex-direction: column;
  font-size: 0.75rem;
  color: var(--text-muted, #555);
}
.threshold-field input {
  font-family: inherit;
  font-size: 0.85rem;
  padding: 0.15rem 0.25rem;
}
.reset-btn,
.close-btn {
  background: none;
  border: 1px solid var(--row-border, #e0e0e0);
  border-radius: 4px;
  padding: 0.15rem 0.5rem;
  cursor: pointer;
  font-size: 0.75rem;
}
.close-btn {
  border: none;
  font-size: 1rem;
}
</style>

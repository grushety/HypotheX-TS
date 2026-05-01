<script setup>
import { computed, nextTick, ref } from 'vue';

import {
  COMPENSATION_MODES,
  createCompensationModeSelectorState,
  nextMode,
} from '../../lib/constraints/createCompensationModeSelectorState.js';

const props = defineProps({
  /** Active domain pack (e.g. `'hydrology'`).  Drives the default mode. */
  domainHint: { type: String, default: null },
  /** Op-category bucket (e.g. `'plateau'`).  Drives the required-mode flag. */
  opCategory: { type: String, default: null },
  /** Currently selected mode (`'naive' | 'local' | 'coupled'`).  v-model. */
  modelValue: { type: String, default: null },
  /** True when the parent treats this op as already user-confirmed. */
  hasExplicitChoice: { type: Boolean, default: null },
  /** Disable interaction (used while the parent op is in flight). */
  disabled: { type: Boolean, default: false },
});

const emit = defineEmits(['update:modelValue', 'change']);

const state = computed(() =>
  createCompensationModeSelectorState({
    domainHint: props.domainHint,
    opCategory: props.opCategory,
    selectedMode: props.modelValue,
    hasExplicitChoice: props.hasExplicitChoice,
  }),
);

const buttonRefs = ref(new Map());

function setButtonRef(mode, el) {
  if (el) buttonRefs.value.set(mode, el);
}

function selectMode(mode) {
  if (props.disabled) return;
  if (mode === state.value.mode) return;
  emit('update:modelValue', mode);
  emit('change', mode);
}

async function focusMode(mode) {
  await nextTick();
  buttonRefs.value.get(mode)?.focus();
}

function handleKeydown(event) {
  if (props.disabled) return;
  switch (event.key) {
    case 'ArrowRight':
    case 'ArrowDown': {
      event.preventDefault();
      const next = nextMode(state.value.mode, +1);
      selectMode(next);
      focusMode(next);
      break;
    }
    case 'ArrowLeft':
    case 'ArrowUp': {
      event.preventDefault();
      const prev = nextMode(state.value.mode, -1);
      selectMode(prev);
      focusMode(prev);
      break;
    }
    case 'Home': {
      event.preventDefault();
      const first = COMPENSATION_MODES[0];
      selectMode(first);
      focusMode(first);
      break;
    }
    case 'End': {
      event.preventDefault();
      const last = COMPENSATION_MODES[COMPENSATION_MODES.length - 1];
      selectMode(last);
      focusMode(last);
      break;
    }
    default:
      break;
  }
}

// NOTE: deliberately no auto-emit on mount.  Emitting the resolved
// default before the user has interacted would make `validSelected`
// truthy on the next render, which sets `hasExplicitChoice = true` and
// flips the required-mode gate to "submittable" — defeating the very
// gating invariant the selector exists to enforce.  Parents that want a
// pre-fill must read `defaultModeForDomain(domainHint)` themselves and
// pre-set the v-model with `hasExplicitChoice: true` if they consider
// that pre-fill an explicit choice (e.g. loaded from a saved session).
//
// CONTRACT WARNING: passing a non-null `modelValue` without also
// passing `hasExplicitChoice: true` will *silently* satisfy the gate
// — the state module treats any valid `selectedMode` as explicit when
// `hasExplicitChoice` is unspecified.  Parents binding `v-model` to a
// field they pre-initialise for *display* must keep that field `null`
// until the user actually clicks, OR pass `hasExplicitChoice: false`
// to opt out.
</script>

<template>
  <div
    class="compensation-mode-selector"
    :class="{
      'compensation-mode-selector--required': state.isRequired,
      'compensation-mode-selector--disabled': disabled,
      'compensation-mode-selector--unconfirmed':
        state.isRequired && !state.hasExplicitChoice,
    }"
  >
    <span class="compensation-mode-selector__label" id="compensation-mode-label">
      Compensation
      <span
        v-if="state.isRequired"
        class="compensation-mode-selector__required-marker"
        aria-hidden="true"
        title="A choice is required for this op"
      >*</span>
    </span>

    <div
      class="compensation-mode-selector__group"
      role="radiogroup"
      aria-labelledby="compensation-mode-label"
      @keydown="handleKeydown"
    >
      <button
        v-for="choice in state.choices"
        :key="choice.mode"
        :ref="(el) => setButtonRef(choice.mode, el)"
        type="button"
        role="radio"
        class="compensation-mode-selector__button"
        :class="{
          'compensation-mode-selector__button--selected': choice.isSelected,
          'compensation-mode-selector__button--recommended': choice.isRecommended,
        }"
        :aria-checked="choice.isSelected ? 'true' : 'false'"
        :tabindex="choice.isSelected ? 0 : -1"
        :title="choice.tooltip"
        :disabled="disabled"
        @click="selectMode(choice.mode)"
      >
        <span class="compensation-mode-selector__button-label">{{ choice.label }}</span>
        <span
          v-if="choice.isRecommended && !choice.isSelected"
          class="compensation-mode-selector__recommended-badge"
          aria-label="Recommended for this domain"
          title="Recommended for this domain"
        >★</span>
      </button>
    </div>

    <p
      v-if="state.isRequired && !state.hasExplicitChoice"
      class="compensation-mode-selector__hint"
    >
      Choose a compensation mode to confirm this op.
    </p>
  </div>
</template>

<style scoped>
.compensation-mode-selector {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 0.85em;
}

.compensation-mode-selector__label {
  font-variant: small-caps;
  letter-spacing: 0.04em;
  font-weight: 600;
}

.compensation-mode-selector__required-marker {
  color: #cf222e;
  margin-left: 2px;
}

.compensation-mode-selector__group {
  display: inline-flex;
  border: 1px solid var(--border-subtle, #d0d7de);
  border-radius: 6px;
  overflow: hidden;
  width: max-content;
}

.compensation-mode-selector--unconfirmed .compensation-mode-selector__group {
  border-color: #cf222e;
}

.compensation-mode-selector__button {
  background: var(--surface, #ffffff);
  border: 0;
  border-right: 1px solid var(--border-subtle, #d0d7de);
  padding: 4px 10px;
  cursor: pointer;
  font: inherit;
  color: inherit;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.compensation-mode-selector__button:last-child {
  border-right: 0;
}

.compensation-mode-selector__button:focus-visible {
  outline: 2px solid var(--focus-ring, #0a3d91);
  outline-offset: -2px;
  z-index: 1;
}

.compensation-mode-selector__button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.compensation-mode-selector__button--selected {
  background: var(--accent, #0a3d91);
  color: #ffffff;
}

.compensation-mode-selector__button--selected:focus-visible {
  outline-color: #ffffff;
}

.compensation-mode-selector__recommended-badge {
  font-size: 0.75em;
  color: #d4a72c;
}

.compensation-mode-selector__button--selected .compensation-mode-selector__recommended-badge {
  color: #ffd54a;
}

.compensation-mode-selector__hint {
  margin: 0;
  font-size: 0.8em;
  color: #cf222e;
}
</style>

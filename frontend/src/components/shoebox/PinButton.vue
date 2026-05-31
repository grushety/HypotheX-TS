<script setup>
import { ref } from "vue";

const props = defineProps({
  ariaLabel: { type: String, default: "Pin to shoebox" },
  disabled: { type: Boolean, default: false },
});

const emit = defineEmits(["pin"]);

const justPinned = ref(false);

function handleClick() {
  if (props.disabled) return;
  emit("pin");
  justPinned.value = true;
  setTimeout(() => {
    justPinned.value = false;
  }, 1100);
}
</script>

<template>
  <button
    type="button"
    class="pin-btn"
    :class="{ pinned: justPinned }"
    :aria-label="ariaLabel"
    :disabled="disabled"
    :title="justPinned ? 'Pinned to shoebox' : ariaLabel"
    @click="handleClick"
  >
    <svg
      v-if="!justPinned"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <path d="M12 17v5" />
      <path d="M9 2h6" />
      <path d="M10 2v6l-3 4v3h10v-3l-3-4V2" />
    </svg>
    <svg
      v-else
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2.4"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <path d="M5 12l5 5L20 7" />
    </svg>
    <span v-if="justPinned" class="pin-toast" aria-live="polite">Pinned</span>
  </button>
</template>

<style scoped>
.pin-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: var(--r-sm);
  border: 1px solid var(--line-2);
  background: var(--bg-panel);
  color: var(--ink-3);
  cursor: pointer;
  padding: 0;
  flex: none;
  transition: all 0.12s;
}
.pin-btn:hover:not(:disabled) {
  background: var(--bg-hover);
  border-color: var(--ink-3);
  color: var(--ink);
}
.pin-btn:disabled { opacity: 0.45; cursor: not-allowed; }
.pin-btn.pinned {
  background: var(--ink);
  border-color: var(--ink);
  color: #fff;
}
.pin-btn svg { width: 13px; height: 13px; }

.pin-toast {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  font-family: var(--font-mono);
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.08em;
  background: var(--ink);
  color: #fff;
  border-radius: 3px;
  padding: 2px 6px;
  white-space: nowrap;
  pointer-events: none;
  animation: pin-toast-in 0.18s ease-out;
}
@keyframes pin-toast-in {
  from { opacity: 0; transform: translateY(-3px); }
}
</style>

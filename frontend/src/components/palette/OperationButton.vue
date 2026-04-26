<script setup>
const props = defineProps({
  op: {
    type: Object,
    required: true,
  },
  enabled: {
    type: Boolean,
    default: false,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  disabledTooltip: {
    type: String,
    default: null,
  },
});

const emit = defineEmits(['invoked']);

function invoke() {
  if (!props.enabled || props.loading) return;
  emit('invoked', { tier: props.op.tier, op_name: props.op.op_name });
}
</script>

<template>
  <button
    class="op-button"
    :class="{
      'op-button-loading': loading,
    }"
    type="button"
    :disabled="!enabled || loading"
    :aria-label="op.label"
    :aria-busy="loading || undefined"
    :title="!enabled && disabledTooltip ? disabledTooltip : undefined"
    @click="invoke"
    @keydown.enter.prevent="invoke"
  >
    <span v-if="loading" class="op-button-spinner" aria-hidden="true" />
    <span v-else-if="op.icon" class="op-button-icon" aria-hidden="true">{{ op.icon }}</span>
    <span class="op-button-label">{{ op.label }}</span>
  </button>
</template>

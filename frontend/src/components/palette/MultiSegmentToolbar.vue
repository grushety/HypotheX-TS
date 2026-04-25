<script setup>
import OperationButton from './OperationButton.vue';

defineProps({
  tier: {
    type: Object,
    required: true,
  },
});

const emit = defineEmits(['op-invoked']);
</script>

<template>
  <div
    class="tier-row tier-row-multi"
    role="toolbar"
    :aria-label="tier.label"
  >
    <span class="tier-label">{{ tier.label }}</span>
    <div class="tier-buttons">
      <OperationButton
        v-for="btn in tier.buttons"
        :key="btn.op_name"
        :op="btn"
        :enabled="btn.enabled"
        :loading="btn.loading"
        @invoked="emit('op-invoked', $event)"
      />
    </div>
  </div>
</template>

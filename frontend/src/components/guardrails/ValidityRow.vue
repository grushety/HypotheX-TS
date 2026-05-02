<script setup>
import GuardrailsRow from './GuardrailsRow.vue';

defineProps({
  row: { type: Object, required: true },
  trafficLight: { type: String, default: 'idle' },
});

defineEmits(['dismiss-pulse']);
</script>

<template>
  <GuardrailsRow
    :row="row"
    :traffic-light="trafficLight"
    @dismiss-pulse="$emit('dismiss-pulse', $event)"
  />
</template>

<script setup>
const props = defineProps({
  row: { type: Object, required: true },
});
const emit = defineEmits(['handle-change', 'reset']);
</script>

<template>
  <div class="decomp-component-editor decomp-linear" :data-component-key="row.componentKey">
    <div class="decomp-component-header">
      <span class="decomp-component-label">{{ row.label }}</span>
      <button
        class="decomp-reset-button"
        type="button"
        @click="emit('reset', row.componentKey)"
      >
        Reset
      </button>
    </div>
    <div class="decomp-handles">
      <label
        v-for="handle in row.handles"
        :key="handle.name"
        class="decomp-handle"
      >
        <span class="decomp-handle-label">{{ handle.label }}</span>
        <input
          class="decomp-slider"
          type="range"
          :min="handle.min"
          :max="handle.max"
          :step="handle.step"
          :value="handle.currentValue"
          @input="emit('handle-change', { componentKey: row.componentKey, handleName: handle.name, value: parseFloat($event.target.value) })"
        />
        <output class="decomp-handle-value">{{ Number(handle.currentValue).toFixed(3) }}</output>
      </label>
    </div>
  </div>
</template>

<script setup>
import { SHAPE_LABELS, getShapeColor } from '../../lib/viewer/shapeColors.js';

const emit = defineEmits(['select', 'close']);
</script>

<template>
  <div
    class="shape-picker"
    role="listbox"
    aria-label="Override shape"
  >
    <button
      v-for="shape in SHAPE_LABELS"
      :key="shape"
      class="shape-picker-option"
      role="option"
      type="button"
      :style="{ borderLeftColor: getShapeColor(shape) }"
      @click="emit('select', shape)"
    >
      {{ shape }}
    </button>
    <button class="shape-picker-cancel" type="button" @click="emit('close')">
      Cancel
    </button>
  </div>
</template>

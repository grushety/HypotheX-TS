<script setup>
defineProps({
  warning: {
    type: Object,
    default: null,
  },
});
</script>

<template>
  <section v-if="warning" class="warning-panel" aria-live="polite" aria-label="Constraint warning">
    <div class="warning-panel-header">
      <div>
        <p class="warning-kicker">Soft constraint</p>
        <h3>{{ warning.title }}</h3>
      </div>
      <span class="warning-status">{{ warning.status }}</span>
    </div>

    <p class="warning-summary">{{ warning.summary }}</p>

    <ul class="warning-reason-list">
      <li v-for="reason in warning.reasons" :key="`${reason.code}-${reason.text}`" class="warning-reason-item">
        {{ reason.text }}
      </li>
    </ul>
  </section>
</template>

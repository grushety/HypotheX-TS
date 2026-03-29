<script setup>
defineProps({
  state: {
    type: Object,
    required: true,
  },
});
</script>

<template>
  <section class="surface comparison-surface" aria-label="Model comparison panel">
    <div class="surface-header">
      <div>
        <p class="section-label">Model comparison</p>
        <h3>{{ state.heading }}</h3>
      </div>
      <span class="surface-tag">{{ state.artifactLabel }}</span>
    </div>

    <p class="comparison-summary">{{ state.message }}</p>

    <ul class="comparison-list">
      <li
        v-for="row in state.rows"
        :key="row.id"
        class="comparison-item"
        :class="{ 'comparison-item-disagreement': row.hasDisagreement }"
      >
        <div>
          <span class="sidebar-label">User</span>
          <strong>{{ row.currentSegment?.label ?? "--" }}</strong>
          <p class="comparison-meta">{{ row.currentRange }}</p>
        </div>
        <div>
          <span class="sidebar-label">Proposal</span>
          <strong>{{ row.proposalSegment?.label ?? "--" }}</strong>
          <p class="comparison-meta">{{ row.proposalRange }}</p>
        </div>
        <div class="comparison-flags">
          <span v-if="row.boundaryChanged" class="comparison-flag">Boundary</span>
          <span v-if="row.labelChanged" class="comparison-flag">Label</span>
          <span v-if="!row.hasDisagreement" class="comparison-flag comparison-flag-match">Match</span>
        </div>
      </li>
    </ul>
  </section>
</template>

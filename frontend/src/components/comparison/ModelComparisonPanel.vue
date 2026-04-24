<script setup>
defineProps({
  state: {
    type: Object,
    required: true,
  },
});

const emit = defineEmits(["request-suggestion", "accept-suggestion", "override-suggestion", "adapt-model", "update-labeler"]);
</script>

<template>
  <section class="surface comparison-surface" aria-label="Model comparison panel">
    <div class="surface-header">
      <div>
        <p class="section-label">Model comparison</p>
        <h3>{{ state.heading }}</h3>
      </div>
      <div class="comparison-header-actions">
        <span class="surface-tag">{{ state.artifactLabel }}</span>
        <div class="comparison-labeler-toggle" role="group" aria-label="Labeler selector">
          <button
            :class="state.selectedLabeler === 'prototype' ? 'comparison-button' : 'comparison-button-secondary'"
            type="button"
            @click="emit('update-labeler', 'prototype')"
          >
            Prototype
          </button>
          <button
            :class="state.selectedLabeler === 'llm' ? 'comparison-button' : 'comparison-button-secondary'"
            type="button"
            @click="emit('update-labeler', 'llm')"
          >
            LLM (Phi-4)
          </button>
        </div>
        <button
          class="comparison-button comparison-button-secondary"
          type="button"
          :disabled="!state.canRequestSuggestion"
          @click="emit('request-suggestion')"
        >
          {{ state.suggestionLoading ? "Loading suggestion..." : "Load suggestion" }}
        </button>
        <button
          class="comparison-button"
          type="button"
          :disabled="!state.canAcceptSuggestion"
          @click="emit('accept-suggestion')"
        >
          Accept suggestion
        </button>
        <button
          class="comparison-button comparison-button-secondary"
          type="button"
          :disabled="!state.canOverrideSuggestion"
          @click="emit('override-suggestion')"
        >
          Override suggestion
        </button>
        <button
          v-if="state.canAdaptModel || state.adaptLoading || state.adaptVersionId || state.adaptError"
          class="comparison-button comparison-button-secondary"
          type="button"
          :disabled="!state.canAdaptModel"
          @click="emit('adapt-model')"
        >
          {{ state.adaptLoading ? "Adapting..." : "Adapt model from corrections" }}
        </button>
        <span v-if="state.adaptVersionId" class="surface-tag">{{ state.adaptVersionId }}</span>
      </div>
    </div>

    <p v-if="state.adaptError" class="comparison-adapt-error">{{ state.adaptError }}</p>

    <p class="comparison-summary">{{ state.message }}</p>

    <p v-if="state.hasProposal && state.suggestionLabeler" class="comparison-summary">
      <span class="surface-tag">via {{ state.suggestionLabeler === "llm" ? "LLM" : "prototype" }}</span>
    </p>

    <ul v-if="state.hasProposal" class="comparison-list">
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

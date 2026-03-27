<script setup>
defineProps({
  entries: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(["export-log"]);
</script>

<template>
  <section class="surface history-surface" aria-label="Interaction history">
    <div class="surface-header">
      <div>
        <p class="section-label">History</p>
        <h3>Recent interactions</h3>
      </div>
      <div class="history-header-actions">
        <span class="surface-tag">{{ entries.length }} entries</span>
        <button class="history-export-button" type="button" :disabled="entries.length === 0" @click="emit('export-log')">
          Export Log
        </button>
      </div>
    </div>

    <p v-if="entries.length === 0" class="history-empty-state">
      Actions will appear here as you edit segments and run operations.
    </p>

    <ol v-else class="history-list">
      <li v-for="entry in entries" :key="entry.id" class="history-item">
        <div class="history-item-header">
          <div>
            <strong>{{ entry.title }}</strong>
            <p class="history-summary">{{ entry.summary }}</p>
          </div>
          <span class="history-status" :class="`history-status-${entry.statusLabel.toLowerCase()}`">
            {{ entry.statusLabel }}
          </span>
        </div>

        <p class="history-meta">
          Entry {{ entry.sequence }}<span v-if="entry.warningCount"> · {{ entry.warningCount }} warning(s)</span>
        </p>

        <p v-if="entry.affectedSegmentIds.length" class="history-meta">
          Segments: {{ entry.affectedSegmentIds.join(", ") }}
        </p>
      </li>
    </ol>
  </section>
</template>

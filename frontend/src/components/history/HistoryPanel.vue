<script setup>
defineProps({
  entries: {
    type: Array,
    default: () => [],
  },
  session: {
    type: Object,
    default: () => ({
      sessionId: "session-unloaded",
      startedAt: null,
      endedAt: null,
      eventCount: 0,
    }),
  },
});

const emit = defineEmits(["export-log"]);
</script>

<template>
  <section class="surface history-surface" aria-label="Session log">
    <div class="surface-header">
      <div>
        <p class="section-label">Session log</p>
        <h3>Chronological actions</h3>
      </div>
      <div class="history-header-actions">
        <span class="surface-tag">{{ session.eventCount }} entries</span>
        <button
          class="history-export-button"
          type="button"
          :disabled="entries.length === 0"
          @click="emit('export-log')"
        >
          Export Session
        </button>
      </div>
    </div>

    <dl class="history-session-summary">
      <div>
        <dt>Session</dt>
        <dd>{{ session.sessionId }}</dd>
      </div>
      <div>
        <dt>Started</dt>
        <dd>{{ session.startedAt ?? "--" }}</dd>
      </div>
      <div>
        <dt>Ended</dt>
        <dd>{{ session.endedAt ?? "--" }}</dd>
      </div>
    </dl>

    <p v-if="entries.length === 0" class="history-empty-state">
      Session actions will appear here as you edit segments and run operations.
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
          Entry {{ entry.sequence }} | {{ entry.timestampLabel }}
          <span v-if="entry.warningCount"> | {{ entry.warningCount }} warning(s)</span>
        </p>

        <p v-if="entry.affectedSegmentIds.length" class="history-meta">
          Segments: {{ entry.affectedSegmentIds.join(", ") }}
        </p>
      </li>
    </ol>
  </section>
</template>

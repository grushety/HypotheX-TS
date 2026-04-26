<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue';

import {
  createAuditLogCsvExport,
  createAuditLogJsonExport,
  createAuditLogPanelState,
} from '../../lib/audit/createAuditLogPanelState.js';
import { labelChipBus } from '../../lib/audit/labelChipBus.js';

const props = defineProps({
  events: {
    type: Array,
    default: () => [],
  },
  session: {
    type: Object,
    default: () => ({ sessionId: null, sampleId: null }),
  },
});

const emit = defineEmits(['export-csv', 'export-json']);

const labelChips = ref([]);
const undoDepth = ref(0);
const selectedRow = ref(null);

// Filters
const filterTier = ref(null);
const filterRuleClass = ref('');
const filterPlausibility = ref('');
const filterOpName = ref('');
const filterDateFrom = ref('');
const filterDateTo = ref('');

// datetime-local inputs produce "YYYY-MM-DDTHH:MM" without timezone; normalise to ISO-8601
// before comparing against event timestamps so string comparison is consistent.
function normaliseDateTime(value) {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

const filters = computed(() => ({
  tier: filterTier.value,
  ruleClass: filterRuleClass.value || null,
  plausibilityBadge: filterPlausibility.value || null,
  opName: filterOpName.value || null,
  dateFrom: normaliseDateTime(filterDateFrom.value),
  dateTo: normaliseDateTime(filterDateTo.value),
}));

const panelState = computed(() =>
  createAuditLogPanelState(props.events, labelChips.value, filters.value, undoDepth.value),
);

function formatCell(value) {
  return value != null ? String(value) : '—';
}

function formatShape(pre, post) {
  if (pre == null && post == null) return '—';
  const preStr = pre ?? '?';
  const postStr = post ?? '?';
  if (preStr === postStr) return preStr;
  return `${preStr} → ${postStr}`;
}

function formatResidual(residual) {
  if (!residual) return '—';
  return JSON.stringify(residual);
}

function handleRowClick(row) {
  selectedRow.value = selectedRow.value?.id === row.id ? null : row;
}

function handleUndo() {
  if (panelState.value.undoable) undoDepth.value += 1;
}

function handleRedo() {
  if (panelState.value.redoable) undoDepth.value -= 1;
}

function downloadFile(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function handleExportCsv() {
  const csv = createAuditLogCsvExport(panelState.value.rows);
  const sampleId = props.session?.sampleId ?? 'session';
  downloadFile(csv, `audit-log-${sampleId}.csv`, 'text/csv');
  emit('export-csv', csv);
}

function handleExportJson() {
  const json = createAuditLogJsonExport(panelState.value.rows, {
    sessionId: props.session?.sessionId ?? null,
    sampleId: props.session?.sampleId ?? null,
  });
  const sampleId = props.session?.sampleId ?? 'session';
  downloadFile(json, `audit-log-${sampleId}.json`, 'application/json');
  emit('export-json', json);
}

function handleClearFilters() {
  filterTier.value = null;
  filterRuleClass.value = '';
  filterPlausibility.value = '';
  filterOpName.value = '';
  filterDateFrom.value = '';
  filterDateTo.value = '';
}

let unsubscribe = null;

onMounted(() => {
  unsubscribe = labelChipBus.subscribe((chip) => {
    labelChips.value = [...labelChips.value, chip];
  });
});

onUnmounted(() => {
  if (unsubscribe) unsubscribe();
});
</script>

<template>
  <section class="surface audit-log-surface" aria-label="Audit log panel">
    <div class="surface-header">
      <div>
        <p class="section-label">Audit log</p>
        <h3>Operation history</h3>
      </div>
      <div class="audit-header-actions">
        <span class="surface-tag">{{ panelState.rows.length }} / {{ panelState.allRows.length }} rows</span>
        <button
          class="audit-action-button"
          type="button"
          :disabled="!panelState.undoable"
          @click="handleUndo"
        >
          Undo
        </button>
        <button
          class="audit-action-button"
          type="button"
          :disabled="!panelState.redoable"
          @click="handleRedo"
        >
          Redo
        </button>
        <button
          class="audit-action-button"
          type="button"
          :disabled="panelState.rows.length === 0"
          @click="handleExportCsv"
        >
          CSV
        </button>
        <button
          class="audit-action-button"
          type="button"
          :disabled="panelState.rows.length === 0"
          @click="handleExportJson"
        >
          JSON
        </button>
      </div>
    </div>

    <!-- Filters -->
    <div class="audit-filters" role="group" aria-label="Log filters">
      <label class="audit-filter-field">
        <span class="audit-filter-label">Tier</span>
        <select
          class="audit-filter-select"
          :value="filterTier"
          @change="filterTier = $event.target.value === '' ? null : Number($event.target.value)"
        >
          <option value="">All</option>
          <option v-for="tier in panelState.filterOptions.tiers" :key="tier" :value="tier">
            Tier {{ tier }}
          </option>
        </select>
      </label>

      <label class="audit-filter-field">
        <span class="audit-filter-label">Rule class</span>
        <select v-model="filterRuleClass" class="audit-filter-select">
          <option value="">All</option>
          <option v-for="rc in panelState.filterOptions.ruleClasses" :key="rc" :value="rc">
            {{ rc }}
          </option>
        </select>
      </label>

      <label class="audit-filter-field">
        <span class="audit-filter-label">Plausibility</span>
        <select v-model="filterPlausibility" class="audit-filter-select">
          <option value="">All</option>
          <option v-for="pb in panelState.filterOptions.plausibilityBadges" :key="pb" :value="pb">
            {{ pb }}
          </option>
        </select>
      </label>

      <label class="audit-filter-field">
        <span class="audit-filter-label">Operation</span>
        <select v-model="filterOpName" class="audit-filter-select">
          <option value="">All</option>
          <option v-for="op in panelState.filterOptions.opNames" :key="op" :value="op">
            {{ op }}
          </option>
        </select>
      </label>

      <label class="audit-filter-field">
        <span class="audit-filter-label">From</span>
        <input
          v-model="filterDateFrom"
          class="audit-filter-input"
          type="datetime-local"
          step="1"
        />
      </label>

      <label class="audit-filter-field">
        <span class="audit-filter-label">To</span>
        <input
          v-model="filterDateTo"
          class="audit-filter-input"
          type="datetime-local"
          step="1"
        />
      </label>

      <button class="audit-action-button" type="button" @click="handleClearFilters">
        Clear
      </button>
    </div>

    <!-- Table -->
    <div class="audit-table-wrapper" role="region" aria-label="Audit log table">
      <p v-if="panelState.allRows.length === 0" class="history-empty-state">
        No operations recorded yet. Edit segments or run operations to populate the log.
      </p>
      <p v-else-if="panelState.rows.length === 0" class="history-empty-state">
        No rows match the current filters.
      </p>
      <table v-else class="audit-table">
        <thead>
          <tr>
            <th scope="col">Timestamp</th>
            <th scope="col">Tier</th>
            <th scope="col">Op</th>
            <th scope="col">Segment</th>
            <th scope="col">Shape</th>
            <th scope="col">Rule class</th>
            <th scope="col">Compensation</th>
            <th scope="col">Plausibility</th>
            <th scope="col">Residual</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in panelState.rows"
            :key="row.id"
            class="audit-row"
            :class="{
              'audit-row-selected': selectedRow?.id === row.id,
              'audit-row-rejected': row.actionStatus === 'rejected',
              'audit-row-warned': row.constraintStatus === 'WARN',
            }"
            @click="handleRowClick(row)"
          >
            <td class="audit-cell audit-cell-timestamp">{{ formatCell(row.timestamp) }}</td>
            <td class="audit-cell audit-cell-tier">
              <span v-if="row.tier != null" class="audit-tier-badge" :class="`audit-tier-${row.tier}`">
                T{{ row.tier }}
              </span>
              <span v-else class="audit-cell-empty">—</span>
            </td>
            <td class="audit-cell audit-cell-op">{{ formatCell(row.op) }}</td>
            <td class="audit-cell audit-cell-segment">{{ formatCell(row.segmentId) }}</td>
            <td class="audit-cell audit-cell-shape">{{ formatShape(row.preShape, row.postShape) }}</td>
            <td class="audit-cell audit-cell-rule">{{ formatCell(row.ruleClass) }}</td>
            <td class="audit-cell audit-cell-compensation">{{ formatCell(row.compensationMode) }}</td>
            <td class="audit-cell audit-cell-plausibility">
              <span
                v-if="row.plausibilityBadge"
                class="audit-plausibility-badge"
                :class="`audit-plausibility-${row.plausibilityBadge}`"
              >
                {{ row.plausibilityBadge }}
              </span>
              <span v-else class="audit-cell-empty">—</span>
            </td>
            <td class="audit-cell audit-cell-residual">{{ formatResidual(row.constraintResidual) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Detail panel (row click) -->
    <div v-if="selectedRow" class="audit-detail-panel" role="region" aria-label="Operation detail">
      <div class="audit-detail-header">
        <p class="section-label">Operation detail</p>
        <button class="audit-action-button" type="button" @click="selectedRow = null">Close</button>
      </div>
      <dl class="audit-detail-grid">
        <div>
          <dt>Op</dt>
          <dd>{{ selectedRow.op ?? '—' }}</dd>
        </div>
        <div>
          <dt>Tier</dt>
          <dd>{{ selectedRow.tier ?? '—' }}</dd>
        </div>
        <div>
          <dt>Segment</dt>
          <dd>{{ selectedRow.segmentId ?? '—' }}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>{{ selectedRow.actionStatus ?? '—' }}</dd>
        </div>
        <div>
          <dt>Constraint</dt>
          <dd>{{ selectedRow.constraintStatus ?? '—' }}</dd>
        </div>
        <div>
          <dt>Shape</dt>
          <dd>{{ formatShape(selectedRow.preShape, selectedRow.postShape) }}</dd>
        </div>
        <div>
          <dt>Rule class</dt>
          <dd>{{ selectedRow.ruleClass ?? '—' }}</dd>
        </div>
        <div>
          <dt>Plausibility</dt>
          <dd>{{ selectedRow.plausibilityBadge ?? '—' }}</dd>
        </div>
      </dl>
      <details class="audit-detail-payload">
        <summary>Full request payload</summary>
        <pre class="audit-detail-pre">{{ JSON.stringify(selectedRow.fullEvent?.request ?? {}, null, 2) }}</pre>
      </details>
      <details v-if="selectedRow.constraintResidual" class="audit-detail-payload">
        <summary>Constraint residual</summary>
        <pre class="audit-detail-pre">{{ JSON.stringify(selectedRow.constraintResidual, null, 2) }}</pre>
      </details>
      <details v-if="selectedRow.fullChip" class="audit-detail-payload">
        <summary>Label chip</summary>
        <pre class="audit-detail-pre">{{ JSON.stringify(selectedRow.fullChip, null, 2) }}</pre>
      </details>
    </div>
  </section>
</template>

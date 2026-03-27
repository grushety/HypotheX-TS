<script setup>
defineProps({
  state: {
    type: Object,
    required: true,
  },
});

const emit = defineEmits([
  "reload",
  "update-dataset",
  "update-artifact",
  "update-split",
  "update-sample-index",
]);
</script>

<template>
  <section class="selector-panel" aria-label="Benchmark selector panel">
    <div class="selector-panel-header">
      <div>
        <p class="section-label">Benchmark selection</p>
        <h2>Dataset and model controls</h2>
      </div>

      <button class="ghost-button" type="button" @click="emit('reload')">Reload options</button>
    </div>

    <p v-if="state.error" class="selector-banner selector-banner-error">{{ state.error }}</p>
    <p
      v-else
      class="selector-banner"
      :class="{
        'selector-banner-loading': state.compatibilityTone === 'loading',
        'selector-banner-ok': state.compatibilityTone === 'ok',
        'selector-banner-warn': state.compatibilityTone === 'warn',
        'selector-banner-error': state.compatibilityTone === 'error',
      }"
    >
      {{ state.compatibilityMessage }}
    </p>

    <div class="selector-grid">
      <label class="selector-field">
        <span class="selector-label">Dataset</span>
        <select
          class="selector-input"
          :value="state.selectedDataset?.name ?? ''"
          :disabled="state.loading || !state.datasetOptions.length"
          @change="emit('update-dataset', $event.target.value)"
        >
          <option value="" disabled>Select dataset</option>
          <option v-for="option in state.datasetOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>

      <label class="selector-field">
        <span class="selector-label">Model</span>
        <select
          class="selector-input"
          :value="state.selectedArtifact?.artifact_id ?? ''"
          :disabled="state.loading || !state.modelOptions.length"
          @change="emit('update-artifact', $event.target.value)"
        >
          <option value="" disabled>Select model</option>
          <option
            v-for="option in state.modelOptions"
            :key="option.value"
            :value="option.value"
            :disabled="option.disabled"
          >
            {{ option.label }}
          </option>
        </select>
      </label>

      <label class="selector-field">
        <span class="selector-label">Split</span>
        <select
          class="selector-input"
          :value="state.selectedSplit"
          :disabled="state.loading || !state.selectedDataset"
          @change="emit('update-split', $event.target.value)"
        >
          <option value="train">Train</option>
          <option value="test">Test</option>
        </select>
      </label>

      <label class="selector-field">
        <span class="selector-label">Sample index</span>
        <input
          class="selector-input"
          type="number"
          min="0"
          :max="state.maxSampleIndex"
          :value="state.sampleIndex"
          :disabled="state.loading || !state.selectedDataset"
          @input="emit('update-sample-index', $event.target.value)"
        />
      </label>
    </div>

    <dl class="selector-summary">
      <div>
        <dt>Samples in split</dt>
        <dd>{{ state.selectedDataset ? state.sampleCount : "--" }}</dd>
      </div>
      <div>
        <dt>Max index</dt>
        <dd>{{ state.selectedDataset ? state.maxSampleIndex : "--" }}</dd>
      </div>
      <div>
        <dt>Series type</dt>
        <dd>{{ state.selectedDataset?.series_type ?? "--" }}</dd>
      </div>
      <div>
        <dt>Selected family</dt>
        <dd>{{ state.selectedArtifact?.display_name ?? "--" }}</dd>
      </div>
    </dl>
  </section>
</template>

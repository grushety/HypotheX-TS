<script setup>
defineProps({
  state: {
    type: Object,
    required: true,
  },
});

const emit = defineEmits(["request-prediction"]);
</script>

<template>
  <section class="prediction-panel" aria-label="Prediction panel">
    <div class="prediction-panel-header">
      <div>
        <p class="section-label">Model inference</p>
        <h2>Prediction panel</h2>
      </div>

      <button
        class="prediction-button"
        type="button"
        :disabled="state.buttonDisabled"
        @click="emit('request-prediction')"
      >
        {{ state.buttonLabel }}
      </button>
    </div>

    <p
      class="prediction-banner"
      :class="{
        'prediction-banner-loading': state.tone === 'loading',
        'prediction-banner-ok': state.tone === 'ok',
        'prediction-banner-warn': state.tone === 'warn',
        'prediction-banner-error': state.tone === 'error',
      }"
    >
      {{ state.message }}
    </p>

    <div class="prediction-grid">
      <section class="prediction-card">
        <p class="section-label">Selected sample</p>
        <dl v-if="state.sampleSummary" class="prediction-summary-list">
          <div>
            <dt>Dataset</dt>
            <dd>{{ state.sampleSummary.datasetName }}</dd>
          </div>
          <div>
            <dt>Sample</dt>
            <dd>{{ state.sampleSummary.sampleId }}</dd>
          </div>
          <div>
            <dt>Split</dt>
            <dd>{{ state.sampleSummary.split }}</dd>
          </div>
          <div>
            <dt>Index</dt>
            <dd>{{ state.sampleSummary.sampleIndex }}</dd>
          </div>
          <div>
            <dt>True label</dt>
            <dd>{{ state.sampleSummary.trueLabel }}</dd>
          </div>
          <div>
            <dt>Series</dt>
            <dd>{{ state.sampleSummary.seriesType }} · {{ state.sampleSummary.channelCount }} ch</dd>
          </div>
        </dl>
        <p v-else class="prediction-empty-state">No sample is loaded yet.</p>
      </section>

      <section class="prediction-card">
        <p class="section-label">Selected model</p>
        <dl v-if="state.modelSummary" class="prediction-summary-list">
          <div>
            <dt>Name</dt>
            <dd>{{ state.modelSummary.displayName }}</dd>
          </div>
          <div>
            <dt>Artifact</dt>
            <dd>{{ state.modelSummary.artifactId }}</dd>
          </div>
          <div>
            <dt>Family</dt>
            <dd>{{ state.modelSummary.family }}</dd>
          </div>
          <div>
            <dt>Dataset</dt>
            <dd>{{ state.modelSummary.dataset }}</dd>
          </div>
        </dl>
        <p v-else class="prediction-empty-state">No model is selected yet.</p>
      </section>
    </div>

    <section class="prediction-results">
      <div class="prediction-results-header">
        <div>
          <p class="section-label">Prediction result</p>
          <h3>{{ state.predictionSummary?.predictedLabel ?? "Awaiting request" }}</h3>
        </div>
        <span class="surface-tag">{{ state.predictionSummary?.scoreCount ?? 0 }} scores</span>
      </div>

      <p v-if="state.predictionSummary" class="prediction-summary-copy">
        Predicted class: <strong>{{ state.predictionSummary.predictedLabel }}</strong>
        <span v-if="state.predictionSummary.trueLabel">
          · true label: <strong>{{ state.predictionSummary.trueLabel }}</strong>
        </span>
      </p>
      <p v-else class="prediction-empty-state">Request a prediction to inspect the normalized model output.</p>

      <ul v-if="state.scores.length" class="prediction-score-list">
        <li v-for="score in state.scores" :key="score.label" class="prediction-score-item">
          <div>
            <p class="prediction-score-label">{{ score.label }}</p>
            <p class="prediction-score-meta">score {{ score.scoreDisplay }}</p>
          </div>
          <strong class="prediction-score-value">{{ score.probabilityDisplay }}</strong>
        </li>
      </ul>
    </section>
  </section>
</template>

function formatProbability(probability) {
  if (!Number.isFinite(probability)) {
    return "--";
  }

  return `${(probability * 100).toFixed(1)}%`;
}

function formatScore(score) {
  if (!Number.isFinite(score)) {
    return "--";
  }

  return score.toFixed(3);
}

function createPredictionScores(scores) {
  if (!Array.isArray(scores)) {
    return [];
  }

  return scores.map((score) => ({
    label: score.label ?? "unknown",
    score: Number.isFinite(score.score) ? score.score : null,
    scoreDisplay: formatScore(Number(score.score)),
    probability: Number.isFinite(score.probability) ? score.probability : null,
    probabilityDisplay: formatProbability(Number(score.probability)),
  }));
}

export function createPredictionPanelState({
  prediction,
  loading,
  error,
  sample,
  selectedArtifact,
  compatibility,
  compatibilityLoading,
  selectorError,
}) {
  const hasSample = Boolean(sample);
  const hasArtifact = Boolean(selectedArtifact);
  const isCompatible = compatibility?.is_compatible !== false;
  const compatibilityMessages = Array.isArray(compatibility?.messages) ? compatibility.messages : [];
  const canRequest =
    hasSample &&
    hasArtifact &&
    !loading &&
    !compatibilityLoading &&
    !selectorError &&
    compatibility?.is_compatible === true;

  let tone = "neutral";
  let message = "Select a dataset and model to request a prediction.";

  if (loading) {
    tone = "loading";
    message = "Running model inference for the selected sample...";
  } else if (error) {
    tone = "error";
    message = error;
  } else if (!hasSample) {
    message = "Load a sample to request a prediction.";
  } else if (!hasArtifact) {
    message = "Select a compatible model to request a prediction.";
  } else if (compatibilityLoading) {
    tone = "loading";
    message = "Checking model compatibility before inference...";
  } else if (selectorError) {
    tone = "error";
    message = selectorError;
  } else if (!isCompatible) {
    tone = "warn";
    message = compatibilityMessages.join(" ") || "The selected dataset and model are not compatible.";
  } else if (prediction) {
    tone = "ok";
    message = "Prediction ready for the selected sample and model.";
  } else {
    tone = "ready";
    message = "Ready to request prediction for the selected sample and model.";
  }

  return {
    tone,
    message,
    buttonLabel: loading ? "Running prediction..." : "Request prediction",
    buttonDisabled: !canRequest,
    canRequest,
    hasPrediction: Boolean(prediction),
    sampleSummary: hasSample
      ? {
          datasetName: sample.datasetName,
          sampleId: sample.sampleId,
          split: sample.sourceSplit,
          sampleIndex: sample.sourceSampleIndex,
          trueLabel: sample.label,
          channelCount: sample.channelCount,
          seriesType: sample.seriesType,
        }
      : null,
    modelSummary: hasArtifact
      ? {
          artifactId: selectedArtifact.artifact_id,
          displayName: selectedArtifact.display_name,
          family: selectedArtifact.family,
          dataset: selectedArtifact.dataset,
        }
      : null,
    predictionSummary: prediction
      ? {
          predictedLabel: prediction.predicted_label,
          trueLabel: prediction.true_label,
          scoreCount: Array.isArray(prediction.scores) ? prediction.scores.length : 0,
        }
      : null,
    scores: createPredictionScores(prediction?.scores),
  };
}

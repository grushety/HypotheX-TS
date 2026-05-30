/**
 * createFidelityStripState — derive the "Model sees this" strip from a
 * prediction response and the project-wide compatibility result.
 *
 * The backend's `PredictionService` is the single source of truth for the
 * input transform chain (REWORK-05 added `transforms` and
 * `model_input_length` to both `/api/benchmarks/prediction` and
 * `/api/benchmarks/predict-values`). This helper does NOT re-implement any
 * transform — it formats the descriptors the service produced.
 *
 * Returned shape:
 *
 *   {
 *     status: "ok" | "warn" | "empty",   // collapsed-strip tone
 *     headline: string,                  // one-line label for the strip
 *     transformCount: number,            // ordered transform list length
 *     transforms: [
 *       {
 *         name: "cast_float64" | "flatten" | ...,
 *         label: string,                 // human-friendly name
 *         caption: string,               // params + shape transition
 *       },
 *       ...
 *     ],
 *     modelInputLength: number | null,
 *     rawInputLength: number | null,
 *     compatibility: {
 *       ok: boolean,
 *       messages: string[],
 *     },
 *   }
 */

const TRANSFORM_LABELS = Object.freeze({
  cast_float64: "Cast to float64",
  flatten: "Flatten to 1-D",
});

function shapeString(shape) {
  if (!Array.isArray(shape) || shape.length === 0) return "()";
  return `(${shape.join(", ")})`;
}

function captionFor(transform) {
  const fromShape = shapeString(transform?.before_shape);
  const toShape = shapeString(transform?.after_shape);
  if (transform?.name === "cast_float64") {
    const from = transform?.params?.from_dtype ?? "?";
    const to = transform?.params?.to_dtype ?? "float64";
    return `dtype ${from} → ${to}`;
  }
  if (transform?.name === "flatten") {
    return `shape ${fromShape} → ${toShape}`;
  }
  if (fromShape !== toShape) return `${fromShape} → ${toShape}`;
  return fromShape;
}

function formatTransform(transform) {
  return {
    name: transform?.name ?? "unknown",
    label: TRANSFORM_LABELS[transform?.name] ?? transform?.name ?? "Unknown transform",
    caption: captionFor(transform),
    beforeShape: Array.isArray(transform?.before_shape) ? transform.before_shape : [],
    afterShape: Array.isArray(transform?.after_shape) ? transform.after_shape : [],
  };
}

export function createFidelityStripState({
  prediction = null,
  compatibility = null,
  rawInputLength = null,
} = {}) {
  const transformsRaw = Array.isArray(prediction?.transforms) ? prediction.transforms : [];
  const transforms = transformsRaw.map(formatTransform);
  const modelInputLength = Number.isFinite(prediction?.model_input_length)
    ? prediction.model_input_length
    : null;

  const compatOk =
    compatibility == null
      ? prediction != null // no compatibility data and we have a prediction → trust the model ran
      : compatibility.is_compatible === true;

  const messages = Array.isArray(compatibility?.messages)
    ? compatibility.messages.filter((message) => typeof message === "string")
    : [];

  // Status discipline: empty when there's nothing to describe (no prediction
  // yet); warn when compatibility flags fired; ok otherwise.
  let status;
  if (prediction == null) {
    status = "empty";
  } else if (!compatOk) {
    status = "warn";
  } else {
    status = "ok";
  }

  const lengthLabel = modelInputLength != null ? `${modelInputLength} values` : "—";
  const transformLabel =
    transforms.length === 0 ? "identity (0 transforms)" : `${transforms.length} transforms`;
  let headline;
  if (status === "empty") {
    headline = "Model sees this · run a prediction to see the transform chain";
  } else if (status === "warn") {
    headline = `Model sees this · ${transformLabel} · ⚠ ${messages.length || "compatibility"} issue${
      messages.length === 1 ? "" : "s"
    }`;
  } else {
    headline = `Model sees this · ${transformLabel} · ✓ compatible · ${lengthLabel}`;
  }

  return {
    status,
    headline,
    transformCount: transforms.length,
    transforms,
    modelInputLength,
    rawInputLength,
    compatibility: { ok: compatOk, messages },
  };
}

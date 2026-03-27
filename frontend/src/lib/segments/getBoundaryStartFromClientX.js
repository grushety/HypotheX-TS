function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

export function getBoundaryStartFromClientX(clientX, rect, seriesLength) {
  if (!rect || rect.width <= 0 || !Number.isInteger(seriesLength) || seriesLength < 2) {
    return 1;
  }

  const ratio = clamp((clientX - rect.left) / rect.width, 0, 1);
  const maxStart = seriesLength - 1;

  return clamp(Math.round(ratio * maxStart), 1, maxStart);
}

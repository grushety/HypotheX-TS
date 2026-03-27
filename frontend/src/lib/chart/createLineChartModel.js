const DEFAULT_WIDTH = 720;
const DEFAULT_HEIGHT = 280;
const DEFAULT_BOUNDS = {
  top: 20,
  right: 18,
  bottom: 42,
  left: 52,
};

function roundLabel(value) {
  return Number.parseFloat(value.toFixed(2)).toString();
}

function createTicks(min, max, count) {
  if (count <= 1 || min === max) {
    return [{ value: min, label: roundLabel(min) }];
  }

  const step = (max - min) / (count - 1);

  return Array.from({ length: count }, (_, index) => {
    const value = min + step * index;

    return {
      value,
      label: roundLabel(value),
    };
  });
}

function toPointString(points) {
  return points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(" ");
}

export function createLineChartModel(values, options = {}) {
  const width = options.width ?? DEFAULT_WIDTH;
  const height = options.height ?? DEFAULT_HEIGHT;
  const bounds = options.bounds ?? DEFAULT_BOUNDS;

  const innerWidth = width - bounds.left - bounds.right;
  const innerHeight = height - bounds.top - bounds.bottom;

  if (!Array.isArray(values) || values.length === 0) {
    return {
      width,
      height,
      bounds: {
        left: bounds.left,
        right: width - bounds.right,
        top: bounds.top,
        bottom: height - bounds.bottom,
      },
      points: [],
      linePath: "",
      areaPath: "",
      xTicks: [],
      yTicks: [],
    };
  }

  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const yMin = minValue === maxValue ? minValue - 1 : minValue;
  const yMax = minValue === maxValue ? maxValue + 1 : maxValue;
  const range = yMax - yMin || 1;

  const scaleX = (index) =>
    bounds.left + (values.length === 1 ? innerWidth / 2 : (index / (values.length - 1)) * innerWidth);
  const scaleY = (value) => bounds.top + ((yMax - value) / range) * innerHeight;

  const points = values.map((value, index) => ({
    index,
    value,
    x: scaleX(index),
    y: scaleY(value),
  }));

  const linePath = toPointString(points);
  const areaPath = `${linePath} L ${points.at(-1).x.toFixed(2)} ${(height - bounds.bottom).toFixed(2)} L ${points[0].x.toFixed(2)} ${(height - bounds.bottom).toFixed(2)} Z`;
  const yTicks = createTicks(yMin, yMax, 4).map((tick) => ({
    ...tick,
    y: scaleY(tick.value),
  }));
  const xTickIndexes = Array.from(new Set([0, Math.floor((values.length - 1) / 2), values.length - 1]));
  const xTicks = xTickIndexes.map((index) => ({
    value: index,
    label: `${index}`,
    x: scaleX(index),
  }));

  return {
    width,
    height,
    bounds: {
      left: bounds.left,
      right: width - bounds.right,
      top: bounds.top,
      bottom: height - bounds.bottom,
    },
    points,
    linePath,
    areaPath,
    xTicks,
    yTicks,
  };
}

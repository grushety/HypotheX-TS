export function createViewerPageState(sample) {
  if (!sample) {
    return {
      statusItems: [
        { label: "Load state", value: "Loading" },
        { label: "Dataset", value: "--" },
        { label: "Series length", value: "--" },
      ],
      sidebarItems: [
        { label: "Benchmark", value: "Waiting for sample" },
        { label: "Task type", value: "--" },
        { label: "Source split", value: "--" },
        { label: "Channels", value: "--" },
        { label: "Segments", value: "--" },
      ],
    };
  }

  return {
    statusItems: [
      { label: "Load state", value: "Ready" },
      { label: "Dataset", value: sample.datasetName },
      { label: "Series length", value: `${sample.seriesLength} points` },
    ],
    sidebarItems: [
      { label: "Benchmark", value: sample.datasetId },
      { label: "Task type", value: sample.taskType },
      { label: "Source split", value: sample.sourceSplit },
      { label: "Channels", value: `${sample.channelCount}` },
      { label: "Segments", value: `${sample.segments?.length ?? 0}` },
    ],
  };
}

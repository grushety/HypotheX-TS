export function createViewerPageState(sample, selectedSegment = null) {
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
        { label: "Active segment", value: "--" },
        { label: "Active label", value: "--" },
        { label: "Active range", value: "--" },
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
      {
        label: "Active segment",
        value: selectedSegment ? `${selectedSegment.label} (${selectedSegment.id})` : "None",
      },
      {
        label: "Active label",
        value: selectedSegment ? selectedSegment.label : "--",
      },
      {
        label: "Active range",
        value: selectedSegment ? `${selectedSegment.start}-${selectedSegment.end}` : "--",
      },
    ],
  };
}

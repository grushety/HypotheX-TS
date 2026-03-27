<script setup>
import { computed, ref } from "vue";

import { AVAILABLE_SEGMENT_LABELS } from "../../lib/segments/updateSegmentLabel";

const props = defineProps({
  selectedSegment: {
    type: Object,
    default: null,
  },
  segments: {
    type: Array,
    default: () => [],
  },
  feedback: {
    type: String,
    default: "",
  },
});

const emit = defineEmits(["run-operation"]);

const splitIndexInput = ref("");
const nextLabel = ref("event");

const selectedIndex = computed(() =>
  props.selectedSegment ? props.segments.findIndex((segment) => segment.id === props.selectedSegment.id) : -1,
);
const leftNeighbor = computed(() =>
  selectedIndex.value > 0 ? props.segments[selectedIndex.value - 1] : null,
);
const rightNeighbor = computed(() =>
  selectedIndex.value >= 0 && selectedIndex.value < props.segments.length - 1
    ? props.segments[selectedIndex.value + 1]
    : null,
);
const mergeLeftDisabled = computed(() => !props.selectedSegment || !leftNeighbor.value);
const mergeRightDisabled = computed(() => !props.selectedSegment || !rightNeighbor.value);

function runSplit() {
  if (!props.selectedSegment || !splitIndexInput.value) {
    return;
  }

  emit("run-operation", {
    type: "split",
    segmentId: props.selectedSegment.id,
    splitIndex: Number.parseInt(splitIndexInput.value, 10),
  });
}

function runMerge(direction) {
  if (!props.selectedSegment) {
    return;
  }

  if (direction === "left" && leftNeighbor.value) {
    emit("run-operation", {
      type: "merge",
      leftSegmentId: leftNeighbor.value.id,
      rightSegmentId: props.selectedSegment.id,
    });
  }

  if (direction === "right" && rightNeighbor.value) {
    emit("run-operation", {
      type: "merge",
      leftSegmentId: props.selectedSegment.id,
      rightSegmentId: rightNeighbor.value.id,
    });
  }
}

function runReclassify() {
  if (!props.selectedSegment) {
    return;
  }

  emit("run-operation", {
    type: "reclassify",
    segmentId: props.selectedSegment.id,
    nextLabel: nextLabel.value,
  });
}
</script>

<template>
  <section class="operation-palette">
    <div class="surface-header">
      <div>
        <p class="section-label">Operations</p>
        <h3>Semantic operation palette</h3>
      </div>
      <span class="surface-tag">{{ selectedSegment ? selectedSegment.id : "Select a segment" }}</span>
    </div>

    <p v-if="feedback" class="operation-feedback">{{ feedback }}</p>

    <div class="operation-group">
      <label class="operation-field">
        <span class="sidebar-label">Split at index</span>
        <input
          v-model="splitIndexInput"
          class="operation-input"
          type="number"
          min="1"
          :disabled="!selectedSegment"
        />
      </label>
      <button class="operation-button" type="button" :disabled="!selectedSegment" @click="runSplit">
        Split
      </button>
    </div>

    <div class="operation-group">
      <button class="operation-button" type="button" :disabled="mergeLeftDisabled" @click="runMerge('left')">
        Merge Left
      </button>
      <button class="operation-button" type="button" :disabled="mergeRightDisabled" @click="runMerge('right')">
        Merge Right
      </button>
    </div>

    <div class="operation-group">
      <label class="operation-field">
        <span class="sidebar-label">Reclassify to</span>
        <select v-model="nextLabel" class="label-editor-select" :disabled="!selectedSegment">
          <option v-for="label in AVAILABLE_SEGMENT_LABELS" :key="label" :value="label">
            {{ label }}
          </option>
        </select>
      </label>
      <button class="operation-button" type="button" :disabled="!selectedSegment" @click="runReclassify">
        Reclassify
      </button>
    </div>
  </section>
</template>

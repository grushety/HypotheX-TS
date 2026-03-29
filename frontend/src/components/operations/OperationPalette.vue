<script setup>
import { computed, ref, watch } from "vue";

import { createManualEditingState } from "../../lib/viewer/createManualEditingState";

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
const nextLabel = ref("");
const editingState = computed(() =>
  createManualEditingState(props.segments, props.selectedSegment),
);

watch(
  () => props.selectedSegment?.id,
  () => {
    splitIndexInput.value = editingState.value.suggestedSplitIndex;
    nextLabel.value = props.selectedSegment?.label ?? editingState.value.relabelOptions[0] ?? "";
  },
  { immediate: true },
);

function runSplit() {
  if (!props.selectedSegment || !splitIndexInput.value || !editingState.value.canSplit) {
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

  if (direction === "left" && editingState.value.leftMergeTarget) {
    emit("run-operation", {
      type: "merge",
      leftSegmentId: editingState.value.leftMergeTarget.id,
      rightSegmentId: props.selectedSegment.id,
    });
  }

  if (direction === "right" && editingState.value.rightMergeTarget) {
    emit("run-operation", {
      type: "merge",
      leftSegmentId: props.selectedSegment.id,
      rightSegmentId: editingState.value.rightMergeTarget.id,
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
        <p class="section-label">Manual editing</p>
        <h3>Split, merge, and relabel</h3>
      </div>
      <span class="surface-tag">{{ editingState.selectedSegmentId ?? "Select a segment" }}</span>
    </div>

    <p v-if="feedback" class="operation-feedback">{{ feedback }}</p>
    <p class="operation-helper-text">{{ editingState.splitHint }}</p>

    <div class="operation-group">
      <label class="operation-field">
        <span class="sidebar-label">Split at index</span>
        <input
          v-model="splitIndexInput"
          class="operation-input"
          type="number"
          :min="editingState.splitMin ?? undefined"
          :max="editingState.splitMax ?? undefined"
          :disabled="!editingState.canSplit"
        />
      </label>
      <button class="operation-button" type="button" :disabled="!editingState.canSplit" @click="runSplit">
        Split
      </button>
    </div>

    <div class="operation-group">
      <button class="operation-button" type="button" :disabled="!editingState.canMergeLeft" @click="runMerge('left')">
        {{ editingState.leftMergeTarget ? `Merge ${editingState.leftMergeTarget.id}` : "Merge Left" }}
      </button>
      <button class="operation-button" type="button" :disabled="!editingState.canMergeRight" @click="runMerge('right')">
        {{ editingState.rightMergeTarget ? `Merge ${editingState.rightMergeTarget.id}` : "Merge Right" }}
      </button>
    </div>

    <div class="operation-group">
      <label class="operation-field">
        <span class="sidebar-label">Relabel to</span>
        <select v-model="nextLabel" class="label-editor-select" :disabled="!selectedSegment">
          <option v-for="label in editingState.relabelOptions" :key="label" :value="label">
            {{ label }}
          </option>
        </select>
      </label>
      <button class="operation-button" type="button" :disabled="!selectedSegment" @click="runReclassify">
        Relabel
      </button>
    </div>
  </section>
</template>

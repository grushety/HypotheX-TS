<script setup>
import { ref, watch } from "vue";

const props = defineProps({
  state: {
    type: Object,
    required: true,
  },
});

const emit = defineEmits(["run-operation"]);

const splitIndexInput = ref("");

watch(
  () => props.state.selectedSegmentId,
  () => {
    splitIndexInput.value = props.state.suggestedSplitIndex;
  },
  { immediate: true },
);

function runSplit() {
  if (!props.state.selectedSegmentId || !splitIndexInput.value || !props.state.canSplit) {
    return;
  }

  emit("run-operation", {
    type: "split",
    segmentId: props.state.selectedSegmentId,
    splitIndex: Number.parseInt(splitIndexInput.value, 10),
  });
}

function runMerge(direction) {
  if (!props.state.selectedSegmentId) {
    return;
  }

  if (direction === "left" && props.state.canMergeLeft) {
    emit("run-operation", {
      type: "merge",
      leftSegmentId: props.state.leftMergeTarget.id,
      rightSegmentId: props.state.selectedSegmentId,
    });
  }

  if (direction === "right" && props.state.canMergeRight) {
    emit("run-operation", {
      type: "merge",
      leftSegmentId: props.state.selectedSegmentId,
      rightSegmentId: props.state.rightMergeTarget.id,
    });
  }
}
</script>

<template>
  <section class="operation-palette">
    <div class="surface-header">
      <div>
        <p class="section-label">Manual editing</p>
        <h3>Semantic operation palette</h3>
      </div>
      <span class="surface-tag">{{ state.selectedSegmentId ?? "Select a segment" }}</span>
    </div>

    <p v-if="state.feedback" class="operation-feedback">{{ state.feedback }}</p>
    <p class="operation-helper-text">{{ state.helperText }}</p>

    <div v-if="state.legalOperations.length" class="operation-legal-list">
      <span
        v-for="operation in state.legalOperations"
        :key="operation.key"
        class="operation-legal-pill"
        :class="{ 'operation-legal-pill-future': !operation.supported }"
      >
        {{ operation.label }}
      </span>
    </div>

    <div v-if="state.showSplit" class="operation-group">
      <label class="operation-field">
        <span class="sidebar-label">Split at index</span>
        <input
          v-model="splitIndexInput"
          class="operation-input"
          type="number"
          :min="state.splitMin ?? undefined"
          :max="state.splitMax ?? undefined"
          :disabled="!state.canSplit"
        />
      </label>
      <button class="operation-button" type="button" :disabled="!state.canSplit" @click="runSplit">
        Split
      </button>
    </div>

    <div v-if="state.showMerge" class="operation-group">
      <button class="operation-button" type="button" :disabled="!state.canMergeLeft" @click="runMerge('left')">
        {{ state.mergeLeftLabel }}
      </button>
      <button class="operation-button" type="button" :disabled="!state.canMergeRight" @click="runMerge('right')">
        {{ state.mergeRightLabel }}
      </button>
    </div>
  </section>
</template>

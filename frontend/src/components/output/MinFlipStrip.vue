<script setup>
import { computed } from "vue";

const props = defineProps({
  result: { type: Object, default: null },
  searching: { type: Boolean, default: false },
  error: { type: String, default: null },
});

const emit = defineEmits(["apply", "clear"]);

const hasResult = computed(() => props.result != null);
const isFound = computed(() => Boolean(props.result?.found));
const distanceLabel = computed(() => {
  if (!isFound.value) return null;
  const d = props.result.distance;
  return typeof d === "number" ? d.toFixed(3) : "—";
});

const touchedLabel = computed(() => {
  if (!isFound.value || !Array.isArray(props.result.edit_values)) return null;
  return props.result.edit_values.length;
});
</script>

<template>
  <section v-if="searching || hasResult || error" class="minflip-strip" aria-label="Minimal flip probe">
    <!-- Searching state -->
    <div v-if="searching" class="minflip-row searching">
      <span class="spin" aria-hidden="true" />
      Searching for the smallest edit that flips the prediction…
    </div>

    <!-- Error -->
    <div v-else-if="error" class="minflip-row error" role="alert">
      <span class="ic" aria-hidden="true">!</span>
      <div class="body">
        <div class="top">Min-flip probe failed</div>
        <div class="sub">{{ error }}</div>
      </div>
      <button type="button" class="btn" @click="emit('clear')">Dismiss</button>
    </div>

    <!-- Found -->
    <div v-else-if="isFound" class="minflip-row found">
      <span class="ic accent" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M5 12h14" />
          <path d="M12 5l7 7-7 7" />
        </svg>
      </span>
      <div class="body">
        <div class="top">
          <b>Minimal flip found</b> ·
          would flip
          <s>{{ result.baseline_class }}</s>
          →
          <b class="flip-target">{{ result.flipped_class }}</b>
        </div>
        <div class="sub">
          distance to decision boundary
          <b class="mono">{{ distanceLabel }}</b>
          (L2) ·
          {{ touchedLabel }} pts touched ·
          ghost shown on canvas
        </div>
        <div v-if="result.reference" class="prov mono">
          {{ result.method }} · {{ result.reference }}
        </div>
      </div>
      <div class="actions">
        <slot name="pin" />
        <button type="button" class="btn primary" @click="emit('apply')">Apply edit</button>
        <button type="button" class="btn" @click="emit('clear')">Clear</button>
      </div>
    </div>

    <!-- Not found (honest reason) -->
    <div v-else class="minflip-row not-found" role="status">
      <span class="ic" aria-hidden="true">∅</span>
      <div class="body">
        <div class="top">No flip reachable within budget</div>
        <div class="sub">{{ result.reason || "The probe could not find a class-flipping edit." }}</div>
      </div>
      <button type="button" class="btn" @click="emit('clear')">Dismiss</button>
    </div>
  </section>
</template>

<style scoped>
.minflip-strip {
  margin-top: 10px;
  border-radius: var(--r-md);
  background: var(--bg-panel);
  border: 1px solid var(--line);
  overflow: hidden;
}

.minflip-row {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 9px 11px;
}
.minflip-row.searching {
  font-size: 12px;
  color: var(--ink-2);
  font-weight: 500;
  background: #f5f7ff;
  border: 1px solid #c4cdf5;
}
.minflip-row.error { background: var(--st-fail-bg); border: 1px solid #e8a6a6; }
.minflip-row.found { background: #f5f7ff; border: 1px solid #c4cdf5; }
.minflip-row.not-found { background: var(--bg-bar); }

.spin {
  width: 13px;
  height: 13px;
  border: 2px solid var(--accent-bg);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: mf-spin 0.6s linear infinite;
}
@keyframes mf-spin { to { transform: rotate(360deg); } }

.ic {
  width: 26px;
  height: 26px;
  border-radius: 7px;
  display: grid;
  place-items: center;
  flex: none;
  background: var(--bg-hover);
  color: var(--ink-3);
  font-weight: 700;
}
.ic.accent { background: var(--accent); color: #fff; }
.ic svg { width: 14px; height: 14px; }
.minflip-row.error .ic { background: var(--st-fail); color: #fff; }

.body { flex: 1; min-width: 0; line-height: 1.4; }
.top { font-size: 12.5px; color: var(--ink-2); }
.top b { color: var(--ink); }
.top s { color: var(--ink-3); }
.top .flip-target { color: var(--accent-ink); }
.sub { font-size: 11px; color: var(--ink-3); margin-top: 2px; }
.sub .mono {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}
.prov {
  font-family: var(--font-mono);
  font-size: 9.5px;
  color: var(--ink-4);
  margin-top: 4px;
}

.actions { display: flex; gap: 6px; flex: none; }
.btn {
  border: 1px solid var(--line-2);
  background: #fff;
  color: var(--ink);
  border-radius: var(--r-sm);
  padding: 5px 11px;
  font: inherit;
  font-size: 11.5px;
  font-weight: 600;
  cursor: pointer;
}
.btn:hover { background: var(--bg-hover); border-color: var(--ink-3); }
.btn.primary {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
.btn.primary:hover { background: #2340c4; border-color: #2340c4; }
</style>

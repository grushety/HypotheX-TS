<script setup>
import { computed } from 'vue';

import { buildBreakdown } from '../../lib/constraints/createConstraintBudgetState.js';

const props = defineProps({
  law: { type: String, required: true },
  components: { type: Object, default: () => ({}) },
  units: { type: String, default: '' },
});

const breakdown = computed(() => buildBreakdown(props.law, props.components, props.units));
</script>

<template>
  <section class="constraint-breakdown" :aria-label="`${law} residual breakdown`">
    <h4 class="constraint-breakdown__title">{{ law }} components</h4>

    <p v-if="!breakdown.supported" class="constraint-breakdown__unsupported">
      No per-component breakdown is available for {{ law }}.
    </p>

    <table v-else class="constraint-breakdown__table">
      <thead>
        <tr>
          <th scope="col">Component</th>
          <th scope="col" class="numeric">Value</th>
          <th scope="col" class="numeric">Sign</th>
          <th scope="col" class="numeric">Contribution</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in breakdown.items" :key="item.key">
          <th scope="row">{{ item.label }}</th>
          <td class="numeric">{{ item.formatted }}</td>
          <td class="numeric">{{ item.sign > 0 ? '+' : '−' }}</td>
          <td class="numeric">{{ item.formattedSigned }}</td>
        </tr>
      </tbody>
      <tfoot>
        <tr>
          <th scope="row">Residual (sum of signed contributions)</th>
          <td colspan="2" />
          <td class="numeric numeric--total">{{ breakdown.formattedTotal }}</td>
        </tr>
      </tfoot>
    </table>
  </section>
</template>

<style scoped>
.constraint-breakdown {
  padding: 8px 12px;
  background: var(--surface-subtle, #f6f8fa);
  border: 1px solid var(--border-subtle, #d0d7de);
  border-radius: 6px;
}
.constraint-breakdown__title {
  font-size: 0.85em;
  margin: 0 0 6px 0;
  font-variant: small-caps;
  letter-spacing: 0.04em;
}
.constraint-breakdown__unsupported {
  margin: 0;
  font-size: 0.85em;
  opacity: 0.7;
}
.constraint-breakdown__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85em;
  font-variant-numeric: tabular-nums;
}
.constraint-breakdown__table th,
.constraint-breakdown__table td {
  padding: 3px 6px;
  text-align: left;
}
.constraint-breakdown__table th[scope="col"] {
  font-size: 0.8em;
  text-transform: uppercase;
  opacity: 0.7;
  border-bottom: 1px solid var(--border-subtle, #d0d7de);
}
.constraint-breakdown__table .numeric {
  text-align: right;
}
.constraint-breakdown__table .numeric--total {
  font-weight: 700;
  border-top: 1px solid var(--border-subtle, #d0d7de);
}
</style>

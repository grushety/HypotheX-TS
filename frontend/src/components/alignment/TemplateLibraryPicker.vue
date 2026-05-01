<script setup>
defineProps({
  templates: { type: Array, default: () => [] },
  selectedTemplateId: { type: String, default: null },
});

const emit = defineEmits(['select-template']);

function handleSelect(templateId) {
  emit('select-template', templateId);
}
</script>

<template>
  <section class="template-library" aria-label="Template library">
    <p class="section-label">Template library</p>
    <ul v-if="templates.length" class="template-library__list">
      <li
        v-for="t in templates"
        :key="t.id"
        class="template-library__item"
        :class="{ 'template-library__item--selected': t.id === selectedTemplateId }"
      >
        <button
          type="button"
          class="template-library__button"
          :aria-pressed="t.id === selectedTemplateId"
          @click="handleSelect(t.id)"
        >
          <strong>{{ t.label ?? t.id }}</strong>
          <span v-if="t.description" class="template-library__desc">
            {{ t.description }}
          </span>
        </button>
      </li>
    </ul>
    <p v-else class="template-library__empty">
      No pre-stored references in this MVP. The picker accepts a list of
      ``{ id, label, values }`` templates whenever a backend route surfaces
      them — wire-up is deferred to a follow-up ticket.
    </p>
  </section>
</template>

<style scoped>
.template-library {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.template-library__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.template-library__button {
  width: 100%;
  font: inherit;
  text-align: left;
  padding: 6px 8px;
  border: 1px solid var(--border-subtle, #d0d7de);
  border-radius: 6px;
  background: var(--surface, #ffffff);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.template-library__item--selected .template-library__button {
  border-color: var(--focus-ring, #0a3d91);
  background: rgba(10, 61, 145, 0.05);
}
.template-library__desc {
  font-size: 0.78rem;
  color: #6b6f8d;
}
.template-library__empty {
  margin: 0;
  padding: 6px 8px;
  border: 1px dashed var(--border-subtle, #d0d7de);
  border-radius: 6px;
  font-size: 0.78rem;
  color: #6b6f8d;
}
</style>

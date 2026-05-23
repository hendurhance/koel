<script setup lang="ts">
defineProps<{
  title?: string
  eyebrow?: string
}>()
</script>

<template>
  <section class="relative border border-hairline bg-surface p-6">
    <header
      v-if="title || eyebrow || $slots.actions"
      class="mb-5 flex items-baseline gap-3 border-b border-hairline pb-3"
    >
      <span
        v-if="eyebrow"
        class="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-muted"
      >
        {{ eyebrow }}
      </span>
      <h3 v-if="title" class="text-sm font-medium text-ink">{{ title }}</h3>
      <div class="ml-auto">
        <slot name="actions" />
      </div>
    </header>
    <slot />
  </section>
</template>

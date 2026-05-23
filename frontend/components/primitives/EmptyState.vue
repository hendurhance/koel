<script setup lang="ts">
defineProps<{
  eyebrow?: string
  title: string
  desc?: string
  cta?: string
}>()
defineEmits<{ (e: 'cta'): void }>()
</script>

<template>
  <div class="grid-bg border border-hairline bg-surface px-6 py-16 text-center">
    <p
      v-if="eyebrow"
      class="mb-3 font-mono text-[10px] uppercase tracking-[0.2em] text-ink-muted"
    >
      {{ eyebrow }}
    </p>
    <h3 class="font-serif text-[28px] leading-tight tracking-tight text-ink">{{ title }}</h3>
    <p
      v-if="desc"
      class="mx-auto mt-3 max-w-md text-[13px] leading-relaxed text-ink-muted"
    >
      {{ desc }}
    </p>
    <button
      v-if="cta"
      type="button"
      class="mt-6 border border-accent bg-accent px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider text-white transition-opacity hover:opacity-90"
      @click="$emit('cta')"
    >
      {{ cta }}
    </button>
  </div>
</template>

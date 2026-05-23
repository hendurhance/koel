<script setup lang="ts">
defineProps<{
  eyebrow: string
  title: string
  desc?: string
}>()
</script>

<template>
  <div class="mx-auto max-w-4xl px-8 py-14">
    <p class="mb-3 font-mono text-[11px] uppercase tracking-[0.2em] text-ink-muted">
      {{ eyebrow }}
    </p>
    <h1 class="font-serif text-[64px] leading-[1.05] tracking-tight text-ink">
      {{ title }}
    </h1>
    <p
      v-if="desc"
      class="mt-6 max-w-md leading-relaxed text-ink-muted"
    >
      {{ desc }}
    </p>

    <div class="grid-bg mt-14 border border-hairline bg-surface p-10 text-center">
      <p class="font-serif text-2xl italic text-ink">wiring soon.</p>
      <p class="mt-2 font-mono text-[11px] uppercase tracking-wider text-ink-muted">
        placeholder — builds in a later step
      </p>
    </div>
  </div>
</template>

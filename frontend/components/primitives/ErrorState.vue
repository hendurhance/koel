<script setup lang="ts">
defineProps<{
  title?: string
  detail?: string
  retryLabel?: string
}>()
defineEmits<{ (e: 'retry'): void }>()
</script>

<template>
  <div class="border border-status-failing/40 bg-surface px-5 py-5">
    <div class="flex items-start gap-4">
      <span class="mt-1 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-status-failing" />
      <div class="min-w-0 flex-1">
        <div class="flex items-baseline gap-2">
          <span class="font-mono text-[10px] uppercase tracking-[0.18em] text-status-failing">
            failed
          </span>
          <span class="text-[13px] font-medium text-ink">
            {{ title ?? 'request failed' }}
          </span>
        </div>
        <p
          v-if="detail"
          class="mt-1 break-words font-mono text-[11px] leading-relaxed text-ink-muted"
        >
          {{ detail }}
        </p>
      </div>
      <button
        type="button"
        class="shrink-0 font-mono text-[11px] uppercase tracking-wider text-status-failing underline-offset-4 hover:underline"
        @click="$emit('retry')"
      >
        {{ retryLabel ?? 'retry →' }}
      </button>
    </div>
  </div>
</template>

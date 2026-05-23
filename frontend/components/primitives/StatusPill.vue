<script setup lang="ts">
type Status =
  | 'ok'
  | 'degraded'
  | 'failing'
  | 'neutral'
  | 'closed'
  | 'half_open'
  | 'open'

const props = defineProps<{
  status: Status
  label?: string
}>()

const display = computed(() => {
  const map: Record<Status, { label: string; color: string; dot: string }> = {
    ok:        { label: 'ok',        color: 'text-status-ok',       dot: 'bg-status-ok' },
    closed:    { label: 'closed',    color: 'text-status-ok',       dot: 'bg-status-ok' },
    degraded:  { label: 'degraded',  color: 'text-status-degraded', dot: 'bg-status-degraded' },
    half_open: { label: 'half-open', color: 'text-status-degraded', dot: 'bg-status-degraded' },
    failing:   { label: 'failing',   color: 'text-status-failing',  dot: 'bg-status-failing' },
    open:      { label: 'open',      color: 'text-accent',          dot: 'bg-accent' },
    neutral:   { label: 'unknown',   color: 'text-ink-muted',       dot: 'bg-ink-muted' },
  }
  return map[props.status]
})
</script>

<template>
  <span
    class="inline-flex items-center gap-1.5 border border-hairline bg-surface px-2 py-0.5 font-mono text-[11px] uppercase tracking-wider leading-none"
  >
    <span class="inline-block h-1.5 w-1.5 rounded-full" :class="display.dot" />
    <span class="pt-px" :class="display.color">{{ label ?? display.label }}</span>
  </span>
</template>

<script setup lang="ts">
/**
 * Hairline-styled shimmer block. Width/height are tailwind classes for easy
 * composition; pass `square` for a hard-edged box, `circle` for an avatar dot.
 */
const props = defineProps<{
  height?: string
  width?: string
  shape?: 'box' | 'circle'
  block?: boolean
}>()

const cls = computed(() => {
  const base = 'skeleton-shimmer relative overflow-hidden bg-surface-2'
  const shape = props.shape === 'circle' ? 'rounded-full' : ''
  const display = props.block ? 'block' : 'inline-block'
  return [base, shape, display, props.height ?? 'h-4', props.width ?? 'w-full']
})
</script>

<template>
  <span :class="cls" aria-hidden="true" />
</template>

<style scoped>
.skeleton-shimmer::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    var(--color-hairline) 50%,
    transparent 100%
  );
  opacity: 0.6;
  transform: translateX(-100%);
  animation: shimmer 1400ms ease-in-out infinite;
}
@keyframes shimmer {
  to { transform: translateX(100%); }
}
</style>

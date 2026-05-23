<script setup lang="ts">
import Icon from './Icon.vue'

const props = defineProps<{
  to: string
  icon: string
  label: string
  collapsed?: boolean
}>()

// `/` must exact-match so it doesn't highlight for every subroute.
const activeClass = computed(() => (props.to === '/' ? '' : 'rail-active'))
const exactActiveClass = computed(() => (props.to === '/' ? 'rail-active' : ''))
</script>

<template>
  <NuxtLink
    :to="to"
    :active-class="activeClass"
    :exact-active-class="exactActiveClass"
    :title="collapsed ? label : undefined"
    class="group relative flex items-center gap-3 px-3 py-2 text-ink-muted transition-colors duration-[80ms] hover:bg-surface-2 hover:text-ink"
    :class="collapsed ? 'justify-center' : ''"
  >
    <span class="rail-indicator absolute left-0 top-1/2 h-0 w-px -translate-y-1/2 bg-transparent transition-[height,background] duration-150" />
    <Icon :name="icon" class="h-4 w-4 shrink-0" />
    <span
      v-if="!collapsed"
      class="text-[13px] leading-none"
    >
      {{ label }}
    </span>
  </NuxtLink>
</template>

<style scoped>
.rail-active {
  color: var(--color-ink);
  background: var(--color-surface-2);
}
.rail-active .rail-indicator {
  background: var(--color-accent);
  height: 1rem;
}
</style>

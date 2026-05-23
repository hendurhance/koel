<script setup lang="ts">
import Skeleton from './Skeleton.vue'

const props = defineProps<{
  count?: number
  cols?: number[]
}>()

const rows = computed(() => Array.from({ length: props.count ?? 6 }))
const widths = computed(() => props.cols ?? [40, 28, 16, 12])
</script>

<template>
  <ul class="divide-y divide-hairline border border-hairline bg-surface">
    <li v-for="(_, i) in rows" :key="i" class="grid items-center gap-4 px-4 py-3.5"
        :style="{ gridTemplateColumns: widths.map((w) => `${w}fr`).join(' ') }">
      <Skeleton v-for="(w, j) in widths" :key="j" block height="h-3" :width="`w-${j === 0 ? 'full' : 'full'}`" />
    </li>
  </ul>
</template>

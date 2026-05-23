<script setup lang="ts" generic="T extends Record<string, any>">
type Align = 'left' | 'right'
type Column = {
  key: keyof T & string
  label: string
  align?: Align
  width?: string
  mono?: boolean
}

defineProps<{
  columns: Column[]
  rows: T[]
  rowKey?: keyof T & string
  empty?: string
}>()
</script>

<template>
  <div class="border border-hairline bg-surface">
    <table class="w-full border-collapse text-sm">
      <thead>
        <tr class="border-b border-hairline">
          <th
            v-for="col in columns"
            :key="col.key"
            :style="{ width: col.width, textAlign: col.align ?? 'left' }"
            class="px-4 py-2.5 font-mono text-[10px] font-medium uppercase tracking-[0.14em] text-ink-muted"
          >
            {{ col.label }}
          </th>
        </tr>
      </thead>
      <tbody class="stagger-in">
        <tr v-if="!rows.length">
          <td
            :colspan="columns.length"
            class="px-4 py-16 text-center text-ink-muted"
          >
            {{ empty ?? 'no rows' }}
          </td>
        </tr>
        <tr
          v-for="(row, i) in rows"
          :key="rowKey ? String(row[rowKey]) : i"
          class="border-t border-hairline transition-colors duration-[80ms] ease-out hover:bg-surface-2"
        >
          <td
            v-for="col in columns"
            :key="col.key"
            :style="{ textAlign: col.align ?? 'left' }"
            class="px-4 py-3 tabular-nums"
            :class="col.mono ? 'font-mono text-[13px]' : ''"
          >
            <slot
              :name="`cell-${col.key}`"
              :row="row"
              :value="row[col.key]"
            >
              {{ row[col.key] }}
            </slot>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

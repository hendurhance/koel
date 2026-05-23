<script setup lang="ts">
type Currency = { code: string; name: string; symbol?: string | null }

const props = defineProps<{
  modelValue: string
  currencies: Currency[]
  label?: string
  disabled?: boolean
}>()
const emit = defineEmits<{
  (e: 'update:modelValue', code: string): void
}>()

const open = ref(false)
const query = ref('')
const highlight = ref(0)
const rootEl = ref<HTMLDivElement | null>(null)
const inputEl = ref<HTMLInputElement | null>(null)

const selected = computed(() =>
  props.currencies.find((c) => c.code === props.modelValue) ?? null,
)

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  const list = props.currencies
  if (!q) return list
  return list.filter(
    (c) => c.code.toLowerCase().includes(q) || c.name.toLowerCase().includes(q),
  )
})

watch(open, async (v) => {
  if (!v) return
  query.value = ''
  const idx = filtered.value.findIndex((c) => c.code === props.modelValue)
  highlight.value = idx >= 0 ? idx : 0
  await nextTick()
  inputEl.value?.focus()
})

watch(filtered, () => {
  highlight.value = 0
})

const choose = (code: string) => {
  if (code === props.modelValue) {
    open.value = false
    return
  }
  emit('update:modelValue', code)
  open.value = false
}

const onKey = (e: KeyboardEvent) => {
  if (!open.value) return
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    highlight.value = Math.min(highlight.value + 1, filtered.value.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    highlight.value = Math.max(highlight.value - 1, 0)
  } else if (e.key === 'Enter') {
    e.preventDefault()
    const pick = filtered.value[highlight.value]
    if (pick) choose(pick.code)
  } else if (e.key === 'Escape') {
    e.preventDefault()
    open.value = false
  }
}

const onDocClick = (e: MouseEvent) => {
  if (!open.value) return
  if (rootEl.value && !rootEl.value.contains(e.target as Node)) open.value = false
}

onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))
</script>

<template>
  <div ref="rootEl" class="relative inline-block" @keydown="onKey">
    <label
      v-if="label"
      class="mb-1.5 block font-mono text-[10px] uppercase tracking-[0.18em] text-ink-muted"
    >
      {{ label }}
    </label>

    <button
      type="button"
      :disabled="disabled"
      class="flex min-w-[240px] items-center justify-between gap-3 border border-hairline bg-surface px-3 py-2.5 text-left transition-colors hover:border-ink focus:border-accent focus:outline-none disabled:opacity-50"
      :class="open ? 'border-accent' : ''"
      @click="open = !open"
    >
      <span class="flex items-baseline gap-2 truncate">
        <span class="font-mono text-[13px] font-medium">{{ selected?.code ?? '—' }}</span>
        <span class="truncate text-[13px] text-ink-muted">{{ selected?.name ?? 'select currency' }}</span>
      </span>
      <span
        class="font-mono text-[10px] text-ink-muted transition-transform"
        :class="open ? 'rotate-180' : ''"
      >
        ▾
      </span>
    </button>

    <div
      v-if="open"
      class="absolute z-30 mt-1 w-[340px] border border-hairline bg-surface shadow-[0_0_0_1px_rgba(0,0,0,0.02)]"
    >
      <div class="border-b border-hairline p-2">
        <input
          ref="inputEl"
          v-model="query"
          type="text"
          placeholder="search code or name…"
          class="w-full bg-transparent px-2 py-1 font-mono text-[12px] text-ink placeholder:text-ink-muted focus:outline-none"
        />
      </div>
      <ul class="max-h-72 overflow-y-auto">
        <li
          v-if="!filtered.length"
          class="px-3 py-3 font-mono text-[11px] uppercase tracking-wider text-ink-muted"
        >
          no match
        </li>
        <li
          v-for="(c, i) in filtered"
          :key="c.code"
          class="flex cursor-pointer items-baseline gap-3 px-3 py-2 transition-colors"
          :class="[
            i === highlight ? 'bg-surface-2' : '',
            c.code === modelValue ? 'text-accent' : '',
          ]"
          @mouseenter="highlight = i"
          @click="choose(c.code)"
        >
          <span class="font-mono text-[12px] font-medium">{{ c.code }}</span>
          <span class="truncate text-[12px] text-ink-muted">{{ c.name }}</span>
        </li>
      </ul>
    </div>
  </div>
</template>

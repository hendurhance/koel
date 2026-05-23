<script setup lang="ts">
import Icon from './Icon.vue'

type Entry = { label: string; hint: string; to: string; icon: string }

const { isOpen, close } = useCommandPalette()
const router = useRouter()

const entries: Entry[] = [
  { label: 'overview',   hint: 'dashboard home',             to: '/',           icon: 'overview' },
  { label: 'rates',      hint: 'current & historical rates', to: '/rates',      icon: 'rates' },
  { label: 'currencies', hint: 'all configured currencies',  to: '/currencies', icon: 'currencies' },
  { label: 'sources',    hint: 'scrape source health',       to: '/sources',    icon: 'sources' },
  { label: 'keys',       hint: 'api keys & groups',          to: '/keys',       icon: 'keys' },
  { label: 'usage',      hint: 'request analytics',          to: '/usage',      icon: 'usage' },
  { label: 'account',    hint: 'profile & session',          to: '/account',    icon: 'account' },
]

const query = ref('')
const active = ref(0)
const inputRef = ref<HTMLInputElement | null>(null)

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return entries
  return entries.filter((e) => e.label.includes(q) || e.hint.includes(q))
})

watch(filtered, () => { active.value = 0 })
watch(isOpen, async (v) => {
  if (!v) return
  query.value = ''
  active.value = 0
  await nextTick()
  inputRef.value?.focus()
})

const select = (i: number) => {
  const entry = filtered.value[i]
  if (!entry) return
  close()
  router.push(entry.to)
}

const onKey = (e: KeyboardEvent) => {
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    active.value = filtered.value.length
      ? (active.value + 1) % filtered.value.length
      : 0
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    active.value = filtered.value.length
      ? (active.value - 1 + filtered.value.length) % filtered.value.length
      : 0
  } else if (e.key === 'Enter') {
    e.preventDefault()
    select(active.value)
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="duration-150 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="duration-100 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="isOpen"
        class="fixed inset-0 z-50 flex items-start justify-center bg-ink/25 px-4 pt-[18vh] backdrop-blur-[8px]"
        @click.self="close"
      >
        <div
          class="palette-panel w-full max-w-xl border border-hairline bg-surface"
          @keydown="onKey"
        >
          <div class="flex items-center gap-3 border-b border-hairline px-4 py-3">
            <Icon name="search" class="h-4 w-4 text-ink-muted" />
            <input
              ref="inputRef"
              v-model="query"
              type="text"
              placeholder="jump to…"
              class="flex-1 bg-transparent text-sm text-ink placeholder:text-ink-muted focus:outline-none"
            />
            <kbd class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
              esc
            </kbd>
          </div>

          <div class="max-h-[52vh] overflow-y-auto py-1">
            <button
              v-for="(entry, i) in filtered"
              :key="entry.to"
              type="button"
              class="flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors"
              :class="i === active ? 'bg-surface-2' : ''"
              @click="select(i)"
              @mouseenter="active = i"
            >
              <Icon :name="entry.icon" class="h-4 w-4 shrink-0 text-ink-muted" />
              <span class="text-sm text-ink">{{ entry.label }}</span>
              <span class="text-xs text-ink-muted">— {{ entry.hint }}</span>
              <span
                v-if="i === active"
                class="ml-auto font-mono text-[10px] uppercase tracking-wider text-accent"
              >
                ↵
              </span>
            </button>

            <div
              v-if="!filtered.length"
              class="px-4 py-10 text-center font-mono text-[11px] uppercase tracking-wider text-ink-muted"
            >
              no matches
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.palette-panel {
  animation: palette-in 180ms ease-out;
}
@keyframes palette-in {
  from {
    opacity: 0;
    transform: scale(0.97) translateY(-4px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
</style>

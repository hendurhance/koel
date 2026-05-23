<script setup lang="ts">
import Icon from './Icon.vue'

const { theme, toggle: toggleTheme } = useTheme()
const auth = useAuthStore()
const palette = useCommandPalette()

// Static for now — wire to runtimeConfig.public once we deploy more envs.
const env = 'local' as 'local' | 'staging' | 'prod'
const envTone = computed(() => {
  switch (env) {
    case 'prod':    return { dot: 'bg-accent',             text: 'text-accent' }
    case 'staging': return { dot: 'bg-status-degraded',    text: 'text-status-degraded' }
    default:        return { dot: 'bg-status-ok',          text: 'text-status-ok' }
  }
})

const doLogout = async () => {
  await auth.logout()
  await navigateTo('/login')
}

const isMac = computed(() =>
  import.meta.client && /Mac|iPhone|iPad/.test(navigator.platform),
)
</script>

<template>
  <header class="sticky top-0 z-10 flex h-14 items-center gap-3 border-b border-hairline bg-surface px-4">
    <div class="flex min-w-0 items-center gap-2">
      <span class="truncate font-mono text-[12px] text-ink">
        {{ auth.user?.email ?? '—' }}
      </span>
      <span
        v-if="auth.isAdmin"
        class="border border-accent/40 px-1.5 py-0.5 font-mono text-[9px] uppercase leading-none tracking-wider text-accent"
      >
        admin
      </span>
    </div>

    <span class="flex items-center gap-1.5 border border-hairline px-2 py-1 font-mono text-[10px] uppercase leading-none tracking-wider">
      <span class="inline-block h-1.5 w-1.5 rounded-full" :class="envTone.dot" />
      <span :class="envTone.text">{{ env }}</span>
    </span>

    <div class="flex-1" />

    <button
      type="button"
      class="flex items-center gap-2 border border-hairline px-2.5 py-1.5 font-mono text-[11px] text-ink-muted transition-colors hover:border-ink-muted hover:text-ink"
      @click="palette.open"
    >
      <Icon name="search" class="h-3.5 w-3.5" />
      <span>search</span>
      <kbd class="ml-4 flex items-center gap-0.5 text-[10px] text-ink-muted">
        <span>{{ isMac ? '⌘' : 'ctrl' }}</span>
        <span v-if="!isMac">+</span>
        <span>K</span>
      </kbd>
    </button>

    <button
      type="button"
      class="flex h-8 w-8 items-center justify-center border border-hairline text-ink-muted transition-colors hover:border-ink-muted hover:text-ink"
      :aria-label="`switch to ${theme === 'dark' ? 'light' : 'dark'} theme`"
      @click="toggleTheme"
    >
      <Icon :name="theme === 'dark' ? 'sun' : 'moon'" class="h-3.5 w-3.5" />
    </button>

    <button
      type="button"
      class="flex h-8 w-8 items-center justify-center border border-hairline text-ink-muted transition-colors hover:border-ink-muted hover:text-ink"
      aria-label="sign out"
      @click="doLogout"
    >
      <Icon name="logout" class="h-3.5 w-3.5" />
    </button>
  </header>
</template>

<script setup lang="ts">
import Logo from '~/components/chrome/Logo.vue'

const { theme, toggle, load } = useTheme()
onMounted(load)
</script>

<template>
  <div class="noise relative min-h-screen bg-surface text-ink">
    <div class="relative z-10 mx-auto flex min-h-screen max-w-lg flex-col px-8 py-10">
      <header class="mb-auto flex items-baseline justify-between">
        <span class="flex items-center gap-2">
          <Logo class="h-4 w-4 text-accent" />
          <span class="font-mono text-xs uppercase tracking-[0.2em] text-ink">koel</span>
        </span>
        <button
          type="button"
          class="font-mono text-[11px] uppercase tracking-wider text-ink-muted transition-colors hover:text-accent"
          @click="toggle"
        >
          [{{ theme }}]
        </button>
      </header>

      <main class="my-auto">
        <slot />
      </main>

      <footer class="mt-auto pt-10 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-muted">
        <span>koel · exchange-rate api</span>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import LeftRail from '~/components/chrome/LeftRail.vue'
import TopBar from '~/components/chrome/TopBar.vue'
import CommandPalette from '~/components/chrome/CommandPalette.vue'
import ToastStack from '~/components/chrome/ToastStack.vue'

const { load } = useTheme()
const palette = useCommandPalette()

let keyHandler: ((e: KeyboardEvent) => void) | null = null

onMounted(() => {
  load()
  keyHandler = (e: KeyboardEvent) => {
    const isMod = e.metaKey || e.ctrlKey
    if (isMod && e.key.toLowerCase() === 'k') {
      e.preventDefault()
      palette.toggle()
    } else if (e.key === 'Escape' && palette.isOpen.value) {
      palette.close()
    }
  }
  window.addEventListener('keydown', keyHandler)
})

onBeforeUnmount(() => {
  if (keyHandler) window.removeEventListener('keydown', keyHandler)
})
</script>

<template>
  <div class="noise relative min-h-screen bg-surface text-ink">
    <div class="relative z-10 flex min-h-screen">
      <LeftRail />
      <div class="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main class="flex-1">
          <slot />
        </main>
      </div>
    </div>
    <CommandPalette />
    <ToastStack />
  </div>
</template>

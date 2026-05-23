<script setup lang="ts">
const { toasts, dismiss } = useToast()

const tone = (t: 'success' | 'error' | 'info') => {
  if (t === 'success') return { rail: 'bg-status-ok',      label: 'ok',     labelClass: 'text-status-ok' }
  if (t === 'error')   return { rail: 'bg-status-failing', label: 'error',  labelClass: 'text-status-failing' }
  return                       { rail: 'bg-ink',           label: 'info',   labelClass: 'text-ink-muted' }
}
</script>

<template>
  <Teleport to="body">
    <div class="pointer-events-none fixed bottom-5 right-5 z-[60] flex w-[360px] max-w-[calc(100vw-2.5rem)] flex-col gap-2">
      <TransitionGroup name="toast">
        <div
          v-for="t in toasts"
          :key="t.id"
          class="toast pointer-events-auto relative overflow-hidden border border-hairline bg-surface shadow-[0_4px_24px_-8px_rgba(0,0,0,0.18)]"
        >
          <span class="absolute inset-y-0 left-0 w-[3px]" :class="tone(t.tone).rail" />
          <div class="flex items-start gap-3 px-4 py-3 pl-5">
            <div class="min-w-0 flex-1">
              <div class="flex items-baseline gap-2">
                <span
                  class="font-mono text-[9px] uppercase tracking-[0.18em]"
                  :class="tone(t.tone).labelClass"
                >
                  {{ tone(t.tone).label }}
                </span>
                <span class="truncate text-[13px] font-medium text-ink">{{ t.title }}</span>
              </div>
              <p
                v-if="t.detail"
                class="mt-1 break-words font-mono text-[11px] leading-relaxed text-ink-muted"
              >
                {{ t.detail }}
              </p>
            </div>
            <button
              type="button"
              class="-mr-1 -mt-1 px-1.5 py-0.5 font-mono text-[11px] text-ink-muted transition-colors hover:text-ink"
              aria-label="dismiss"
              @click="dismiss(t.id)"
            >
              ✕
            </button>
          </div>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-enter-active {
  transition: transform 220ms cubic-bezier(0.22, 1, 0.36, 1), opacity 180ms ease-out;
}
.toast-leave-active {
  transition: transform 160ms ease-in, opacity 140ms ease-in;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(20px);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
.toast-move {
  transition: transform 220ms cubic-bezier(0.22, 1, 0.36, 1);
}
</style>

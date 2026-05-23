<script setup lang="ts">
definePageMeta({ layout: 'auth' })

const route = useRoute()
const auth = useAuthStore()

const state = ref<'working' | 'ok' | 'error'>('working')
const message = ref<string | null>(null)

onMounted(async () => {
  const token = typeof route.query.token === 'string' ? route.query.token : ''
  if (!token) {
    state.value = 'error'
    message.value = 'no token in link'
    return
  }
  try {
    await auth.verify(token)
    state.value = 'ok'
    const next = typeof route.query.next === 'string' ? route.query.next : '/'
    setTimeout(() => navigateTo(next), 400)
  } catch (e: unknown) {
    state.value = 'error'
    message.value =
      e instanceof Error && e.message
        ? e.message
        : 'this link is invalid, expired, or already used.'
  }
})
</script>

<template>
  <template v-if="state === 'working'">
    <p class="mb-3 font-mono text-[11px] uppercase tracking-[0.2em] text-ink-muted">
      verifying
    </p>
    <h1 class="font-serif text-[48px] leading-[1.05] tracking-tight">
      one moment.
    </h1>
    <div class="mt-8 flex items-center gap-2">
      <span class="block h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
      <span class="font-mono text-[11px] uppercase tracking-wider text-ink-muted">
        exchanging token for session
      </span>
    </div>
  </template>

  <template v-else-if="state === 'ok'">
    <p class="mb-3 font-mono text-[11px] uppercase tracking-[0.2em] text-status-ok">
      verified
    </p>
    <h1 class="font-serif text-[48px] leading-[1.05] tracking-tight">
      welcome back.
    </h1>
    <p class="mt-4 font-mono text-[11px] uppercase tracking-wider text-ink-muted">
      redirecting…
    </p>
  </template>

  <template v-else>
    <p class="mb-3 font-mono text-[11px] uppercase tracking-[0.2em] text-status-failing">
      link invalid
    </p>
    <h1 class="font-serif text-[48px] leading-[1.05] tracking-tight">
      that link won't open.
    </h1>
    <p class="mt-4 max-w-sm leading-relaxed text-ink-muted">
      {{ message }}
    </p>
    <NuxtLink
      to="/login"
      class="mt-8 inline-block border border-accent bg-accent px-4 py-2.5 font-mono text-[12px] uppercase tracking-[0.18em] text-white transition-opacity hover:opacity-90"
    >
      request a new link →
    </NuxtLink>
  </template>
</template>

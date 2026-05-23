<script setup lang="ts">
import HairlineCard from '~/components/primitives/HairlineCard.vue'
import ErrorState from '~/components/primitives/ErrorState.vue'
import Skeleton from '~/components/primitives/Skeleton.vue'

const auth = useAuthStore()
const toast = useToast()

const loading = ref(false)
const refreshError = ref<string | null>(null)
const signingOut = ref(false)

const refreshMe = async () => {
  if (loading.value) return
  loading.value = true
  refreshError.value = null
  try {
    await auth.fetchMe()
  } catch (e: unknown) {
    refreshError.value = (e as Error)?.message ?? 'failed to load'
  } finally {
    loading.value = false
  }
}

const doSignOut = async () => {
  if (signingOut.value) return
  signingOut.value = true
  try {
    await auth.logout()
    toast.success('signed out', 'session ended.')
    await navigateTo('/login')
  } catch (e: unknown) {
    toast.error('sign out failed', (e as Error)?.message)
  } finally {
    signingOut.value = false
  }
}

const copyEmail = async () => {
  if (!auth.user?.email) return
  try {
    await navigator.clipboard.writeText(auth.user.email)
    toast.success('email copied')
  } catch {
    toast.error('clipboard blocked')
  }
}

const copyId = async () => {
  if (!auth.user?.id) return
  try {
    await navigator.clipboard.writeText(auth.user.id)
    toast.success('user id copied')
  } catch {
    toast.error('clipboard blocked')
  }
}

const initials = computed(() => {
  const e = auth.user?.email ?? ''
  return e ? e.slice(0, 2).toUpperCase() : '—'
})

const statusColor = computed(() => (auth.user?.is_active ? 'text-status-ok' : 'text-status-degraded'))
const statusDot = computed(() => (auth.user?.is_active ? 'bg-status-ok' : 'bg-status-degraded'))
</script>

<template>
  <div class="mx-auto max-w-4xl px-8 py-12">
    <div class="mb-10 flex items-baseline justify-between">
      <p class="font-mono text-[11px] uppercase tracking-[0.2em] text-ink-muted">account</p>
      <button
        type="button"
        class="font-mono text-[10px] uppercase tracking-wider text-ink-muted underline-offset-4 hover:text-ink hover:underline disabled:opacity-50"
        :disabled="loading"
        @click="refreshMe"
      >
        {{ loading ? 'refreshing…' : 'refresh' }}
      </button>
    </div>

    <h1 class="mb-12 font-serif text-[64px] leading-[0.95] tracking-tight">who you are.</h1>

    <ErrorState
      v-if="refreshError"
      class="mb-8"
      title="couldn't reload session"
      :detail="refreshError"
      @retry="refreshMe"
    />

    <HairlineCard class="mb-6">
      <div class="flex flex-wrap items-center gap-6">
        <div class="flex h-16 w-16 shrink-0 items-center justify-center border border-hairline bg-surface-2 font-mono text-[18px] tracking-wider text-ink-muted">
          <template v-if="auth.user">{{ initials }}</template>
          <Skeleton v-else height="h-5" width="w-8" />
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex items-baseline gap-2">
            <template v-if="auth.user">
              <span class="truncate font-mono text-[15px] text-ink">{{ auth.user.email }}</span>
              <button
                type="button"
                class="font-mono text-[10px] uppercase tracking-wider text-ink-muted underline-offset-4 hover:text-ink hover:underline"
                @click="copyEmail"
              >
                copy
              </button>
            </template>
            <Skeleton v-else height="h-4" width="w-56" />
          </div>
          <div class="mt-2 flex flex-wrap items-center gap-2">
            <span
              v-if="auth.user"
              class="inline-flex items-center border px-1.5 py-0.5 font-mono text-[10px] uppercase leading-none tracking-wider"
              :class="auth.isAdmin ? 'border-accent/50 text-accent' : 'border-hairline text-ink-muted'"
            >
              {{ auth.user.role }}
            </span>
            <span
              v-if="auth.user"
              class="inline-flex items-center gap-1.5 border border-hairline px-1.5 py-0.5 font-mono text-[10px] uppercase leading-none tracking-wider"
            >
              <span class="h-1.5 w-1.5 rounded-full" :class="statusDot" />
              <span :class="statusColor">{{ auth.user.is_active ? 'active' : 'inactive' }}</span>
            </span>
          </div>
        </div>
      </div>
    </HairlineCard>

    <div class="mb-6 grid grid-cols-1 gap-px border border-hairline bg-hairline md:grid-cols-2">
      <div class="bg-surface px-5 py-4">
        <div class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">user id</div>
        <div class="mt-1 flex items-baseline gap-2">
          <code v-if="auth.user" class="break-all font-mono text-[12px] text-ink">{{ auth.user.id }}</code>
          <Skeleton v-else height="h-3" width="w-44" block />
          <button
            v-if="auth.user"
            type="button"
            class="shrink-0 font-mono text-[10px] uppercase tracking-wider text-ink-muted underline-offset-4 hover:text-ink hover:underline"
            @click="copyId"
          >
            copy
          </button>
        </div>
      </div>
      <div class="bg-surface px-5 py-4">
        <div class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">session</div>
        <div class="mt-1 flex items-baseline gap-2 text-[12px]">
          <span v-if="auth.isAuthed" class="inline-flex items-center gap-2 font-mono">
            <span class="h-1.5 w-1.5 rounded-full bg-status-ok" />
            active · cookie-bound
          </span>
          <Skeleton v-else height="h-3" width="w-32" block />
        </div>
      </div>
      <div class="bg-surface px-5 py-4">
        <div class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">auth method</div>
        <div class="mt-1 font-mono text-[12px]">magic link · email</div>
      </div>
      <div class="bg-surface px-5 py-4">
        <div class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">scope</div>
        <div class="mt-1 font-mono text-[12px]">
          {{ auth.isAdmin ? 'full · admin' : 'self-service · user' }}
        </div>
      </div>
    </div>

    <section class="border border-hairline bg-surface">
      <header class="flex items-baseline gap-3 border-b border-hairline px-5 py-3">
        <span class="font-mono text-[10px] uppercase tracking-[0.18em] text-status-failing">
          end session
        </span>
        <span class="font-mono text-[11px] text-ink-muted">
          revokes the current session cookie on this browser.
        </span>
      </header>
      <div class="flex items-center justify-between gap-4 px-5 py-5">
        <p class="text-[13px] leading-relaxed text-ink-muted">
          You'll be returned to the sign-in page. Other sessions (if any) keep working.
        </p>
        <button
          type="button"
          :disabled="signingOut || !auth.isAuthed"
          class="border border-status-failing bg-surface px-4 py-2 font-mono text-[11px] uppercase tracking-wider text-status-failing transition-colors hover:bg-status-failing hover:text-white disabled:opacity-40"
          @click="doSignOut"
        >
          {{ signingOut ? 'signing out…' : 'sign out →' }}
        </button>
      </div>
    </section>
  </div>
</template>

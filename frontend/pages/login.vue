<script setup lang="ts">
definePageMeta({ layout: 'auth' })

const auth = useAuthStore()

const email = ref('')
const submitting = ref(false)
const error = ref<string | null>(null)
const sent = ref(false)

const submit = async () => {
  if (!email.value.trim() || submitting.value) return
  submitting.value = true
  error.value = null
  try {
    await auth.requestLink(email.value.trim())
    sent.value = true
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'something went wrong'
  } finally {
    submitting.value = false
  }
}

const resend = () => {
  sent.value = false
  email.value = ''
}
</script>

<template>
  <div v-if="!sent">
    <p class="mb-3 font-mono text-[11px] uppercase tracking-[0.2em] text-ink-muted">
      sign in
    </p>
    <h1 class="mb-10 font-serif text-[56px] leading-[1.05] tracking-tight">
      one link.<br />no password.
    </h1>

    <form class="flex flex-col gap-3" @submit.prevent="submit">
      <label class="font-mono text-[11px] uppercase tracking-wider text-ink-muted">
        email
      </label>
      <input
        v-model="email"
        type="email"
        autocomplete="email"
        autofocus
        required
        :disabled="submitting"
        placeholder="you@example.com"
        class="border border-hairline bg-surface px-4 py-3 text-base text-ink transition-colors placeholder:text-ink-muted focus:border-accent focus:outline-none disabled:opacity-50"
      />

      <button
        type="submit"
        :disabled="submitting"
        class="mt-2 flex items-center justify-between border border-accent bg-accent px-4 py-3 font-mono text-[12px] uppercase tracking-[0.18em] text-white transition-opacity hover:opacity-90 disabled:opacity-60"
      >
        <span>{{ submitting ? 'sending…' : 'send magic link' }}</span>
        <span aria-hidden="true">→</span>
      </button>

      <p v-if="error" class="mt-2 font-mono text-[11px] text-status-failing">
        {{ error }}
      </p>
    </form>
  </div>

  <div v-else>
    <p class="mb-3 font-mono text-[11px] uppercase tracking-[0.2em] text-ink-muted">
      link sent
    </p>
    <h1 class="mb-6 font-serif text-[56px] leading-[1.05] tracking-tight">
      check your inbox.
    </h1>
    <p class="max-w-sm leading-relaxed text-ink-muted">
      If an account exists for
      <span class="font-mono text-ink">{{ email }}</span>,
      a sign-in link is on its way. It expires in 15 minutes.
    </p>
    <button
      type="button"
      class="mt-10 font-mono text-[11px] uppercase tracking-wider text-ink-muted transition-colors hover:text-accent"
      @click="resend"
    >
      ← use a different email
    </button>
  </div>
</template>

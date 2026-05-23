<script setup lang="ts">
import EmptyState from '~/components/primitives/EmptyState.vue'
import ErrorState from '~/components/primitives/ErrorState.vue'
import Skeleton from '~/components/primitives/Skeleton.vue'
import type { AuditEntryInfo, AuditLogResponse } from '~/types/api'

const api = useApi()

const LIMITS = [50, 100, 200] as const
const ACTIONS = [
  'user.promote',
  'user.demote',
  'apikey.create',
  'apikey.revoke',
  'apikey.group.create',
  'apikey.group.delete',
] as const

const limit = ref<(typeof LIMITS)[number]>(50)
const action = ref('') // '' = all

const { data, pending, error, refresh } = await useAsyncData<AuditLogResponse>(
  'admin:audit',
  () =>
    api<AuditLogResponse>('/admin/audit', {
      query: { limit: limit.value, ...(action.value ? { action: action.value } : {}) },
    }),
  { watch: [limit, action] },
)
const entries = computed(() => data.value?.entries ?? [])

const actor = (e: AuditEntryInfo) => e.actor_user_id ?? 'system'
const subject = (e: AuditEntryInfo) =>
  e.subject_type ? `${e.subject_type}:${e.subject_id ?? '—'}` : '—'
const metaText = (e: AuditEntryInfo) => {
  const keys = Object.keys(e.metadata ?? {})
  return keys.length ? JSON.stringify(e.metadata) : ''
}

const fmtTime = (iso: string) =>
  new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })

function errorDetail(e: unknown): string {
  const x = e as { data?: { detail?: string }; message?: string; statusMessage?: string }
  return x?.data?.detail ?? x?.statusMessage ?? x?.message ?? 'request failed'
}
</script>

<template>
  <div class="mx-auto max-w-5xl px-8 py-12">
    <div class="mb-10 flex items-baseline justify-between">
      <p class="font-mono text-[11px] uppercase tracking-[0.2em] text-ink-muted">audit</p>
      <span class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
        admin only · {{ entries.length }} shown
      </span>
    </div>

    <h1 class="mb-8 font-serif text-[64px] leading-[0.95] tracking-tight">who did what.</h1>

    <div class="mb-8 flex flex-wrap items-center justify-between gap-4">
      <div class="flex flex-wrap items-center gap-1 font-mono text-[10px] uppercase tracking-wider">
        <button
          class="border px-2.5 py-1 leading-none transition-colors"
          :class="action === '' ? 'border-accent text-accent' : 'border-hairline text-ink-muted hover:text-ink'"
          @click="action = ''"
        >
          all
        </button>
        <button
          v-for="a in ACTIONS"
          :key="a"
          class="border px-2.5 py-1 leading-none transition-colors"
          :class="action === a ? 'border-accent text-accent' : 'border-hairline text-ink-muted hover:text-ink'"
          @click="action = a"
        >
          {{ a }}
        </button>
      </div>
      <div class="flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider">
        <button
          v-for="l in LIMITS"
          :key="l"
          class="border px-2.5 py-1 leading-none transition-colors"
          :class="limit === l ? 'border-accent text-accent' : 'border-hairline text-ink-muted hover:text-ink'"
          @click="limit = l"
        >
          {{ l }}
        </button>
      </div>
    </div>

    <div v-if="pending && !data" class="border border-hairline bg-surface">
      <div v-for="i in 8" :key="i" class="border-t border-hairline px-4 py-3 first:border-t-0">
        <div class="flex items-center justify-between gap-4">
          <Skeleton height="h-4" width="w-40" block />
          <Skeleton height="h-3" width="w-24" block />
        </div>
        <Skeleton class="mt-2" height="h-3" width="w-72" block />
      </div>
    </div>

    <ErrorState
      v-else-if="error"
      title="couldn't load audit log"
      :detail="errorDetail(error)"
      @retry="refresh()"
    />

    <EmptyState
      v-else-if="!entries.length"
      eyebrow="no entries"
      title="nothing recorded in this view."
      desc="Audit entries appear here when an admin changes a role or a user mints/revokes an API key."
    />

    <ul v-else class="border border-hairline bg-surface">
      <li
        v-for="(e, i) in entries"
        :key="i"
        class="border-t border-hairline px-4 py-3 first:border-t-0"
      >
        <div class="flex items-baseline justify-between gap-4">
          <span class="font-mono text-[13px] text-ink">{{ e.action }}</span>
          <span class="shrink-0 font-mono text-[10px] uppercase tracking-wider text-ink-muted">
            {{ fmtTime(e.occurred_at) }}
          </span>
        </div>
        <div class="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[11px] text-ink-muted">
          <span>actor: {{ actor(e) }}</span>
          <span>subject: {{ subject(e) }}</span>
          <span v-if="e.ip_address">ip: {{ e.ip_address }}</span>
          <span v-if="metaText(e)" class="text-ink-muted/80">{{ metaText(e) }}</span>
        </div>
      </li>
    </ul>
  </div>
</template>

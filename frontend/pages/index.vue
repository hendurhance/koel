<script setup lang="ts">
import HairlineCard from '~/components/primitives/HairlineCard.vue'
import DataTable from '~/components/primitives/DataTable.vue'
import StatusPill from '~/components/primitives/StatusPill.vue'
import CodeChip from '~/components/primitives/CodeChip.vue'
import EmptyState from '~/components/primitives/EmptyState.vue'
import ErrorState from '~/components/primitives/ErrorState.vue'
import Skeleton from '~/components/primitives/Skeleton.vue'
import type { SinglePairResponse, SourcesResponse, UsageSummaryResponse } from '~/types/api'

const api = useApi()

const HERO_BASE = 'USD'
const HERO_TARGET = 'EUR'

const {
  data: rate,
  pending: ratePending,
  error: rateError,
  refresh: refreshRate,
} = await useAsyncData<SinglePairResponse | null>('overview:rate', async () => {
  try {
    return await api<SinglePairResponse>('/rates/current', {
      query: { base: HERO_BASE, target: HERO_TARGET },
    })
  } catch (e: unknown) {
    const status = (e as { status?: number; statusCode?: number })?.status
      ?? (e as { statusCode?: number })?.statusCode
    if (status === 404) return null
    throw e
  }
})

const heroRate = computed(() => {
  const n = parseFloat(rate.value?.rate ?? '')
  return Number.isFinite(n) ? n.toFixed(4) : '—'
})
const heroConfidence = computed(() => {
  const c = rate.value?.confidence
  if (c == null) return null
  const n = parseFloat(c)
  return Number.isFinite(n) ? n.toFixed(3) : null
})

const { data: sourcesData } = await useAsyncData<SourcesResponse>('overview:sources', () =>
  api<SourcesResponse>('/sources'),
)
const sources = computed(() => sourcesData.value?.sources ?? [])

type Row = {
  slug: string
  name: string
  weight: string
  state: 'closed' | 'half_open' | 'open' | 'neutral'
  latency: string
  failures: number
}
const rows = computed<Row[]>(() =>
  sources.value.map((s) => ({
    slug: s.slug,
    name: s.name,
    weight: parseFloat(s.weight).toFixed(3),
    state: s.health?.circuit_state ?? 'neutral',
    latency:
      s.health?.avg_latency_ms != null
        ? `${parseFloat(s.health.avg_latency_ms).toFixed(1)} ms`
        : '—',
    failures: s.health?.total_failures ?? 0,
  })),
)

const cols = [
  { key: 'slug'     as const, label: 'slug',        mono: true,                                width: '22%' },
  { key: 'name'     as const, label: 'source',                                                 width: '28%' },
  { key: 'weight'   as const, label: 'weight',      mono: true, align: 'right' as const,      width: '12%' },
  { key: 'state'    as const, label: 'circuit',                                                width: '14%' },
  { key: 'latency'  as const, label: 'avg latency', mono: true, align: 'right' as const,      width: '12%' },
  { key: 'failures' as const, label: 'failures',    mono: true, align: 'right' as const,      width: '12%' },
]

const { data: usage } = await useAsyncData<UsageSummaryResponse | null>(
  'overview:usage',
  async () => {
    const now = new Date()
    const from = new Date(now.getTime() - 7 * 86400_000)
    try {
      return await api<UsageSummaryResponse>('/usage/summary', {
        query: { from: from.toISOString(), to: now.toISOString() },
      })
    } catch {
      return null
    }
  },
)

const totalRequests = computed(() =>
  (usage.value?.by_day ?? []).reduce((sum, d) => sum + d.requests, 0),
)
const bars = computed(() => {
  const days = usage.value?.by_day ?? []
  if (!days.length) return []
  const max = Math.max(1, ...days.map((d) => d.requests))
  return days.map((d) => Math.max(4, (d.requests / max) * 100))
})
const usageSpan = computed(() => {
  const days = usage.value?.by_day ?? []
  const fmt = (iso: string) =>
    new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  if (!days.length) return { start: '—', end: 'today' }
  return { start: fmt(days[0].date), end: fmt(days[days.length - 1].date) }
})

const relTime = (iso: string | null | undefined) => {
  if (!iso) return '—'
  const s = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000))
  if (s < 60) return `${s}s ago`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

function errorDetail(e: unknown): string {
  const x = e as { data?: { detail?: string }; message?: string; statusMessage?: string }
  return x?.data?.detail ?? x?.statusMessage ?? x?.message ?? 'request failed'
}
</script>

<template>
  <div class="mx-auto max-w-5xl px-8 py-12">
    <div class="mb-10 flex items-baseline justify-between">
      <p class="font-mono text-[11px] uppercase tracking-[0.2em] text-ink-muted">
        overview
      </p>
      <span class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
        last refresh: {{ relTime(rate?.observed_at) }}
      </span>
    </div>

    <section class="mb-20">
      <div class="mb-2 flex items-center gap-3">
        <CodeChip>{{ HERO_BASE }}</CodeChip>
        <span class="text-ink-muted">→</span>
        <CodeChip>{{ HERO_TARGET }}</CodeChip>
      </div>

      <ErrorState
        v-if="rateError"
        title="couldn't load rate"
        :detail="errorDetail(rateError)"
        @retry="refreshRate"
      />

      <EmptyState
        v-else-if="rate === null && !ratePending"
        eyebrow="missing pair"
        :title="`no current rate for ${HERO_BASE} → ${HERO_TARGET}.`"
        desc="The pair may not have been observed yet, or all sources are circuit-open."
      />

      <div v-else-if="ratePending && !rate" class="flex flex-wrap items-baseline gap-x-6 gap-y-2">
        <Skeleton height="h-[88px]" width="w-[360px]" block />
        <div class="flex flex-col gap-2">
          <Skeleton height="h-4" width="w-24" block />
          <Skeleton height="h-3" width="w-40" block />
        </div>
      </div>

      <div v-else class="flex flex-wrap items-baseline gap-x-6 gap-y-2">
        <span class="font-serif text-[96px] leading-none tracking-tight tabular-nums">
          {{ heroRate }}
        </span>
        <div class="flex flex-col gap-1.5">
          <StatusPill
            status="ok"
            :label="`${rate?.sources_count ?? 0} source${rate?.sources_count === 1 ? '' : 's'}`"
          />
          <span class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
            observed {{ relTime(rate?.observed_at) }}
            <template v-if="heroConfidence"> · confidence {{ heroConfidence }}</template>
          </span>
        </div>
      </div>
    </section>

    <div class="mb-12 grid grid-cols-1 gap-8 md:grid-cols-2">
      <HairlineCard eyebrow="overview" title="7-day requests">
        <div class="space-y-5">
          <div class="flex items-baseline gap-3">
            <span class="font-serif text-5xl leading-none tabular-nums">
              {{ totalRequests.toLocaleString() }}
            </span>
          </div>
          <div v-if="bars.length" class="flex h-12 items-end gap-1">
            <div
              v-for="(h, i) in bars"
              :key="i"
              class="flex-1 bg-ink/15 transition-colors hover:bg-accent"
              :style="{ height: `${h}%` }"
            />
          </div>
          <div v-else class="flex h-12 items-center font-mono text-[11px] text-ink-muted">
            no requests in the last 7 days.
          </div>
          <div class="flex justify-between font-mono text-[10px] text-ink-muted">
            <span>{{ usageSpan.start }}</span>
            <span>{{ usageSpan.end }}</span>
          </div>
        </div>
      </HairlineCard>

      <HairlineCard eyebrow="sources" title="circuit health">
        <ul v-if="sources.length" class="space-y-3">
          <li
            v-for="s in sources.slice(0, 5)"
            :key="s.slug"
            class="flex items-center justify-between"
          >
            <span class="font-mono text-[13px]">{{ s.slug }}</span>
            <StatusPill :status="s.health?.circuit_state ?? 'neutral'" />
          </li>
        </ul>
        <p v-else class="font-mono text-[11px] text-ink-muted">no sources configured.</p>
      </HairlineCard>
    </div>

    <section class="mb-16">
      <div class="mb-4 flex items-baseline gap-3">
        <span class="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-muted">sources</span>
        <span class="text-xs text-ink-muted">· {{ sources.length }} configured</span>
      </div>
      <EmptyState
        v-if="!sources.length"
        eyebrow="no sources"
        title="no sources configured."
        desc="Sources register once ingestion has run at least once."
      />
      <DataTable v-else :columns="cols" :rows="rows" row-key="slug">
        <template #cell-state="{ row }">
          <StatusPill :status="row.state" />
        </template>
      </DataTable>
    </section>
  </div>
</template>

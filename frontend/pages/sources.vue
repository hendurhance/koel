<script setup lang="ts">
import HairlineCard from '~/components/primitives/HairlineCard.vue'
import StatusPill from '~/components/primitives/StatusPill.vue'
import EmptyState from '~/components/primitives/EmptyState.vue'
import ErrorState from '~/components/primitives/ErrorState.vue'
import Skeleton from '~/components/primitives/Skeleton.vue'
import type { SourceHealthInfo as SourceHealth, SourcesResponse } from '~/types/api'

const api = useApi()
const { data, pending, error, refresh } = await useAsyncData('sources', () =>
  api<SourcesResponse>('/sources'),
)

const sources = computed(() => data.value?.sources ?? [])

const failureRate = (h: SourceHealth) => {
  if (h.total_requests === 0) return '0.0%'
  return ((h.total_failures / h.total_requests) * 100).toFixed(1) + '%'
}

const latency = (h: SourceHealth) => {
  if (h.avg_latency_ms === null) return '—'
  return parseFloat(h.avg_latency_ms).toFixed(1) + ' ms'
}

const relTime = (iso: string | null) => {
  if (!iso) return 'never'
  const then = new Date(iso).getTime()
  const diff = Date.now() - then
  if (diff < 0) return 'just now'
  const s = Math.floor(diff / 1000)
  if (s < 60) return `${s}s ago`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  return `${d}d ago`
}

function errorDetail(e: unknown): string {
  const x = e as { data?: { detail?: string }; message?: string; statusMessage?: string }
  return x?.data?.detail ?? x?.statusMessage ?? x?.message ?? 'request failed'
}
</script>

<template>
  <div class="mx-auto max-w-5xl px-8 py-12">
    <div class="mb-10 flex items-baseline justify-between">
      <p class="font-mono text-[11px] uppercase tracking-[0.2em] text-ink-muted">sources</p>
      <span class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
        {{ sources.length }} configured
      </span>
    </div>

    <h1 class="mb-8 font-serif text-[64px] leading-[0.95] tracking-tight">
      where rates come from.
    </h1>

    <div v-if="pending && !data" class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <div
        v-for="i in 6"
        :key="i"
        class="border border-hairline bg-surface p-6"
      >
        <div class="flex items-start justify-between gap-4">
          <div class="min-w-0 space-y-2">
            <Skeleton height="h-3" width="w-20" block />
            <Skeleton height="h-3" width="w-40" block />
          </div>
          <div class="flex flex-col items-end gap-2">
            <Skeleton height="h-4" width="w-16" block />
            <Skeleton height="h-3" width="w-20" block />
          </div>
        </div>
        <div class="mt-5 grid grid-cols-2 gap-6 border-t border-hairline pt-4">
          <div v-for="j in 4" :key="j" class="space-y-2">
            <Skeleton height="h-2" width="w-16" block />
            <Skeleton height="h-4" width="w-24" block />
          </div>
        </div>
      </div>
    </div>

    <ErrorState
      v-else-if="error"
      title="couldn't load sources"
      :detail="errorDetail(error)"
      @retry="refresh()"
    />

    <EmptyState
      v-else-if="!sources.length"
      eyebrow="no sources"
      title="no sources configured."
      desc="Sources are loaded from koel/scraping — this usually means ingestion hasn't registered yet."
    />

    <div v-else class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <HairlineCard v-for="s in sources" :key="s.slug">
        <div class="flex items-start justify-between gap-4">
          <div class="min-w-0">
            <div class="flex items-baseline gap-3">
              <span class="font-mono text-[13px] font-medium">{{ s.slug }}</span>
              <span
                v-if="!s.is_active"
                class="font-mono text-[10px] uppercase tracking-wider text-ink-muted"
              >
                · inactive
              </span>
            </div>
            <div class="mt-1 truncate text-[13px] text-ink-muted">{{ s.name }}</div>
          </div>
          <div class="flex flex-col items-end gap-1.5">
            <StatusPill
              v-if="s.health"
              :status="s.health.circuit_state"
            />
            <StatusPill v-else status="neutral" />
            <span class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
              weight {{ parseFloat(s.weight).toFixed(3) }}
            </span>
          </div>
        </div>

        <div v-if="s.health" class="mt-5 grid grid-cols-2 gap-x-6 gap-y-3 border-t border-hairline pt-4">
          <div>
            <div class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">requests</div>
            <div class="mt-0.5 font-mono text-[14px] tabular-nums">
              {{ s.health.total_requests.toLocaleString() }}
            </div>
          </div>
          <div>
            <div class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">failure rate</div>
            <div
              class="mt-0.5 font-mono text-[14px] tabular-nums"
              :class="s.health.total_failures > 0 ? 'text-status-degraded' : ''"
            >
              {{ failureRate(s.health) }}
            </div>
          </div>
          <div>
            <div class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">avg latency</div>
            <div class="mt-0.5 font-mono text-[14px] tabular-nums">{{ latency(s.health) }}</div>
          </div>
          <div>
            <div class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
              consecutive failures
            </div>
            <div class="mt-0.5 font-mono text-[14px] tabular-nums">
              {{ s.health.consecutive_failures }}
            </div>
          </div>
          <div class="col-span-2 mt-1 flex items-center gap-6 border-t border-hairline pt-3">
            <div class="flex items-center gap-2">
              <span class="h-1.5 w-1.5 rounded-full bg-status-ok" />
              <span class="font-mono text-[11px] text-ink-muted">
                last success {{ relTime(s.health.last_success_at) }}
              </span>
            </div>
            <div class="flex items-center gap-2">
              <span class="h-1.5 w-1.5 rounded-full bg-status-failing" />
              <span class="font-mono text-[11px] text-ink-muted">
                last failure {{ relTime(s.health.last_failure_at) }}
              </span>
            </div>
          </div>
        </div>

        <div v-else class="mt-5 border-t border-hairline pt-4 font-mono text-[11px] text-ink-muted">
          no health data yet — source has not been polled.
        </div>
      </HairlineCard>
    </div>
  </div>
</template>

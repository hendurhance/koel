<script setup lang="ts">
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'
import EmptyState from '~/components/primitives/EmptyState.vue'
import ErrorState from '~/components/primitives/ErrorState.vue'
import Skeleton from '~/components/primitives/Skeleton.vue'
import type { UsageSummaryResponse as Summary } from '~/types/api'

const api = useApi()
const range = ref<7 | 30 | 90>(30)
const view = ref<'day' | 'endpoint'>('day')
const chartEl = ref<HTMLDivElement | null>(null)
let plot: uPlot | null = null

const { data, pending, error, refresh } = await useAsyncData<Summary>(
  'usage',
  () => {
    const now = new Date()
    const from = new Date(now.getTime() - range.value * 86400_000)
    return api<Summary>('/usage/summary', {
      query: { from: from.toISOString(), to: now.toISOString() },
    })
  },
  { watch: [range] },
)

const totals = computed(() => {
  const d = data.value
  if (!d) return { requests: 0, errors: 0, rate: '0.0%' }
  const requests = d.by_day.reduce((s, r) => s + r.requests, 0)
  const errors = d.by_day.reduce((s, r) => s + r.errors, 0)
  const rate = requests === 0 ? '0.0%' : ((errors / requests) * 100).toFixed(1) + '%'
  return { requests, errors, rate }
})

const maxEndpointRequests = computed(() => {
  const eps = data.value?.by_endpoint ?? []
  return Math.max(1, ...eps.map((e) => e.requests))
})

const topEndpoints = computed(() => {
  const eps = [...(data.value?.by_endpoint ?? [])]
  return eps.sort((a, b) => b.requests - a.requests).slice(0, 20)
})

function getAccentColor() {
  if (!import.meta.client) return '#ff3d1f'
  const css = getComputedStyle(document.documentElement).getPropertyValue('--color-accent').trim()
  return css || '#ff3d1f'
}
function getInkColor() {
  if (!import.meta.client) return '#0b0b0d'
  const css = getComputedStyle(document.documentElement).getPropertyValue('--color-ink').trim()
  return css || '#0b0b0d'
}
function getHairlineColor() {
  if (!import.meta.client) return '#e5e5e0'
  const css = getComputedStyle(document.documentElement).getPropertyValue('--color-hairline').trim()
  return css || '#e5e5e0'
}
function getMutedColor() {
  if (!import.meta.client) return '#8a8a85'
  const css = getComputedStyle(document.documentElement).getPropertyValue('--color-ink-muted').trim()
  return css || '#8a8a85'
}

function buildPlot() {
  if (!chartEl.value) return
  plot?.destroy()
  plot = null

  const days = data.value?.by_day ?? []
  if (days.length === 0) return

  const xs = days.map((d) => Math.floor(new Date(d.date).getTime() / 1000))
  const requests = days.map((d) => d.requests)
  const errors = days.map((d) => d.errors)

  const accent = getAccentColor()
  const ink = getInkColor()
  const hairline = getHairlineColor()
  const muted = getMutedColor()

  const width = chartEl.value.clientWidth
  plot = new uPlot(
    {
      width,
      height: 280,
      padding: [16, 8, 8, 8],
      cursor: { drag: { x: false, y: false }, points: { size: 6 } },
      legend: { show: false },
      scales: { x: { time: true } },
      axes: [
        {
          stroke: muted,
          grid: { show: false },
          ticks: { show: false, stroke: hairline },
          font: '10px "JetBrains Mono", ui-monospace, monospace',
        },
        {
          stroke: muted,
          grid: { stroke: hairline, width: 1 },
          ticks: { show: false },
          font: '10px "JetBrains Mono", ui-monospace, monospace',
          size: 48,
        },
      ],
      series: [
        { label: 'date' },
        {
          label: 'requests',
          stroke: ink,
          width: 1.5,
          points: { show: false },
        },
        {
          label: 'errors',
          stroke: accent,
          width: 1.5,
          points: { show: false },
        },
      ],
    },
    [xs, requests, errors],
    chartEl.value,
  )
}

let resizeObs: ResizeObserver | null = null
onMounted(() => {
  watch(
    [data, view, chartEl],
    async () => {
      await nextTick()
      if (view.value === 'day') buildPlot()
      else plot?.destroy(), (plot = null)
    },
    { immediate: true },
  )
  if (chartEl.value) {
    resizeObs = new ResizeObserver(() => {
      if (plot && chartEl.value) plot.setSize({ width: chartEl.value.clientWidth, height: 280 })
    })
    resizeObs.observe(chartEl.value)
  }
})
onBeforeUnmount(() => {
  plot?.destroy()
  plot = null
  resizeObs?.disconnect()
})

const fmtDate = (iso: string) => {
  const d = new Date(iso)
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function errorDetail(e: unknown): string {
  const x = e as { data?: { detail?: string }; message?: string; statusMessage?: string }
  return x?.data?.detail ?? x?.statusMessage ?? x?.message ?? 'request failed'
}
</script>

<template>
  <div class="mx-auto max-w-5xl px-8 py-12">
    <div class="mb-10 flex items-baseline justify-between">
      <p class="font-mono text-[11px] uppercase tracking-[0.2em] text-ink-muted">usage</p>
      <div class="flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider">
        <button
          v-for="r in [7, 30, 90] as const"
          :key="r"
          class="border px-2.5 py-1 leading-none transition-colors"
          :class="
            range === r
              ? 'border-accent text-accent'
              : 'border-hairline text-ink-muted hover:text-ink'
          "
          @click="range = r"
        >
          {{ r }}d
        </button>
      </div>
    </div>

    <h1 class="mb-8 font-serif text-[64px] leading-[0.95] tracking-tight">
      requests over time.
    </h1>

    <div class="mb-8 grid grid-cols-3 gap-px border border-hairline bg-hairline">
      <div class="bg-surface px-5 py-4">
        <div class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">requests</div>
        <div v-if="pending && !data" class="mt-2">
          <Skeleton height="h-7" width="w-28" block />
        </div>
        <div v-else class="mt-1 font-serif text-[32px] leading-none tabular-nums">
          {{ totals.requests.toLocaleString() }}
        </div>
      </div>
      <div class="bg-surface px-5 py-4">
        <div class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">errors</div>
        <div v-if="pending && !data" class="mt-2">
          <Skeleton height="h-7" width="w-20" block />
        </div>
        <div
          v-else
          class="mt-1 font-serif text-[32px] leading-none tabular-nums"
          :class="totals.errors > 0 ? 'text-status-degraded' : ''"
        >
          {{ totals.errors.toLocaleString() }}
        </div>
      </div>
      <div class="bg-surface px-5 py-4">
        <div class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">error rate</div>
        <div v-if="pending && !data" class="mt-2">
          <Skeleton height="h-7" width="w-16" block />
        </div>
        <div v-else class="mt-1 font-serif text-[32px] leading-none tabular-nums">{{ totals.rate }}</div>
      </div>
    </div>

    <div class="mb-4 flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider">
      <button
        class="border px-2.5 py-1 leading-none transition-colors"
        :class="
          view === 'day'
            ? 'border-accent text-accent'
            : 'border-hairline text-ink-muted hover:text-ink'
        "
        @click="view = 'day'"
      >
        by day
      </button>
      <button
        class="border px-2.5 py-1 leading-none transition-colors"
        :class="
          view === 'endpoint'
            ? 'border-accent text-accent'
            : 'border-hairline text-ink-muted hover:text-ink'
        "
        @click="view = 'endpoint'"
      >
        by endpoint
      </button>
    </div>

    <div v-if="pending && !data" class="border border-hairline bg-surface px-4 py-6">
      <div class="space-y-3">
        <div class="flex items-end gap-1.5" style="height: 200px">
          <div
            v-for="i in 28"
            :key="i"
            class="skeleton-bar flex-1 bg-surface-2"
            :style="{ height: `${20 + ((i * 17) % 70)}%` }"
          />
        </div>
        <div class="flex justify-between pt-2">
          <Skeleton height="h-2" width="w-16" block />
          <Skeleton height="h-2" width="w-16" block />
        </div>
      </div>
    </div>

    <ErrorState
      v-else-if="error"
      title="couldn't load usage"
      :detail="errorDetail(error)"
      @retry="refresh()"
    />

    <template v-else>
      <div v-show="view === 'day'" class="border border-hairline bg-surface px-4 py-4">
        <EmptyState
          v-if="!data?.by_day.length"
          eyebrow="no traffic"
          title="no requests in this window."
          desc="Try a wider range, or wait for traffic to roll in. Aggregations land within the hour."
        />
        <div v-else ref="chartEl" class="w-full" />
        <div
          v-if="data?.by_day.length"
          class="mt-4 flex items-center gap-5 border-t border-hairline pt-3 font-mono text-[10px] uppercase tracking-wider text-ink-muted"
        >
          <span class="flex items-center gap-2">
            <span class="h-[1.5px] w-4 bg-ink" /> requests
          </span>
          <span class="flex items-center gap-2">
            <span class="h-[1.5px] w-4 bg-accent" /> errors
          </span>
        </div>
      </div>

      <div v-show="view === 'endpoint'" class="border border-hairline bg-surface">
        <EmptyState
          v-if="!topEndpoints.length"
          eyebrow="no traffic"
          title="no endpoint activity in this window."
          desc="Endpoints with at least one request will rank here."
        />
        <ul v-else class="divide-y divide-hairline">
          <li
            v-for="e in topEndpoints"
            :key="e.endpoint"
            class="grid grid-cols-[1fr_auto] items-center gap-x-4 px-4 py-3"
          >
            <div class="min-w-0">
              <div class="truncate font-mono text-[13px]">{{ e.endpoint }}</div>
              <div class="relative mt-1.5 h-1 bg-surface-2">
                <div
                  class="absolute inset-y-0 left-0 bg-ink"
                  :style="{ width: `${(e.requests / maxEndpointRequests) * 100}%` }"
                />
              </div>
            </div>
            <div class="text-right font-mono text-[13px] tabular-nums">
              {{ e.requests.toLocaleString() }}
              <span v-if="e.errors > 0" class="ml-2 text-status-degraded text-[11px]">
                · {{ e.errors }} err
              </span>
            </div>
          </li>
        </ul>
      </div>
    </template>

    <div
      v-if="data && data.by_day.length"
      class="mt-3 flex justify-between font-mono text-[10px] uppercase tracking-wider text-ink-muted"
    >
      <span>{{ fmtDate(data.from) }}</span>
      <span>{{ fmtDate(data.to) }}</span>
    </div>
  </div>
</template>

<style>
.uplot,
.u-wrap,
.u-over,
.u-under {
  font-family: var(--font-mono, 'JetBrains Mono', ui-monospace, monospace);
}
.skeleton-bar {
  position: relative;
  overflow: hidden;
}
.skeleton-bar::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, transparent, var(--color-hairline), transparent);
  transform: translateY(-100%);
  animation: skeleton-bar-pulse 1400ms ease-in-out infinite;
  opacity: 0.5;
}
@keyframes skeleton-bar-pulse {
  to { transform: translateY(100%); }
}
</style>

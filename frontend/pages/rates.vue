<script setup lang="ts">
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'
import NumberFlow, { type Format } from '@number-flow/vue'
import CurrencyCombobox from '~/components/primitives/CurrencyCombobox.vue'
import EmptyState from '~/components/primitives/EmptyState.vue'
import ErrorState from '~/components/primitives/ErrorState.vue'
import Skeleton from '~/components/primitives/Skeleton.vue'
import type {
  CurrenciesResponse,
  HistoryResponse,
  SinglePairResponse as CurrentPair,
} from '~/types/api'

type RangeKey = '24h' | '7d' | '30d' | '24mo'
const RANGES: Record<RangeKey, { hours: number; limit: number; label: string }> = {
  '24h':  { hours: 24,       limit: 500,   label: '24h' },
  '7d':   { hours: 24 * 7,   limit: 1000,  label: '7d' },
  '30d':  { hours: 24 * 30,  limit: 2000,  label: '30d' },
  '24mo': { hours: 24 * 730, limit: 10000, label: '24mo' },
}

const api = useApi()

const base = ref('USD')
const target = ref('EUR')
const range = ref<RangeKey>('7d')

const { data: currenciesResp } = await useAsyncData('rates:currencies', () =>
  api<CurrenciesResponse>('/currencies'),
)
const currencies = computed(() => currenciesResp.value?.currencies ?? [])
const targetCurrency = computed(() =>
  currencies.value.find((c) => c.code === target.value) ?? null,
)

const currentKey = computed(() => `rates:current:${base.value}:${target.value}`)
const {
  data: current,
  pending: currentPending,
  error: currentError,
  refresh: refreshCurrent,
} = await useAsyncData<CurrentPair | null>(
  currentKey,
  async () => {
    if (!base.value || !target.value || base.value === target.value) return null
    try {
      return await api<CurrentPair>('/rates/current', {
        query: { base: base.value, target: target.value },
      })
    } catch (e: unknown) {
      const status = (e as { status?: number; statusCode?: number })?.status
        ?? (e as { statusCode?: number })?.statusCode
      if (status === 404) return null
      throw e
    }
  },
  { watch: [base, target] },
)

const historyKey = computed(
  () => `rates:history:${base.value}:${target.value}:${range.value}`,
)
const {
  data: history,
  pending: historyPending,
  refresh: refreshHistory,
} = await useAsyncData<HistoryResponse | null>(
  historyKey,
  async () => {
    if (!base.value || !target.value || base.value === target.value) return null
    const cfg = RANGES[range.value]
    const since = new Date(Date.now() - cfg.hours * 3600_000).toISOString()
    try {
      return await api<HistoryResponse>('/rates/history', {
        query: { base: base.value, target: target.value, since, limit: cfg.limit },
      })
    } catch {
      return null
    }
  },
  { watch: [base, target, range] },
)

const rateNumber = computed(() => {
  const r = current.value?.rate
  if (!r) return 0
  const n = parseFloat(r)
  return Number.isFinite(n) ? n : 0
})

const decimals = computed(() => targetCurrency.value?.decimal_digits ?? 4)

const rateFormat = computed<Format>(() => ({
  minimumFractionDigits: Math.max(decimals.value, 4),
  maximumFractionDigits: Math.max(decimals.value, 4),
  useGrouping: false,
}))

const confidenceLabel = computed(() => {
  const c = current.value?.confidence
  if (c == null) return null
  const n = parseFloat(c)
  return Number.isFinite(n) ? n.toFixed(3) : null
})

const isDerived = computed(
  () => current.value != null && current.value.confidence == null,
)

const relTime = (iso: string | null | undefined) => {
  if (!iso) return ''
  const then = new Date(iso).getTime()
  const diff = Date.now() - then
  const s = Math.max(0, Math.floor(diff / 1000))
  if (s < 60) return `${s}s ago`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  return `${d}d ago`
}

const swap = () => {
  const b = base.value
  base.value = target.value
  target.value = b
}


const chartEl = ref<HTMLDivElement | null>(null)
let plot: uPlot | null = null
let resizeObs: ResizeObserver | null = null

const cssVar = (name: string, fallback: string) => {
  if (!import.meta.client) return fallback
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

function buildPlot() {
  if (!chartEl.value) return
  plot?.destroy()
  plot = null

  const points = history.value?.points ?? []
  if (points.length < 2) return

  const xs: number[] = []
  const ys: (number | null)[] = []
  for (const p of points) {
    const t = Math.floor(new Date(p.observed_at).getTime() / 1000)
    const n = parseFloat(p.rate)
    xs.push(t)
    ys.push(Number.isFinite(n) ? n : null)
  }

  const ink      = cssVar('--color-ink',       '#0b0b0d')
  const hairline = cssVar('--color-hairline',  '#e5e5e0')
  const muted    = cssVar('--color-ink-muted', '#8a8a85')

  const dp = Math.max(decimals.value, 4)

  plot = new uPlot(
    {
      width: chartEl.value.clientWidth,
      height: 280,
      padding: [16, 8, 8, 8],
      cursor: {
        drag: { x: false, y: false },
        points: { size: 5, fill: (_, idx) => (idx === 1 ? ink : ink) },
      },
      legend: { show: false },
      scales: { x: { time: true } },
      axes: [
        {
          stroke: muted,
          grid: { show: false },
          ticks: { show: false },
          font: '10px "JetBrains Mono", ui-monospace, monospace',
        },
        {
          stroke: muted,
          grid: { stroke: hairline, width: 1 },
          ticks: { show: false },
          font: '10px "JetBrains Mono", ui-monospace, monospace',
          size: 64,
          values: (_u, splits) => splits.map((v) => v.toFixed(dp)),
        },
      ],
      series: [
        { label: 't' },
        {
          label: 'rate',
          stroke: ink,
          width: 1.5,
          points: { show: false },
        },
      ],
    },
    [xs, ys],
    chartEl.value,
  )
}

onMounted(() => {
  watch(
    [history, chartEl],
    async () => {
      await nextTick()
      buildPlot()
    },
    { immediate: true },
  )
  if (chartEl.value) {
    resizeObs = new ResizeObserver(() => {
      if (plot && chartEl.value) {
        plot.setSize({ width: chartEl.value.clientWidth, height: 280 })
      }
    })
    resizeObs.observe(chartEl.value)
  }
})
onBeforeUnmount(() => {
  plot?.destroy()
  plot = null
  resizeObs?.disconnect()
})

const retry = () => {
  refreshCurrent()
  refreshHistory()
}

function errorDetail(e: unknown): string {
  const x = e as { data?: { detail?: string }; message?: string; statusMessage?: string }
  return x?.data?.detail ?? x?.statusMessage ?? x?.message ?? 'request failed'
}
</script>

<template>
  <div class="mx-auto max-w-5xl px-8 py-12">
    <div class="mb-10 flex items-baseline justify-between">
      <p class="font-mono text-[11px] uppercase tracking-[0.2em] text-ink-muted">rates</p>
      <span class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
        <span v-if="current">observed {{ relTime(current.observed_at) }}</span>
      </span>
    </div>

    <div class="mb-10 flex flex-wrap items-end gap-3">
      <CurrencyCombobox
        v-model="base"
        :currencies="currencies"
        label="base"
        :disabled="!currencies.length"
      />
      <button
        type="button"
        class="mb-[2px] flex h-[42px] items-center justify-center border border-hairline bg-surface px-3 font-mono text-[13px] text-ink-muted transition-colors hover:border-ink hover:text-ink"
        title="swap"
        @click="swap"
      >
        ⇄
      </button>
      <CurrencyCombobox
        v-model="target"
        :currencies="currencies"
        label="target"
        :disabled="!currencies.length"
      />
    </div>

    <section class="mb-16">
      <EmptyState
        v-if="base === target"
        eyebrow="same code"
        title="pick two different currencies."
        desc="The base and target need to differ for a meaningful rate."
      />

      <ErrorState
        v-else-if="currentError"
        title="couldn't load rate"
        :detail="errorDetail(currentError)"
        @retry="retry"
      />

      <EmptyState
        v-else-if="current === null && !currentPending"
        eyebrow="missing pair"
        :title="`no current rate for ${base} → ${target}.`"
        desc="The pair may not have been observed yet, or all sources for it are circuit-open. Try a different target or check sources."
      />

      <div v-else-if="currentPending && !current">
        <div class="mb-2 flex items-baseline gap-2 font-mono text-[12px]">
          <span class="font-medium">{{ base }}</span>
          <span class="text-ink-muted">→</span>
          <span class="font-medium">{{ target }}</span>
        </div>
        <div class="flex flex-wrap items-baseline gap-x-6 gap-y-3">
          <Skeleton height="h-[88px]" width="w-[420px]" block />
          <div class="flex flex-col gap-2">
            <div class="flex flex-wrap items-center gap-1.5">
              <Skeleton height="h-4" width="w-24" block />
              <Skeleton height="h-4" width="w-20" block />
            </div>
            <Skeleton height="h-3" width="w-40" block />
          </div>
        </div>
      </div>

      <div v-else>
        <div class="mb-2 flex items-baseline gap-2 font-mono text-[12px]">
          <span class="font-medium">{{ base }}</span>
          <span class="text-ink-muted">→</span>
          <span class="font-medium">{{ target }}</span>
        </div>

        <div class="flex flex-wrap items-baseline gap-x-6 gap-y-3">
          <span
            class="font-serif text-[96px] leading-none tracking-tight tabular-nums"
            :class="currentPending ? 'opacity-40' : ''"
          >
            <NumberFlow
              :value="rateNumber"
              :format="rateFormat"
              :transformTiming="{ duration: 450, easing: 'cubic-bezier(0.22,1,0.36,1)' }"
              :spinTiming="{ duration: 450, easing: 'cubic-bezier(0.22,1,0.36,1)' }"
            />
          </span>

          <div class="flex flex-col gap-2">
            <div class="flex flex-wrap items-center gap-1.5">
              <span
                v-if="isDerived"
                class="inline-flex items-center border border-hairline border-dashed px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider leading-none text-ink-muted"
              >
                derived
              </span>
              <span
                v-else-if="confidenceLabel"
                class="inline-flex items-center border border-hairline px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider leading-none text-ink-muted"
              >
                confidence {{ confidenceLabel }}
              </span>
              <span
                v-if="current"
                class="inline-flex items-center gap-1.5 border border-hairline px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider leading-none text-ink-muted"
              >
                <span class="h-1.5 w-1.5 rounded-full bg-status-ok" />
                {{ current.sources_count }} source<span v-if="current.sources_count !== 1">s</span>
              </span>
            </div>
            <span class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
              1 {{ base }} = {{ target }} · {{ decimals }} decimal<span v-if="decimals !== 1">s</span>
            </span>
          </div>
        </div>
      </div>
    </section>

    <section class="mb-12">
      <div class="mb-4 flex items-center justify-between gap-4">
        <span class="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-muted">
          history
        </span>
        <div class="flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider">
          <button
            v-for="(cfg, k) in RANGES"
            :key="k"
            class="border px-2.5 py-1 leading-none transition-colors"
            :class="
              range === k
                ? 'border-accent text-accent'
                : 'border-hairline text-ink-muted hover:text-ink'
            "
            @click="range = k as RangeKey"
          >
            {{ cfg.label }}
          </button>
        </div>
      </div>

      <div
        v-if="historyPending && !history"
        class="border border-hairline bg-surface px-4 py-6"
      >
        <div class="flex items-end gap-1.5" style="height: 240px">
          <div
            v-for="i in 32"
            :key="i"
            class="rate-skel-bar flex-1 bg-surface-2"
            :style="{ height: `${30 + ((i * 11) % 60)}%` }"
          />
        </div>
      </div>

      <template v-else>
        <EmptyState
          v-if="base === target"
          eyebrow="same code"
          title="pick two different currencies."
        />
        <EmptyState
          v-else-if="!history || history.points.length < 2"
          eyebrow="thin history"
          title="not enough history in this window."
          desc="Try a wider range, or wait for more observations to accumulate."
        />
        <div v-else class="border border-hairline bg-surface px-4 py-4">
          <div ref="chartEl" class="w-full" />
          <div class="mt-4 flex items-center justify-between border-t border-hairline pt-3 font-mono text-[10px] uppercase tracking-wider text-ink-muted">
            <span>{{ history.points.length }} points</span>
            <span class="flex items-center gap-2">
              <span class="h-[1.5px] w-4 bg-ink" /> {{ base }} / {{ target }}
            </span>
          </div>
        </div>
      </template>
    </section>
  </div>
</template>

<style>
.uplot,
.u-wrap,
.u-over,
.u-under {
  font-family: var(--font-mono, 'JetBrains Mono', ui-monospace, monospace);
}
.rate-skel-bar {
  position: relative;
  overflow: hidden;
}
.rate-skel-bar::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, transparent, var(--color-hairline), transparent);
  transform: translateY(-100%);
  animation: rate-skel-pulse 1400ms ease-in-out infinite;
  opacity: 0.5;
}
@keyframes rate-skel-pulse {
  to { transform: translateY(100%); }
}
</style>

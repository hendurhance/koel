<script setup lang="ts">
import DataTable from '~/components/primitives/DataTable.vue'
import EmptyState from '~/components/primitives/EmptyState.vue'
import ErrorState from '~/components/primitives/ErrorState.vue'
import SkeletonRow from '~/components/primitives/SkeletonRow.vue'
import type { CurrencyInfo as Currency } from '~/types/api'

const api = useApi()
const query = ref('')

const { data, pending, error, refresh } = await useAsyncData('currencies', () =>
  api<{ currencies: Currency[] }>('/currencies'),
)

function errorDetail(e: unknown): string {
  const x = e as { data?: { detail?: string }; message?: string; statusMessage?: string }
  return x?.data?.detail ?? x?.statusMessage ?? x?.message ?? 'request failed'
}

const rows = computed(() => {
  const q = query.value.trim().toLowerCase()
  const all = data.value?.currencies ?? []
  if (!q) return all
  return all.filter(
    (c) =>
      c.code.toLowerCase().includes(q) ||
      c.name.toLowerCase().includes(q) ||
      (c.symbol ?? '').toLowerCase().includes(q),
  )
})

const tierClass = (t: string) => {
  if (t === 'major') return 'border-accent/50 text-accent'
  if (t === 'exotic') return 'border-hairline text-ink-muted border-dashed'
  return 'border-hairline text-ink-muted'
}

const cols = [
  { key: 'code'          as const, label: 'code',     mono: true,                            width: '14%' },
  { key: 'name'          as const, label: 'name',                                            width: '46%' },
  { key: 'symbol'        as const, label: 'symbol',   mono: true, align: 'right' as const,  width: '12%' },
  { key: 'decimal_digits' as const, label: 'decimals', mono: true, align: 'right' as const, width: '14%' },
  { key: 'tier'          as const, label: 'tier',                                            width: '14%' },
]
</script>

<template>
  <div class="mx-auto max-w-5xl px-8 py-12">
    <div class="mb-10 flex items-baseline justify-between">
      <p class="font-mono text-[11px] uppercase tracking-[0.2em] text-ink-muted">currencies</p>
      <span class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
        {{ data?.currencies.length ?? 0 }} tracked
      </span>
    </div>

    <h1 class="mb-8 font-serif text-[64px] leading-[0.95] tracking-tight">every code we track.</h1>

    <div class="mb-6 flex items-center gap-3">
      <div class="relative flex-1 max-w-sm">
        <input
          v-model="query"
          type="text"
          placeholder="search code, name, symbol…"
          class="w-full border border-hairline bg-surface px-3 py-2 font-mono text-[13px] text-ink placeholder:text-ink-muted focus:border-accent focus:outline-none"
        />
      </div>
      <span class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
        · {{ rows.length }} match<span v-if="rows.length !== 1">es</span>
      </span>
    </div>

    <SkeletonRow v-if="pending && !data" :count="10" :cols="[14, 46, 12, 14, 14]" />

    <ErrorState
      v-else-if="error"
      title="couldn't load currencies"
      :detail="errorDetail(error)"
      @retry="refresh()"
    />

    <EmptyState
      v-else-if="!rows.length && query"
      eyebrow="no match"
      title="nothing matches that search."
      :desc="`Try a different code or name. Searched ${data?.currencies.length ?? 0} tracked currencies.`"
    />

    <EmptyState
      v-else-if="!rows.length"
      eyebrow="empty"
      title="no currencies tracked yet."
      desc="The currency table is empty — seed data will appear after the first ingestion run."
    />

    <DataTable v-else :columns="cols" :rows="rows" row-key="code" empty="no matching currencies">
      <template #cell-symbol="{ row }">
        <span v-if="row.symbol">{{ row.symbol }}</span>
        <span v-else class="text-ink-muted">—</span>
      </template>
      <template #cell-tier="{ row }">
        <span
          class="inline-block border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider leading-none"
          :class="tierClass(row.tier)"
        >
          {{ row.tier }}
        </span>
      </template>
    </DataTable>
  </div>
</template>

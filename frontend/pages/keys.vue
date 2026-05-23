<script setup lang="ts">
import EmptyState from '~/components/primitives/EmptyState.vue'
import ErrorState from '~/components/primitives/ErrorState.vue'
import Skeleton from '~/components/primitives/Skeleton.vue'
import type {
  GroupInfo as Group,
  GroupsResponse,
  KeyCreatedResponse,
  KeyInfo as Key,
  KeysResponse,
} from '~/types/api'

type Modal =
  | { kind: 'none' }
  | { kind: 'new-group' }
  | { kind: 'new-key' }
  | { kind: 'reveal'; secret: string; info: Key }
  | { kind: 'revoke-key'; key: Key }
  | { kind: 'delete-group'; group: Group }

const api = useApi()
const toast = useToast()

const selectedId = ref<string | null>(null)
const modal = ref<Modal>({ kind: 'none' })
const actionError = ref<string | null>(null)
const submitting = ref(false)

const {
  data: groupsData,
  pending: groupsPending,
  error: groupsError,
  refresh: refreshGroups,
} = await useAsyncData('keys:groups', () => api<GroupsResponse>('/keys/groups'))

const groups = computed(() => groupsData.value?.groups ?? [])

watchEffect(() => {
  if (selectedId.value && !groups.value.find((g) => g.id === selectedId.value)) {
    selectedId.value = groups.value[0]?.id ?? null
  } else if (!selectedId.value && groups.value.length) {
    selectedId.value = groups.value[0].id
  }
})

const selectedGroup = computed(
  () => groups.value.find((g) => g.id === selectedId.value) ?? null,
)

const keysKey = computed(() => `keys:list:${selectedId.value ?? 'none'}`)
const {
  data: keysData,
  pending: keysPending,
  refresh: refreshKeys,
} = await useAsyncData<KeysResponse | null>(
  keysKey,
  async () => {
    if (!selectedId.value) return null
    return await api<KeysResponse>(`/keys/groups/${selectedId.value}/keys`)
  },
  { watch: [selectedId] },
)

const keys = computed(() => keysData.value?.keys ?? [])

const groupForm = reactive({ name: '', description: '' })
const keyForm = reactive({
  name: '',
  scopes: 'rates:read',
  rate_limit_per_min: '',
})

const openNewGroup = () => {
  groupForm.name = ''
  groupForm.description = ''
  actionError.value = null
  modal.value = { kind: 'new-group' }
}

const openNewKey = () => {
  if (!selectedId.value) return
  keyForm.name = ''
  keyForm.scopes = 'rates:read'
  keyForm.rate_limit_per_min = ''
  actionError.value = null
  modal.value = { kind: 'new-key' }
}

const closeModal = () => {
  modal.value = { kind: 'none' }
  actionError.value = null
}

const submitNewGroup = async () => {
  if (submitting.value || !groupForm.name.trim()) return
  submitting.value = true
  actionError.value = null
  try {
    const created = await api<Group>('/keys/groups', {
      method: 'POST',
      body: {
        name: groupForm.name.trim(),
        description: groupForm.description.trim() || null,
      },
    })
    await refreshGroups()
    selectedId.value = created.id
    toast.success('group created', created.name)
    closeModal()
  } catch (e: unknown) {
    actionError.value = extractError(e)
  } finally {
    submitting.value = false
  }
}

const submitNewKey = async () => {
  if (submitting.value || !keyForm.name.trim() || !selectedId.value) return
  submitting.value = true
  actionError.value = null
  try {
    const scopes = keyForm.scopes
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    const body: Record<string, unknown> = { name: keyForm.name.trim() }
    if (scopes.length) body.scopes = scopes
    const rl = keyForm.rate_limit_per_min.trim()
    if (rl) body.rate_limit_per_min = Number(rl)

    const res = await api<KeyCreatedResponse>(
      `/keys/groups/${selectedId.value}/keys`,
      { method: 'POST', body },
    )
    await Promise.all([refreshGroups(), refreshKeys()])
    modal.value = { kind: 'reveal', secret: res.key, info: res.info }
  } catch (e: unknown) {
    actionError.value = extractError(e)
  } finally {
    submitting.value = false
  }
}

const confirmRevokeKey = async () => {
  if (modal.value.kind !== 'revoke-key' || submitting.value) return
  const key = modal.value.key
  submitting.value = true
  actionError.value = null
  try {
    await api(`/keys/keys/${key.id}`, { method: 'DELETE' })
    await Promise.all([refreshGroups(), refreshKeys()])
    toast.success('key revoked', key.name)
    closeModal()
  } catch (e: unknown) {
    actionError.value = extractError(e)
  } finally {
    submitting.value = false
  }
}

const confirmDeleteGroup = async () => {
  if (modal.value.kind !== 'delete-group' || submitting.value) return
  const group = modal.value.group
  submitting.value = true
  actionError.value = null
  try {
    await api(`/keys/groups/${group.id}`, { method: 'DELETE' })
    if (selectedId.value === group.id) selectedId.value = null
    await refreshGroups()
    toast.success('group deleted', `${group.name} · ${group.keys_count} key${group.keys_count === 1 ? '' : 's'} removed`)
    closeModal()
  } catch (e: unknown) {
    actionError.value = extractError(e)
  } finally {
    submitting.value = false
  }
}

function extractError(e: unknown): string {
  const err = e as { data?: { detail?: string }; message?: string; statusText?: string }
  return err?.data?.detail || err?.message || err?.statusText || 'request failed'
}

const revealed = ref('')
const revealHandle = ref<number | null>(null)
const acknowledged = ref(false)
const copied = ref(false)

watch(modal, (m) => {
  if (m.kind !== 'reveal') {
    revealed.value = ''
    acknowledged.value = false
    copied.value = false
    if (revealHandle.value !== null) {
      window.clearTimeout(revealHandle.value)
      revealHandle.value = null
    }
    return
  }
  revealed.value = ''
  acknowledged.value = false
  copied.value = false
  const full = m.secret
  let i = 0
  const tick = () => {
    i += 1
    revealed.value = full.slice(0, i)
    if (i < full.length) {
      revealHandle.value = window.setTimeout(tick, 18)
    } else {
      revealHandle.value = null
    }
  }
  revealHandle.value = window.setTimeout(tick, 120)
})

onBeforeUnmount(() => {
  if (revealHandle.value !== null) window.clearTimeout(revealHandle.value)
})

const copySecret = async () => {
  if (modal.value.kind !== 'reveal') return
  try {
    await navigator.clipboard.writeText(modal.value.secret)
    copied.value = true
    window.setTimeout(() => (copied.value = false), 1800)
  } catch {
    toast.error('clipboard blocked', 'copy the key manually with your keyboard.')
  }
}

const relTime = (iso: string | null) => {
  if (!iso) return 'never'
  const diff = Date.now() - new Date(iso).getTime()
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

const keyStatus = (k: Key): 'active' | 'revoked' | 'expired' => {
  if (k.revoked_at) return 'revoked'
  if (k.expires_at && new Date(k.expires_at).getTime() < Date.now()) return 'expired'
  return k.is_active ? 'active' : 'revoked'
}

// Full key shape is `koel_<prefix>_<secret>`. Color the recognizable
// identifier portion (`koel_<prefix>_`) in ink and the secret in accent.
// During the typewriter reveal, only the portion typed so far is shown.
const heroSplitIndex = computed(() => {
  if (modal.value.kind !== 'reveal') return 0
  return `koel_${modal.value.info.key_prefix}_`.length
})
const heroPrefix = computed(() => revealed.value.slice(0, heroSplitIndex.value))
const heroRemainder = computed(() => revealed.value.slice(heroSplitIndex.value))

function errorDetail(e: unknown): string {
  const x = e as { data?: { detail?: string }; message?: string; statusMessage?: string }
  return x?.data?.detail ?? x?.statusMessage ?? x?.message ?? 'request failed'
}
</script>

<template>
  <div class="mx-auto max-w-6xl px-8 py-12">
    <div class="mb-10 flex items-baseline justify-between">
      <p class="font-mono text-[11px] uppercase tracking-[0.2em] text-ink-muted">keys</p>
      <span class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
        {{ groups.length }} group<span v-if="groups.length !== 1">s</span>
      </span>
    </div>

    <h1 class="mb-10 font-serif text-[64px] leading-[0.95] tracking-tight">
      groups & secrets.
    </h1>

    <ErrorState
      v-if="groupsError"
      class="mb-6"
      title="couldn't load groups"
      :detail="errorDetail(groupsError)"
      @retry="refreshGroups()"
    />

    <div class="grid grid-cols-1 gap-6 lg:grid-cols-[280px_1fr]">
      <aside class="border border-hairline bg-surface">
        <div class="flex items-center justify-between border-b border-hairline px-4 py-3">
          <span class="font-mono text-[10px] uppercase tracking-[0.18em] text-ink-muted">
            groups
          </span>
          <button
            type="button"
            class="font-mono text-[11px] uppercase tracking-wider text-accent underline-offset-4 hover:underline"
            @click="openNewGroup"
          >
            + new
          </button>
        </div>
        <ul
          v-if="groupsPending && !groups.length"
          class="divide-y divide-hairline"
        >
          <li v-for="i in 4" :key="i" class="space-y-2 px-4 py-3">
            <div class="flex items-center justify-between">
              <Skeleton height="h-3" width="w-24" block />
              <Skeleton height="h-3" width="w-5" block />
            </div>
            <Skeleton height="h-2" width="w-32" block />
          </li>
        </ul>
        <div
          v-else-if="!groups.length"
          class="px-4 py-10 text-center"
        >
          <p class="font-mono text-[10px] uppercase tracking-[0.18em] text-ink-muted">
            no groups yet
          </p>
          <p class="mt-2 text-[12px] text-ink-muted">
            Create one to start minting keys.
          </p>
          <button
            type="button"
            class="mt-4 font-mono text-[11px] uppercase tracking-wider text-accent underline-offset-4 hover:underline"
            @click="openNewGroup"
          >
            + new group
          </button>
        </div>
        <ul v-else class="divide-y divide-hairline">
          <li
            v-for="g in groups"
            :key="g.id"
            class="cursor-pointer px-4 py-3 transition-colors"
            :class="selectedId === g.id ? 'bg-surface-2' : 'hover:bg-surface-2'"
            @click="selectedId = g.id"
          >
            <div class="flex items-center justify-between gap-2">
              <span class="truncate text-[13px] font-medium">{{ g.name }}</span>
              <span
                class="shrink-0 font-mono text-[10px] uppercase tracking-wider"
                :class="selectedId === g.id ? 'text-accent' : 'text-ink-muted'"
              >
                {{ g.keys_count }}
              </span>
            </div>
            <div v-if="g.description" class="mt-0.5 truncate text-[12px] text-ink-muted">
              {{ g.description }}
            </div>
            <div class="mt-1 font-mono text-[10px] uppercase tracking-wider text-ink-muted">
              created {{ relTime(g.created_at) }}
            </div>
          </li>
        </ul>
      </aside>

      <section class="border border-hairline bg-surface">
        <header class="flex items-center justify-between gap-3 border-b border-hairline px-5 py-3.5">
          <div class="min-w-0">
            <div class="font-mono text-[10px] uppercase tracking-[0.18em] text-ink-muted">
              keys
            </div>
            <div class="mt-0.5 truncate text-[14px] font-medium">
              {{ selectedGroup?.name ?? '—' }}
            </div>
          </div>
          <div class="flex items-center gap-3">
            <button
              v-if="selectedGroup"
              type="button"
              class="font-mono text-[11px] uppercase tracking-wider text-ink-muted transition-colors hover:text-status-failing"
              @click="modal = { kind: 'delete-group', group: selectedGroup }"
            >
              delete group
            </button>
            <button
              type="button"
              :disabled="!selectedGroup"
              class="border border-accent bg-accent px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider text-white transition-opacity hover:opacity-90 disabled:opacity-40"
              @click="openNewKey"
            >
              + new key
            </button>
          </div>
        </header>

        <div v-if="!selectedGroup && !groupsPending" class="p-5">
          <EmptyState
            eyebrow="no group selected"
            title="pick a group on the left."
            desc="Groups hold keys. Create one if nothing is listed."
          />
        </div>
        <ul
          v-else-if="keysPending && !keys.length"
          class="divide-y divide-hairline"
        >
          <li v-for="i in 3" :key="i" class="grid grid-cols-[1fr_auto] items-start gap-x-6 gap-y-2 px-5 py-4">
            <div class="space-y-2">
              <Skeleton height="h-4" width="w-48" block />
              <Skeleton height="h-3" width="w-32" block />
              <div class="flex gap-1.5">
                <Skeleton height="h-3" width="w-16" block />
                <Skeleton height="h-3" width="w-12" block />
              </div>
            </div>
            <div class="space-y-2 justify-self-end">
              <Skeleton height="h-3" width="w-24" block />
              <Skeleton height="h-3" width="w-16" block />
            </div>
          </li>
        </ul>
        <div v-else-if="selectedGroup && !keys.length" class="p-5">
          <EmptyState
            eyebrow="empty group"
            title="no keys yet."
            desc="Mint a key for this group to start calling the API."
            cta="+ mint key"
            @cta="openNewKey"
          />
        </div>
        <ul v-else class="divide-y divide-hairline">
          <li
            v-for="k in keys"
            :key="k.id"
            class="grid grid-cols-[1fr_auto] items-start gap-x-6 gap-y-2 px-5 py-4"
          >
            <div class="min-w-0">
              <div class="flex items-baseline gap-2">
                <span class="truncate text-[14px] font-medium">{{ k.name }}</span>
                <span
                  class="inline-flex items-center gap-1 border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider leading-none"
                  :class="{
                    'border-hairline text-status-ok': keyStatus(k) === 'active',
                    'border-hairline text-ink-muted border-dashed': keyStatus(k) === 'revoked',
                    'border-hairline text-status-degraded': keyStatus(k) === 'expired',
                  }"
                >
                  {{ keyStatus(k) }}
                </span>
              </div>
              <div class="mt-1 font-mono text-[13px] text-ink-muted">
                {{ k.key_prefix }}••••
              </div>
              <div class="mt-2 flex flex-wrap items-center gap-1.5">
                <span
                  v-for="s in k.scopes"
                  :key="s"
                  class="border border-hairline px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider leading-none text-ink-muted"
                >
                  {{ s }}
                </span>
                <span class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
                  · {{ k.rate_limit_per_min }}/min
                </span>
              </div>
            </div>
            <div class="flex flex-col items-end gap-2">
              <div class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
                last used {{ relTime(k.last_used_at) }}
              </div>
              <button
                v-if="keyStatus(k) === 'active'"
                type="button"
                class="font-mono text-[11px] uppercase tracking-wider text-ink-muted transition-colors hover:text-status-failing"
                @click="modal = { kind: 'revoke-key', key: k }"
              >
                revoke →
              </button>
            </div>
          </li>
        </ul>
      </section>
    </div>

    <Teleport to="body">
      <div
        v-if="modal.kind === 'new-group'"
        class="fixed inset-0 z-40 flex items-center justify-center bg-ink/25 px-4 backdrop-blur-[6px]"
        @click.self="closeModal"
      >
        <div class="modal-panel w-full max-w-md border border-hairline bg-surface">
          <header class="flex items-center justify-between border-b border-hairline px-5 py-3">
            <span class="font-mono text-[10px] uppercase tracking-[0.18em] text-ink-muted">
              new group
            </span>
            <button
              class="font-mono text-[11px] text-ink-muted hover:text-ink"
              @click="closeModal"
            >
              ✕
            </button>
          </header>
          <form class="space-y-4 px-5 py-5" @submit.prevent="submitNewGroup">
            <div>
              <label class="mb-1.5 block font-mono text-[10px] uppercase tracking-wider text-ink-muted">
                name
              </label>
              <input
                v-model="groupForm.name"
                type="text"
                required
                autofocus
                maxlength="128"
                placeholder="e.g. production"
                class="w-full border border-hairline bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-muted focus:border-accent focus:outline-none"
              />
            </div>
            <div>
              <label class="mb-1.5 block font-mono text-[10px] uppercase tracking-wider text-ink-muted">
                description
                <span class="text-ink-muted/60">(optional)</span>
              </label>
              <input
                v-model="groupForm.description"
                type="text"
                maxlength="1024"
                placeholder="where these keys are used…"
                class="w-full border border-hairline bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-muted focus:border-accent focus:outline-none"
              />
            </div>
            <p v-if="actionError" class="font-mono text-[11px] text-status-failing">
              {{ actionError }}
            </p>
            <div class="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                class="font-mono text-[11px] uppercase tracking-wider text-ink-muted hover:text-ink"
                @click="closeModal"
              >
                cancel
              </button>
              <button
                type="submit"
                :disabled="submitting || !groupForm.name.trim()"
                class="border border-accent bg-accent px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider text-white transition-opacity hover:opacity-90 disabled:opacity-40"
              >
                {{ submitting ? 'creating…' : 'create group' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="modal.kind === 'new-key'"
        class="fixed inset-0 z-40 flex items-center justify-center bg-ink/25 px-4 backdrop-blur-[6px]"
        @click.self="closeModal"
      >
        <div class="modal-panel w-full max-w-md border border-hairline bg-surface">
          <header class="flex items-center justify-between border-b border-hairline px-5 py-3">
            <span class="font-mono text-[10px] uppercase tracking-[0.18em] text-ink-muted">
              mint key · {{ selectedGroup?.name }}
            </span>
            <button class="font-mono text-[11px] text-ink-muted hover:text-ink" @click="closeModal">
              ✕
            </button>
          </header>
          <form class="space-y-4 px-5 py-5" @submit.prevent="submitNewKey">
            <div>
              <label class="mb-1.5 block font-mono text-[10px] uppercase tracking-wider text-ink-muted">
                name
              </label>
              <input
                v-model="keyForm.name"
                type="text"
                required
                autofocus
                maxlength="128"
                placeholder="e.g. ingest pipeline"
                class="w-full border border-hairline bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-muted focus:border-accent focus:outline-none"
              />
            </div>
            <div>
              <label class="mb-1.5 block font-mono text-[10px] uppercase tracking-wider text-ink-muted">
                scopes
                <span class="text-ink-muted/60">(comma-separated)</span>
              </label>
              <input
                v-model="keyForm.scopes"
                type="text"
                class="w-full border border-hairline bg-surface px-3 py-2 font-mono text-[13px] text-ink focus:border-accent focus:outline-none"
              />
            </div>
            <div>
              <label class="mb-1.5 block font-mono text-[10px] uppercase tracking-wider text-ink-muted">
                rate limit (per minute)
                <span class="text-ink-muted/60">· blank = default</span>
              </label>
              <input
                v-model="keyForm.rate_limit_per_min"
                type="number"
                min="1"
                max="100000"
                placeholder="60"
                class="w-full border border-hairline bg-surface px-3 py-2 font-mono text-[13px] text-ink placeholder:text-ink-muted focus:border-accent focus:outline-none"
              />
            </div>
            <p v-if="actionError" class="font-mono text-[11px] text-status-failing">
              {{ actionError }}
            </p>
            <div class="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                class="font-mono text-[11px] uppercase tracking-wider text-ink-muted hover:text-ink"
                @click="closeModal"
              >
                cancel
              </button>
              <button
                type="submit"
                :disabled="submitting || !keyForm.name.trim()"
                class="border border-accent bg-accent px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider text-white transition-opacity hover:opacity-90 disabled:opacity-40"
              >
                {{ submitting ? 'minting…' : 'mint key' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="modal.kind === 'reveal'"
        class="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 px-4 backdrop-blur-[10px]"
      >
        <div class="reveal-panel w-full max-w-2xl border border-hairline bg-surface">
          <header class="flex items-baseline justify-between border-b border-hairline px-6 py-4">
            <div class="flex items-baseline gap-3">
              <span class="h-1.5 w-1.5 translate-y-[-2px] rounded-full bg-accent" />
              <span class="font-mono text-[10px] uppercase tracking-[0.18em] text-accent">
                shown once
              </span>
            </div>
            <span class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
              {{ modal.info.name }}
            </span>
          </header>

          <div class="px-6 py-8">
            <h2 class="mb-6 font-serif text-[44px] leading-[1] tracking-tight">
              save this now.
            </h2>
            <p class="mb-6 max-w-md text-[13px] leading-relaxed text-ink-muted">
              We hash keys on creation and never store the raw value. If you lose it, mint a new one.
            </p>

            <div class="relative mb-6 border border-accent/50 bg-surface-2 px-5 py-5">
              <div class="absolute -top-px left-0 h-px w-16 bg-accent" />
              <code class="block break-all font-mono text-[15px] leading-[1.55]">
                <span class="text-ink">{{ heroPrefix }}</span><span class="text-accent">{{ heroRemainder }}</span><span class="caret">▍</span>
              </code>
              <div class="mt-5 flex items-center justify-between">
                <span class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
                  scopes:
                  <span class="text-ink">{{ modal.info.scopes.join(' · ') }}</span>
                  · limit:
                  <span class="text-ink">{{ modal.info.rate_limit_per_min }}/min</span>
                </span>
                <button
                  type="button"
                  class="font-mono text-[11px] uppercase tracking-wider text-accent underline-offset-4 hover:underline disabled:opacity-50"
                  :disabled="revealed.length < modal.secret.length"
                  @click="copySecret"
                >
                  {{ copied ? 'copied ✓' : 'copy →' }}
                </button>
              </div>
            </div>

            <label class="mb-6 flex items-start gap-3 text-[13px] text-ink">
              <input
                v-model="acknowledged"
                type="checkbox"
                class="mt-[3px] h-4 w-4 border-hairline accent-accent"
              />
              <span>I've saved this key somewhere safe. I understand it won't be shown again.</span>
            </label>

            <div class="flex items-center justify-end">
              <button
                type="button"
                :disabled="!acknowledged"
                class="border border-ink bg-ink px-4 py-2 font-mono text-[11px] uppercase tracking-wider text-surface transition-opacity disabled:opacity-30 disabled:cursor-not-allowed enabled:hover:opacity-90"
                @click="closeModal"
              >
                done
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="modal.kind === 'revoke-key'"
        class="fixed inset-0 z-40 flex items-center justify-center bg-ink/25 px-4 backdrop-blur-[6px]"
        @click.self="closeModal"
      >
        <div class="modal-panel w-full max-w-md border border-hairline bg-surface">
          <div class="px-6 py-6">
            <div class="mb-2 font-mono text-[10px] uppercase tracking-[0.18em] text-ink-muted">
              revoke key
            </div>
            <h3 class="mb-4 font-serif text-[28px] leading-tight">
              this can't be undone.
            </h3>
            <p class="mb-5 text-[13px] leading-relaxed text-ink-muted">
              <span class="font-mono text-ink">{{ modal.key.name }}</span>
              ({{ modal.key.key_prefix }}…) will stop working immediately.
            </p>
            <p v-if="actionError" class="mb-3 font-mono text-[11px] text-status-failing">
              {{ actionError }}
            </p>
            <div class="flex items-center justify-end gap-3">
              <button
                type="button"
                class="font-mono text-[11px] uppercase tracking-wider text-ink-muted hover:text-ink"
                @click="closeModal"
              >
                cancel
              </button>
              <button
                type="button"
                :disabled="submitting"
                class="border border-status-failing bg-surface px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider text-status-failing transition-colors hover:bg-status-failing hover:text-white disabled:opacity-50"
                @click="confirmRevokeKey"
              >
                {{ submitting ? 'revoking…' : 'revoke' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="modal.kind === 'delete-group'"
        class="fixed inset-0 z-40 flex items-center justify-center bg-ink/25 px-4 backdrop-blur-[6px]"
        @click.self="closeModal"
      >
        <div class="modal-panel w-full max-w-md border border-hairline bg-surface">
          <div class="px-6 py-6">
            <div class="mb-2 font-mono text-[10px] uppercase tracking-[0.18em] text-ink-muted">
              delete group
            </div>
            <h3 class="mb-4 font-serif text-[28px] leading-tight">cascades to all keys.</h3>
            <p class="mb-5 text-[13px] leading-relaxed text-ink-muted">
              <span class="font-mono text-ink">{{ modal.group.name }}</span>
              and its
              <span class="font-mono text-ink">{{ modal.group.keys_count }}</span>
              key<span v-if="modal.group.keys_count !== 1">s</span> will be deleted.
            </p>
            <p v-if="actionError" class="mb-3 font-mono text-[11px] text-status-failing">
              {{ actionError }}
            </p>
            <div class="flex items-center justify-end gap-3">
              <button
                type="button"
                class="font-mono text-[11px] uppercase tracking-wider text-ink-muted hover:text-ink"
                @click="closeModal"
              >
                cancel
              </button>
              <button
                type="button"
                :disabled="submitting"
                class="border border-status-failing bg-surface px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider text-status-failing transition-colors hover:bg-status-failing hover:text-white disabled:opacity-50"
                @click="confirmDeleteGroup"
              >
                {{ submitting ? 'deleting…' : 'delete group' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.modal-panel {
  animation: modal-in 160ms cubic-bezier(0.22, 1, 0.36, 1);
}
.reveal-panel {
  animation: reveal-in 240ms cubic-bezier(0.22, 1, 0.36, 1);
}
@keyframes modal-in {
  from { opacity: 0; transform: scale(0.97) translateY(4px); }
  to   { opacity: 1; transform: scale(1)    translateY(0);   }
}
@keyframes reveal-in {
  from { opacity: 0; transform: scale(0.96); }
  to   { opacity: 1; transform: scale(1);    }
}
.caret {
  display: inline-block;
  width: 1ch;
  color: var(--color-accent);
  animation: blink 900ms steps(1, end) infinite;
}
@keyframes blink {
  50% { opacity: 0; }
}
</style>

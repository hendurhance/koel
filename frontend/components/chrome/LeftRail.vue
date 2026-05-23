<script setup lang="ts">
import Icon from './Icon.vue'
import Logo from './Logo.vue'
import RailItem from './RailItem.vue'

const auth = useAuthStore()
const collapsed = useState('chrome:rail-collapsed', () => false)
const toggle = () => { collapsed.value = !collapsed.value }

const items = computed(() => [
  { to: '/',           icon: 'overview',   label: 'overview' },
  { to: '/rates',      icon: 'rates',      label: 'rates' },
  { to: '/currencies', icon: 'currencies', label: 'currencies' },
  { to: '/sources',    icon: 'sources',    label: 'sources' },
  { to: '/keys',       icon: 'keys',       label: 'keys' },
  { to: '/usage',      icon: 'usage',      label: 'usage' },
  ...(auth.isAdmin ? [{ to: '/audit', icon: 'audit', label: 'audit' }] : []),
])
const footerItems = [
  { to: '/account', icon: 'account', label: 'account' },
]
</script>

<template>
  <aside
    :class="collapsed ? 'w-14' : 'w-60'"
    class="sticky top-0 z-20 flex h-screen shrink-0 flex-col border-r border-hairline bg-surface transition-[width] duration-150 ease-out"
  >
    <div
      class="flex h-14 items-center border-b border-hairline px-4"
      :class="collapsed ? 'justify-center px-0' : ''"
    >
      <div class="flex items-center gap-2.5">
        <Logo class="h-5 w-5 shrink-0 text-accent" />
        <span
          v-if="!collapsed"
          class="font-mono text-[13px] tracking-[0.08em] text-ink"
        >
          koel
        </span>
      </div>
    </div>

    <nav class="flex flex-col gap-0.5 p-2">
      <RailItem
        v-for="item in items"
        :key="item.to"
        :to="item.to"
        :icon="item.icon"
        :label="item.label"
        :collapsed="collapsed"
      />
    </nav>

    <!-- divider pushes account to bottom -->
    <div class="mt-auto border-t border-hairline" />

    <nav class="flex flex-col gap-0.5 p-2">
      <RailItem
        v-for="item in footerItems"
        :key="item.to"
        :to="item.to"
        :icon="item.icon"
        :label="item.label"
        :collapsed="collapsed"
      />
    </nav>

    <button
      type="button"
      class="flex h-10 items-center border-t border-hairline font-mono text-[10px] uppercase tracking-wider text-ink-muted transition-colors hover:text-accent"
      :class="collapsed ? 'justify-center px-0' : 'justify-between px-4'"
      :title="collapsed ? 'expand' : 'collapse'"
      @click="toggle"
    >
      <span v-if="!collapsed">collapse</span>
      <Icon :name="collapsed ? 'expand' : 'collapse'" class="h-3.5 w-3.5" />
    </button>
  </aside>
</template>

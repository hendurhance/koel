<script setup lang="ts">
defineProps<{ name: string }>()
</script>

<template>
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.5"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <g v-if="name === 'overview'">
      <rect x="3" y="3" width="7" height="7" />
      <rect x="14" y="3" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" />
      <rect x="14" y="14" width="7" height="7" />
    </g>

    <g v-else-if="name === 'rates'">
      <path d="M7 4v15" />
      <path d="M4 7l3 -3l3 3" />
      <path d="M17 20v-15" />
      <path d="M20 17l-3 3l-3 -3" />
    </g>

    <g v-else-if="name === 'currencies'">
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="3" />
    </g>

    <g v-else-if="name === 'sources'">
      <path d="M10 14a5 5 0 0 1 0 -6l3 -3a5 5 0 0 1 7 7l-1.5 1.5" />
      <path d="M14 10a5 5 0 0 1 0 6l-3 3a5 5 0 0 1 -7 -7l1.5 -1.5" />
    </g>

    <g v-else-if="name === 'keys'">
      <circle cx="8" cy="15" r="4" />
      <path d="M10.85 12.15l7.65 -7.65" />
      <path d="M18 8l2 2" />
      <path d="M17 5l2 2" />
    </g>

    <g v-else-if="name === 'usage'">
      <rect x="4"    y="13" width="3" height="7" />
      <rect x="10.5" y="7"  width="3" height="13" />
      <rect x="17"   y="10" width="3" height="10" />
    </g>

    <g v-else-if="name === 'account'">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 20c0 -4 4 -6 8 -6s8 2 8 6" />
    </g>

    <path v-else-if="name === 'collapse'" d="M15 6l-6 6l6 6" />

    <path v-else-if="name === 'expand'" d="M9 6l6 6l-6 6" />

    <g v-else-if="name === 'search'">
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.35 -4.35" />
    </g>

    <g v-else-if="name === 'sun'">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2" />
      <path d="M12 20v2" />
      <path d="M4.93 4.93l1.41 1.41" />
      <path d="M17.66 17.66l1.41 1.41" />
      <path d="M2 12h2" />
      <path d="M20 12h2" />
      <path d="M6.34 17.66l-1.41 1.41" />
      <path d="M19.07 4.93l-1.41 1.41" />
    </g>

    <path v-else-if="name === 'moon'" d="M21 12.79A9 9 0 1 1 11.21 3A7 7 0 0 0 21 12.79Z" />

    <g v-else-if="name === 'logout'">
      <path d="M9 21H5a2 2 0 0 1 -2 -2V5a2 2 0 0 1 2 -2h4" />
      <path d="M16 17l5 -5l-5 -5" />
      <path d="M21 12H9" />
    </g>

    <g v-else-if="name === 'audit'">
      <rect x="5" y="3" width="14" height="18" rx="1" />
      <path d="M9 8h6" />
      <path d="M9 12h6" />
      <path d="M9 16h4" />
    </g>
  </svg>
</template>

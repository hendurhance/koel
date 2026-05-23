import { defineStore } from 'pinia'
import type { RequestLinkResponse, UserMe, VerifyResponse } from '~/types/api'

export type User = UserMe

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as User | null,
    loaded: false,
    loading: false,
  }),
  getters: {
    isAuthed: (s): boolean => !!s.user,
    isAdmin: (s): boolean => s.user?.role === 'admin',
  },
  actions: {
    async fetchMe() {
      if (this.loading) return
      this.loading = true
      try {
        const api = useApi()
        // /auth/me returns the UserMe payload flat (no { user } wrapper).
        const data = await api<UserMe>('/auth/me')
        this.user = data
      } catch {
        this.user = null
      } finally {
        this.loaded = true
        this.loading = false
      }
    },
    async requestLink(email: string) {
      const api = useApi()
      return api<RequestLinkResponse>('/auth/request-link', {
        method: 'POST',
        body: { email },
      })
    },
    async verify(token: string) {
      const api = useApi()
      const data = await api<VerifyResponse>('/auth/verify', {
        query: { token },
      })
      this.user = data.user
      this.loaded = true
      return data
    },
    async logout() {
      const api = useApi()
      try {
        await api('/auth/logout', { method: 'POST' })
      } catch {
        /* server clears cookie either way; ignore network blips */
      }
      this.user = null
    },
    handle401() {
      this.user = null
      this.loaded = true
      const route = useRoute()
      const next =
        route.path !== '/login' && route.path !== '/auth/verify'
          ? `?next=${encodeURIComponent(route.fullPath)}`
          : ''
      navigateTo(`/login${next}`)
    },
  },
})

const PUBLIC = new Set(['/login', '/auth/verify'])
const ADMIN_ONLY = new Set(['/audit'])

export default defineNuxtRouteMiddleware(async (to) => {
  if (import.meta.server) return

  const auth = useAuthStore()
  if (!auth.loaded) await auth.fetchMe()

  const isPublic = PUBLIC.has(to.path)

  if (!auth.isAuthed && !isPublic) {
    return navigateTo({
      path: '/login',
      query: { next: to.fullPath },
    })
  }

  if (auth.isAuthed && to.path === '/login') {
    const next = typeof to.query.next === 'string' ? to.query.next : '/'
    return navigateTo(next)
  }

  if (auth.isAuthed && ADMIN_ONLY.has(to.path) && !auth.isAdmin) {
    return navigateTo('/')
  }
})

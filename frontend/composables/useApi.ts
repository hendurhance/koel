export const useApi = () => {
  return $fetch.create({
    baseURL: '/api/koel',
    credentials: 'include',
    onResponseError({ request, response }) {
      if (response.status !== 401) return
      if (!import.meta.client) return
      const url = typeof request === 'string' ? request : ''
      if (url.includes('/auth/me')) return
      const auth = useAuthStore()
      auth.handle401()
    },
  })
} 

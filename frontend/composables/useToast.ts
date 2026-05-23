export type ToastTone = 'success' | 'error' | 'info'

export type Toast = {
  id: number
  tone: ToastTone
  title: string
  detail?: string
  ttl: number
}

const toasts = ref<Toast[]>([])
let _id = 0

const push = (tone: ToastTone, title: string, detail?: string, ttl = 4200): number => {
  const id = ++_id
  toasts.value = [...toasts.value, { id, tone, title, detail, ttl }]
  if (import.meta.client && ttl > 0) {
    window.setTimeout(() => dismiss(id), ttl)
  }
  return id
}

const dismiss = (id: number) => {
  toasts.value = toasts.value.filter((t) => t.id !== id)
}

export const useToast = () => {
  return {
    toasts,
    dismiss,
    success: (title: string, detail?: string, ttl?: number) =>
      push('success', title, detail, ttl),
    error: (title: string, detail?: string, ttl?: number) =>
      push('error', title, detail, ttl ?? 6000),
    info: (title: string, detail?: string, ttl?: number) =>
      push('info', title, detail, ttl),
  }
}

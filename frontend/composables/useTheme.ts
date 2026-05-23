type Mode = 'light' | 'dark'

export const useTheme = () => {
  const theme = useState<Mode>('koel:theme', () => 'light')

  const apply = (v: Mode) => {
    if (!import.meta.client) return
    document.documentElement.classList.toggle('dark', v === 'dark')
    localStorage.setItem('koel-theme', v)
  }

  const load = () => {
    if (!import.meta.client) return
    const saved = localStorage.getItem('koel-theme') as Mode | null
    const prefers = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
    theme.value = saved ?? prefers
    apply(theme.value)
  }

  const toggle = () => {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
    apply(theme.value)
  }

  return { theme: readonly(theme), toggle, load }
}

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

export type ThemePref = 'light' | 'dark' | 'system'

interface ThemeState {
  pref: ThemePref
  isDark: boolean
  setPref: (pref: ThemePref) => void
  toggle: () => void
}

const ThemeContext = createContext<ThemeState | null>(null)
const STORAGE_KEY = 'fb_theme'

function systemPrefersDark(): boolean {
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [pref, setPrefState] = useState<ThemePref>(() => {
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved === 'light' || saved === 'dark' ? saved : 'system'
  })
  const [systemDark, setSystemDark] = useState<boolean>(systemPrefersDark)

  // 跟隨系統時要監看系統偏好變化
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = (e: MediaQueryListEvent) => setSystemDark(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  const isDark = pref === 'dark' || (pref === 'system' && systemDark)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', isDark)
  }, [isDark])

  const setPref = useCallback((next: ThemePref) => {
    setPrefState(next)
    localStorage.setItem(STORAGE_KEY, next)
  }, [])

  const toggle = useCallback(() => {
    setPref(isDark ? 'light' : 'dark')
  }, [isDark, setPref])

  const value = useMemo<ThemeState>(
    () => ({ pref, isDark, setPref, toggle }),
    [pref, isDark, setPref, toggle],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeState {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme 必須在 ThemeProvider 內使用')
  return ctx
}

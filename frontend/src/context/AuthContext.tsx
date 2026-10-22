import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { authApi } from '../api'
import type { RegisterResponse } from '../api'
import { toCode, toMessage } from '../api/client'
import type { User } from '../api/types'

interface AuthState {
  user: User | null
  loading: boolean
  register: (body: {
    email: string
    username: string
    display_name: string
    password: string
  }) => Promise<RegisterResponse>
  resendCode: (email: string) => Promise<void>
  verify: (email: string, code: string) => Promise<User>
  login: (email: string, password: string) => Promise<User>
  logout: () => Promise<void>
  refresh: () => Promise<void>
  setUser: (user: User | null) => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  // 啟動時問後端要目前的登入狀態
  useEffect(() => {
    let alive = true
    authApi
      .me()
      .then((data) => {
        if (alive) setUser(data.user)
      })
      .catch(() => {
        if (alive) setUser(null)
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [])

  const register = useCallback(
    async (body: {
      email: string
      username: string
      display_name: string
      password: string
    }) => {
      try {
        return await authApi.register(body)
      } catch (err) {
        throw new Error(toMessage(err, '註冊失敗'))
      }
    },
    [],
  )

  const resendCode = useCallback(async (email: string) => {
    try {
      await authApi.resendCode(email)
    } catch (err) {
      throw new Error(toMessage(err, '重新寄送失敗'))
    }
  }, [])

  const verify = useCallback(async (email: string, code: string) => {
    try {
      const data = await authApi.verify(email, code)
      setUser(data.user)
      return data.user
    } catch (err) {
      // 未驗證卻想登入 -> 導向驗證碼畫面
      if (toCode(err) === 'email_not_verified') {
        throw new Error('請先完成信箱驗證')
      }
      throw new Error(toMessage(err, '驗證失敗'))
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    try {
      const data = await authApi.login(email, password)
      setUser(data.user)
      return data.user
    } catch (err) {
      if (toCode(err) === 'email_not_verified') {
        throw new Error('這個信箱還沒完成驗證，請先輸入驗證碼')
      }
      throw new Error(toMessage(err, '登入失敗'))
    }
  }, [])

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } finally {
      setUser(null)
    }
  }, [])

  const refresh = useCallback(async () => {
    try {
      const data = await authApi.me()
      setUser(data.user)
    } catch {
      setUser(null)
    }
  }, [])

  const value = useMemo<AuthState>(
    () => ({ user, loading, register, resendCode, verify, login, logout, refresh, setUser }),
    [user, loading, register, resendCode, verify, login, logout, refresh],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth 必須在 AuthProvider 內使用')
  return ctx
}

import axios from 'axios'
import type { AxiosError } from 'axios'
import type { ApiErrorBody } from './types'

/** 同源部署，cookie 直接帶上 */
export const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

/** 把後端的 { error, message } 轉成可讀的 Error */
export function toMessage(err: unknown, fallback = '發生錯誤，請稍後再試'): string {
  if (axios.isAxiosError(err)) {
    const axErr = err as AxiosError<ApiErrorBody>
    const data = axErr.response?.data
    if (data && typeof data.message === 'string' && data.message) return data.message
    if (axErr.code === 'ERR_NETWORK') return '無法連線到伺服器，請確認後端是否還在跑'
    return fallback
  }
  if (err instanceof Error && err.message) return err.message
  return fallback
}

/** 取後端的機器可讀 error code（例如 email_not_verified） */
export function toCode(err: unknown): string | null {
  if (axios.isAxiosError(err)) {
    const axErr = err as AxiosError<ApiErrorBody>
    return axErr.response?.data?.error ?? null
  }
  return null
}

export function statusOf(err: unknown): number | null {
  if (axios.isAxiosError(err)) {
    return (err as AxiosError<ApiErrorBody>).response?.status ?? null
  }
  return null
}

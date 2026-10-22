import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { ErrorBanner, Spinner } from '../components/Feedback'

interface VerifyState {
  email?: string
  devCode?: string
  delivery?: 'resend' | 'console'
  justRegistered?: boolean
}

export default function VerifyPage() {
  const { verify, resendCode } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const state = (location.state as VerifyState | null) ?? {}

  const [email, setEmail] = useState(state.email ?? '')
  const [code, setCode] = useState('')
  const [devCode] = useState(state.devCode ?? '')
  const delivery = state.delivery
  const [busy, setBusy] = useState(false)
  const [resending, setResending] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState(
    state.justRegistered
      ? state.delivery === 'console'
        ? '這個信箱暫時收不到信，驗證碼直接顯示在下方。'
        : '驗證碼已寄出，請查收你的信箱。'
      : '',
  )
  const [cooldown, setCooldown] = useState(0)

  // 重發冷卻倒數
  useEffect(() => {
    if (cooldown <= 0) return
    const t = window.setTimeout(() => setCooldown((c) => c - 1), 1000)
    return () => window.clearTimeout(t)
  }, [cooldown])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await verify(email.trim(), code.trim())
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : '驗證失敗')
    } finally {
      setBusy(false)
    }
  }

  async function handleResend() {
    if (!email.trim()) {
      setError('請先填寫電子郵件')
      return
    }
    setResending(true)
    setError('')
    setInfo('')
    try {
      await resendCode(email.trim())
      setInfo('新的驗證碼已寄出。')
      setCooldown(60)
    } catch (err) {
      setError(err instanceof Error ? err.message : '重新寄送失敗')
    } finally {
      setResending(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-brand-500">信箱驗證</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            我們寄了一組 6 位數驗證碼給你
          </p>
        </div>

        <form onSubmit={submit} className="card p-5 space-y-3">
          {error && <ErrorBanner message={error} onClose={() => setError('')} />}

          {info && (
            <div className="rounded-lg bg-green-50 border border-green-200 px-3 py-2 text-sm text-green-700 dark:bg-green-950/40 dark:border-green-900 dark:text-green-300">
              {info}
            </div>
          )}

          {devCode && (
            <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-sm text-amber-800 dark:bg-amber-950/40 dark:border-amber-900 dark:text-amber-300">
              <p className="font-medium">
                {delivery === 'console'
                  ? '這個信箱收不到驗證信（Resend 尚未驗證網域）'
                  : '開發模式（EMAIL_BACKEND=console，未實際寄信）'}
              </p>
              <p className="mt-1 text-xs opacity-80">
                驗證碼直接顯示在這裡，也同時印在後端 log。
              </p>
              <p className="mt-1 font-mono text-lg tracking-widest">{devCode}</p>
              <button
                type="button"
                onClick={() => setCode(devCode)}
                className="mt-1 underline text-xs"
              >
                點我填入
              </button>
            </div>
          )}

          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="電子郵件"
            required
            className="input"
          />
          <input
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            placeholder="6 位數驗證碼"
            inputMode="numeric"
            required
            className="input text-center text-2xl tracking-[0.5em] font-mono"
          />

          <button type="submit" disabled={busy || code.length !== 6} className="btn-primary w-full">
            {busy && <Spinner className="w-4 h-4" />} 驗證
          </button>

          <button
            type="button"
            onClick={handleResend}
            disabled={resending || cooldown > 0}
            className="btn-ghost w-full text-sm"
          >
            {resending && <Spinner className="w-3.5 h-3.5" />}
            {cooldown > 0 ? `重新寄送（${cooldown} 秒後）` : '重新寄送驗證碼'}
          </button>

          <div className="text-center text-sm pt-2">
            <Link to="/login" className="link">
              返回登入
            </Link>
          </div>
        </form>
      </div>
    </div>
  )
}

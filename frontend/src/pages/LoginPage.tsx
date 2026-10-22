import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { ErrorBanner, Spinner } from '../components/Feedback'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const from = (location.state as { from?: string } | null)?.from ?? '/'

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await login(email.trim(), password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : '登入失敗')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="text-center mb-6">
          <h1 className="text-3xl font-bold text-brand-500">facebook</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            登入你的帳號，繼續看看動態
          </p>
        </div>

        <form onSubmit={submit} className="card p-5 space-y-3">
          {error && <ErrorBanner message={error} onClose={() => setError('')} />}

          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="電子郵件"
            autoComplete="email"
            required
            className="input"
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="密碼"
            autoComplete="current-password"
            required
            className="input"
          />
          <button type="submit" disabled={busy} className="btn-primary w-full">
            {busy && <Spinner className="w-4 h-4" />} 登入
          </button>

          <div className="text-center text-sm pt-2">
            <Link to="/register" className="link">
              還沒有帳號？註冊一個
            </Link>
          </div>
        </form>
      </div>
    </div>
  )
}

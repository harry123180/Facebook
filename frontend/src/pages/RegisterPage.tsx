import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { ErrorBanner, Spinner } from '../components/Feedback'

export default function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({
    email: '',
    username: '',
    display_name: '',
    password: '',
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  function set<K extends keyof typeof form>(key: K, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const res = await register({
        email: form.email.trim(),
        username: form.username.trim(),
        display_name: form.display_name.trim() || form.username.trim(),
        password: form.password,
      })
      // 帶著 email 與 dev_code 跳到驗證碼畫面
      navigate('/verify', {
        state: {
          email: res.email,
          devCode: res.dev_code,
          delivery: res.delivery,
          justRegistered: true,
        },
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : '註冊失敗')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="text-center mb-6">
          <h1 className="text-3xl font-bold text-brand-500">facebook</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">建立你的帳號</p>
        </div>

        <form onSubmit={submit} className="card p-5 space-y-3">
          {error && <ErrorBanner message={error} onClose={() => setError('')} />}

          <input
            type="email"
            value={form.email}
            onChange={(e) => set('email', e.target.value)}
            placeholder="電子郵件"
            autoComplete="email"
            required
            className="input"
          />
          <input
            value={form.username}
            onChange={(e) => set('username', e.target.value)}
            placeholder="使用者名稱（英數字、底線，3-30 字）"
            autoComplete="username"
            required
            className="input"
          />
          <input
            value={form.display_name}
            onChange={(e) => set('display_name', e.target.value)}
            placeholder="顯示名稱"
            autoComplete="name"
            className="input"
          />
          <input
            type="password"
            value={form.password}
            onChange={(e) => set('password', e.target.value)}
            placeholder="密碼（至少 8 個字元）"
            autoComplete="new-password"
            minLength={8}
            required
            className="input"
          />

          <button type="submit" disabled={busy} className="btn-primary w-full">
            {busy && <Spinner className="w-4 h-4" />} 註冊
          </button>

          <div className="text-center text-sm pt-2">
            <Link to="/login" className="link">
              已經有帳號了？登入
            </Link>
          </div>
        </form>
      </div>
    </div>
  )
}

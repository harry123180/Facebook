import { useState } from 'react'
import { usersApi, uploadsApi } from '../api'
import { toMessage } from '../api/client'
import Avatar from '../components/Avatar'
import { ErrorBanner, Spinner } from '../components/Feedback'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import type { ThemePref } from '../context/ThemeContext'

export default function SettingsPage() {
  const { user, setUser } = useAuth()
  const { pref, setPref } = useTheme()
  const [displayName, setDisplayName] = useState(user?.display_name ?? '')
  const [bio, setBio] = useState(user?.bio ?? '')
  const [avatarUrl, setAvatarUrl] = useState(user?.avatar_url ?? '')
  const [busy, setBusy] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')

  async function handleAvatar(file: File) {
    setUploading(true)
    setError('')
    setOk('')
    try {
      const { url } = await uploadsApi.image(file)
      setAvatarUrl(url)
      const data = await usersApi.updateMe({ avatar_url: url })
      setUser(data.user)
      setOk('頭像已更新')
    } catch (err) {
      setError(toMessage(err, '頭像更新失敗'))
    } finally {
      setUploading(false)
    }
  }

  async function save(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    setOk('')
    try {
      const data = await usersApi.updateMe({
        display_name: displayName.trim(),
        bio: bio.trim(),
        avatar_url: avatarUrl.trim() || null,
      })
      setUser(data.user)
      setOk('已儲存')
    } catch (err) {
      setError(toMessage(err, '儲存失敗'))
    } finally {
      setBusy(false)
    }
  }

  const themeOptions: Array<{ key: ThemePref; label: string }> = [
    { key: 'light', label: '☀️ 淺色' },
    { key: 'dark', label: '🌙 深色' },
    { key: 'system', label: '💻 跟隨系統' },
  ]

  return (
    <div className="space-y-4">
      <div className="card p-5">
        <h1 className="font-bold mb-4">個人資料</h1>

        {error && (
          <div className="mb-3">
            <ErrorBanner message={error} onClose={() => setError('')} />
          </div>
        )}
        {ok && (
          <div className="mb-3 rounded-lg bg-green-50 border border-green-200 px-3 py-2 text-sm text-green-700 dark:bg-green-950/40 dark:border-green-900 dark:text-green-300">
            {ok}
          </div>
        )}

        <form onSubmit={save} className="space-y-4">
          <div className="flex items-center gap-4">
            <Avatar user={{ ...(user ?? ({} as never)), avatar_url: avatarUrl || null }} size="lg" />
            <div>
              <label className="btn-secondary cursor-pointer">
                {uploading ? <Spinner className="w-3.5 h-3.5" /> : '📷'} 更換頭像
                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0]
                    if (f) void handleAvatar(f)
                  }}
                />
              </label>
              <p className="text-xs text-gray-400 mt-1">png / jpg / gif / webp，8MB 以內</p>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">顯示名稱</label>
            <input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              maxLength={100}
              required
              className="input"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">使用者名稱</label>
            <input value={user?.username ?? ''} disabled className="input opacity-60" />
            <p className="text-xs text-gray-400 mt-1">使用者名稱建立後不可更改</p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">個人簡介</label>
            <textarea
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              maxLength={500}
              rows={3}
              className="input resize-none"
              placeholder="介绍一下自己…"
            />
          </div>

          <button type="submit" disabled={busy} className="btn-primary">
            {busy && <Spinner className="w-4 h-4" />} 儲存
          </button>
        </form>
      </div>

      <div className="card p-5">
        <h1 className="font-bold mb-3">外觀</h1>
        <div className="flex gap-2">
          {themeOptions.map((o) => (
            <button
              key={o.key}
              onClick={() => setPref(o.key)}
              className={pref === o.key ? 'btn-primary' : 'btn-secondary'}
            >
              {o.label}
            </button>
          ))}
        </div>
        <p className="text-xs text-gray-400 mt-2">
          選擇會存進 localStorage，下次開啟會直接套用（不會閃白）。
        </p>
      </div>
    </div>
  )
}

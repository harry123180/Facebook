import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { notificationsApi } from '../api'
import { useEffect, useState } from 'react'
import { cx } from '../lib/utils'

const NAV = [
  { to: '/', label: '動態牆', icon: '🏠' },
  { to: '/friends', label: '好友', icon: '👥' },
  { to: '/messages', label: '訊息', icon: '💬' },
  { to: '/notifications', label: '通知', icon: '🔔' },
  { to: '/search', label: '搜尋', icon: '🔍' },
]

function NotificationBell() {
  const [unread, setUnread] = useState(0)
  const navigate = useNavigate()

  useEffect(() => {
    let alive = true
    const load = () => {
      notificationsApi
        .list(1, 1)
        .then((d) => {
          if (alive) setUnread(d.unread_count)
        })
        .catch(() => undefined)
    }
    load()
    // 30 秒輪詢一次未讀數
    const timer = window.setInterval(load, 30_000)
    return () => {
      alive = false
      window.clearInterval(timer)
    }
  }, [])

  return (
    <button
      onClick={() => navigate('/notifications')}
      className="relative text-xl leading-none p-1"
      title={`通知（${unread} 則未讀）`}
      aria-label={`通知，${unread} 則未讀`}
    >
      🔔
      {unread > 0 && (
        <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center">
          {unread > 99 ? '99+' : unread}
        </span>
      )}
    </button>
  )
}

export default function Layout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth()
  const { isDark, toggle } = useTheme()
  const navigate = useNavigate()

  return (
    <div className="min-h-screen flex flex-col">
      <header className="sticky top-0 z-20 bg-white border-b border-gray-200 dark:bg-gray-800 dark:border-gray-700">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center gap-4">
          <Link to="/" className="font-bold text-xl text-brand-500 shrink-0">
            facebook
          </Link>

          <div className="flex-1 max-w-sm hidden sm:block">
            <input
              type="search"
              placeholder="搜尋 Facebook"
              className="input !rounded-full !bg-gray-100 !border-0 dark:!bg-gray-700"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  const q = (e.target as HTMLInputElement).value.trim()
                  if (q) navigate(`/search?q=${encodeURIComponent(q)}`)
                }
              }}
            />
          </div>

          <div className="flex-1" />

          <div className="flex items-center gap-4">
            <NotificationBell />
            <button
              onClick={toggle}
              className="text-lg leading-none"
              title={isDark ? '切換為淺色模式' : '切換為深色模式'}
              aria-label="切換深色模式"
            >
              {isDark ? '☀️' : '🌙'}
            </button>

            {user && (
              <Link
                to={`/profile/${user.id}`}
                className="flex items-center gap-2 hover:opacity-80"
                title={user.display_name}
              >
                <span className="text-sm font-medium hidden sm:inline">{user.display_name}</span>
              </Link>
            )}

            {user && (
              <button
                onClick={async () => {
                  await logout()
                  navigate('/login')
                }}
                className="text-sm text-gray-500 hover:text-gray-800 dark:hover:text-gray-200"
              >
                登出
              </button>
            )}
          </div>
        </div>
      </header>

      <div className="flex-1 max-w-6xl mx-auto w-full px-4 py-6 flex gap-6">
        <aside className="hidden md:block w-56 shrink-0">
          <nav className="sticky top-20 space-y-1">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) => cx('nav-link', isActive && 'nav-link-active')}
              >
                <span className="text-lg">{item.icon}</span>
                {item.label}
              </NavLink>
            ))}
            {user && (
              <NavLink
                to={`/profile/${user.id}`}
                className={({ isActive }) => cx('nav-link', isActive && 'nav-link-active')}
              >
                <span className="text-lg">👤</span>
                我的個人頁
              </NavLink>
            )}
            {user && (
              <NavLink
                to="/settings"
                className={({ isActive }) => cx('nav-link', isActive && 'nav-link-active')}
              >
                <span className="text-lg">⚙️</span>
                設定
              </NavLink>
            )}
          </nav>
        </aside>

        <main className="flex-1 min-w-0 pb-16">{children}</main>
      </div>

      <footer className="border-t border-gray-200 dark:border-gray-700 py-4 text-center text-xs text-gray-400">
        Facebook MVP · 教學/作品型專案 · 與 Meta 無關
      </footer>
    </div>
  )
}

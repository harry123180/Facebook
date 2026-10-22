import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { friendsApi } from '../api'
import { toMessage } from '../api/client'
import type { FriendRequest, User } from '../api/types'
import Avatar from '../components/Avatar'
import { EmptyState, ErrorBanner, Spinner } from '../components/Feedback'
import { useAuth } from '../context/AuthContext'
import { timeAgo } from '../lib/utils'

type Tab = 'friends' | 'received' | 'sent' | 'search'

export default function FriendsPage() {
  const { user: me } = useAuth()
  const [tab, setTab] = useState<Tab>('friends')
  const [friends, setFriends] = useState<User[]>([])
  const [received, setReceived] = useState<FriendRequest[]>([])
  const [sent, setSent] = useState<FriendRequest[]>([])
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<User[]>([])
  const [searching, setSearching] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadAll = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [f, r] = await Promise.all([friendsApi.list(), friendsApi.requests()])
      setFriends(f.friends)
      setReceived(r.received)
      setSent(r.sent)
    } catch (err) {
      setError(toMessage(err, '載入好友資料失敗'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadAll()
  }, [loadAll])

  useEffect(() => {
    const q = query.trim()
    if (!q) {
      setResults([])
      return
    }
    const t = window.setTimeout(() => {
      setSearching(true)
      friendsApi
        .search(q)
        .then((d) => setResults(d.users))
        .catch((err) => setError(toMessage(err, '搜尋失敗')))
        .finally(() => setSearching(false))
    }, 300)
    return () => window.clearTimeout(t)
  }, [query])

  async function act(fn: () => Promise<unknown>, okMsg?: string) {
    setError('')
    try {
      await fn()
      await loadAll()
      if (okMsg) window.alert(okMsg)
    } catch (err) {
      setError(toMessage(err, '操作失敗'))
    }
  }

  const tabs: Array<{ key: Tab; label: string; count?: number }> = [
    { key: 'friends', label: '我的好友', count: friends.length },
    { key: 'received', label: '收到的請求', count: received.length },
    { key: 'sent', label: '送出的請求', count: sent.length },
    { key: 'search', label: '找人' },
  ]

  return (
    <div className="space-y-4">
      <div className="card p-4">
        <div className="flex flex-wrap gap-1">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={
                tab === t.key
                  ? 'px-3 py-1.5 rounded-lg text-sm font-semibold bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-200'
                  : 'px-3 py-1.5 rounded-lg text-sm text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'
              }
            >
              {t.label}
              {t.count !== undefined && t.count > 0 && (
                <span className="ml-1.5 rounded-full bg-red-500 text-white text-[10px] px-1.5 py-0.5">
                  {t.count}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {error && <ErrorBanner message={error} onClose={() => setError('')} />}

      {loading ? (
        <div className="flex justify-center py-10">
          <Spinner className="w-7 h-7" />
        </div>
      ) : (
        <>
          {tab === 'friends' && (
            <div className="card p-4">
              {friends.length === 0 ? (
                <EmptyState title="還沒有好友" hint="到「找人」分頁搜尋其他人，發送好友請求" />
              ) : (
                <ul className="divide-y divide-gray-100 dark:divide-gray-700">
                  {friends.map((f) => (
                    <li key={f.id} className="flex items-center gap-3 py-3">
                      <Link to={`/profile/${f.id}`}>
                        <Avatar user={f} size="md" />
                      </Link>
                      <div className="flex-1 min-w-0">
                        <Link to={`/profile/${f.id}`} className="font-semibold hover:underline block truncate">
                          {f.display_name}
                        </Link>
                        <p className="text-xs text-gray-500">@{f.username}</p>
                      </div>
                      <button
                        onClick={() => act(() => friendsApi.remove(f.id))}
                        className="btn-ghost !px-3 !py-1.5 text-xs"
                      >
                        解除好友
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {tab === 'received' && (
            <div className="card p-4">
              {received.length === 0 ? (
                <EmptyState title="沒有待處理的好友請求" />
              ) : (
                <ul className="divide-y divide-gray-100 dark:divide-gray-700">
                  {received.map((r) => (
                    <li key={r.id} className="flex items-center gap-3 py-3">
                      {r.user && (
                        <Link to={`/profile/${r.user.id}`}>
                          <Avatar user={r.user} size="md" />
                        </Link>
                      )}
                      <div className="flex-1 min-w-0">
                        {r.user && (
                          <Link to={`/profile/${r.user.id}`} className="font-semibold hover:underline block truncate">
                            {r.user.display_name}
                          </Link>
                        )}
                        <p className="text-xs text-gray-500">{timeAgo(r.created_at)} 送來好友請求</p>
                        {r.message && (
                          <p className="text-sm mt-1 text-gray-600 dark:text-gray-300">「{r.message}」</p>
                        )}
                      </div>
                      <div className="flex gap-2 shrink-0">
                        <button
                          onClick={() => act(() => friendsApi.accept(r.id))}
                          className="btn-primary !px-3 !py-1.5 text-xs"
                        >
                          接受
                        </button>
                        <button
                          onClick={() => act(() => friendsApi.decline(r.id))}
                          className="btn-secondary !px-3 !py-1.5 text-xs"
                        >
                          拒絕
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {tab === 'sent' && (
            <div className="card p-4">
              {sent.length === 0 ? (
                <EmptyState title="沒有送出中的好友請求" />
              ) : (
                <ul className="divide-y divide-gray-100 dark:divide-gray-700">
                  {sent.map((r) => (
                    <li key={r.id} className="flex items-center gap-3 py-3">
                      {r.user && (
                        <Link to={`/profile/${r.user.id}`}>
                          <Avatar user={r.user} size="md" />
                        </Link>
                      )}
                      <div className="flex-1 min-w-0">
                        {r.user && (
                          <Link to={`/profile/${r.user.id}`} className="font-semibold hover:underline block truncate">
                            {r.user.display_name}
                          </Link>
                        )}
                        <p className="text-xs text-gray-500">{timeAgo(r.created_at)} 送出</p>
                      </div>
                      <button
                        onClick={() => act(() => friendsApi.cancel(r.id))}
                        className="btn-secondary !px-3 !py-1.5 text-xs"
                      >
                        取消
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {tab === 'search' && (
            <div className="card p-4 space-y-3">
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="搜尋使用者名稱、顯示名稱或 email"
                className="input"
                autoFocus
              />
              {searching && <Spinner />}
              {results.length > 0 && (
                <ul className="divide-y divide-gray-100 dark:divide-gray-700">
                  {results.map((u) => (
                    <li key={u.id} className="flex items-center gap-3 py-3">
                      <Link to={`/profile/${u.id}`}>
                        <Avatar user={u} size="md" />
                      </Link>
                      <div className="flex-1 min-w-0">
                        <Link to={`/profile/${u.id}`} className="font-semibold hover:underline block truncate">
                          {u.display_name}
                        </Link>
                        <p className="text-xs text-gray-500">@{u.username}</p>
                      </div>
                      <button
                        onClick={() => act(() => friendsApi.send(u.id))}
                        className="btn-primary !px-3 !py-1.5 text-xs"
                      >
                        加好友
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {query.trim() && !searching && results.length === 0 && (
                <EmptyState title="找不到符合的使用者" />
              )}
              {me && (
                <p className="text-xs text-gray-400">
                  提示：搜尋結果不會包含你自己（@{me.username}）。
                </p>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

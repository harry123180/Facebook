import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { searchApi } from '../api'
import { toMessage } from '../api/client'
import type { Post, User } from '../api/types'
import Avatar from '../components/Avatar'
import PostCard from '../components/PostCard'
import { EmptyState, ErrorBanner, Spinner } from '../components/Feedback'
import { useAuth } from '../context/AuthContext'

type Type = 'all' | 'users' | 'posts'

export default function SearchPage() {
  const [params, setParams] = useSearchParams()
  const { user: me } = useAuth()
  const [q, setQ] = useState(params.get('q') ?? '')
  const [type, setType] = useState<Type>('all')
  const [users, setUsers] = useState<User[]>([])
  const [posts, setPosts] = useState<Post[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [error, setError] = useState('')

  const keyword = params.get('q') ?? ''

  useEffect(() => {
    setQ(keyword)
  }, [keyword])

  useEffect(() => {
    if (!keyword.trim()) {
      setUsers([])
      setPosts([])
      setSearched(false)
      return
    }
    let alive = true
    setLoading(true)
    setError('')
    searchApi
      .query(keyword, type)
      .then((d) => {
        if (!alive) return
        setUsers(d.users)
        setPosts(d.posts)
        setSearched(true)
      })
      .catch((err) => {
        if (alive) setError(toMessage(err, '搜尋失敗'))
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [keyword, type])

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const v = q.trim()
    if (!v) return
    setParams({ q: v })
  }

  return (
    <div className="space-y-4">
      <form onSubmit={submit} className="card p-4">
        <div className="flex gap-2">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="搜尋使用者或貼文內容"
            className="input"
            autoFocus
          />
          <button type="submit" className="btn-primary shrink-0">
            搜尋
          </button>
        </div>
        <div className="flex gap-1 mt-3">
          {(
            [
              { key: 'all', label: '全部' },
              { key: 'users', label: '使用者' },
              { key: 'posts', label: '貼文' },
            ] as Array<{ key: Type; label: string }>
          ).map((t) => (
            <button
              key={t.key}
              onClick={() => setType(t.key)}
              className={
                type === t.key
                  ? 'px-3 py-1.5 rounded-lg text-sm font-semibold bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-200'
                  : 'px-3 py-1.5 rounded-lg text-sm text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'
              }
            >
              {t.label}
            </button>
          ))}
        </div>
      </form>

      {error && <ErrorBanner message={error} onClose={() => setError('')} />}

      {loading && (
        <div className="flex justify-center py-10">
          <Spinner className="w-7 h-7" />
        </div>
      )}

      {!loading && searched && users.length === 0 && posts.length === 0 && (
        <div className="card">
          <EmptyState title={`找不到「${keyword}」的結果`} />
        </div>
      )}

      {users.length > 0 && (
        <div className="card p-4">
          <h2 className="font-semibold mb-2 text-sm text-gray-500">使用者（{users.length}）</h2>
          <ul className="divide-y divide-gray-100 dark:divide-gray-700">
            {users.map((u) => (
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
                {u.id !== me?.id && (
                  <Link to="/friends" className="btn-secondary !px-3 !py-1.5 text-xs">
                    加好友
                  </Link>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {posts.length > 0 && (
        <div className="space-y-4">
          <h2 className="font-semibold text-sm text-gray-500 px-1">貼文（{posts.length}）</h2>
          {posts.map((p) => (
            <PostCard key={p.id} post={p} onToggleLike={() => undefined} />
          ))}
        </div>
      )}
    </div>
  )
}

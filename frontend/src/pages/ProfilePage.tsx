import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { postsApi, usersApi } from '../api'
import { toMessage } from '../api/client'
import type { Post, User } from '../api/types'
import Avatar from '../components/Avatar'
import PostCard from '../components/PostCard'
import { EmptyState, ErrorBanner, Spinner } from '../components/Feedback'
import { useAuth } from '../context/AuthContext'
import { formatTime } from '../lib/utils'

export default function ProfilePage() {
  const { id } = useParams<{ id: string }>()
  const userId = Number(id)
  const { user: me } = useAuth()

  const [profile, setProfile] = useState<User | null>(null)
  const [stats, setStats] = useState<{ post_count: number; friend_count: number } | null>(null)
  const [posts, setPosts] = useState<Post[]>([])
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(
    async (targetPage: number, append: boolean) => {
      if (!Number.isFinite(userId)) return
      setError('')
      try {
        if (!append) {
          const data = await usersApi.get(userId)
          setProfile(data.user)
          setStats(data.stats)
        }
        const p = await usersApi.posts(userId, targetPage, 20)
        setPosts((prev) => (append ? [...prev, ...p.posts] : p.posts))
        setHasMore(p.pagination.has_more)
        setPage(targetPage)
      } catch (err) {
        setError(toMessage(err, '載入個人頁失敗'))
      } finally {
        setLoading(false)
      }
    },
    [userId],
  )

  useEffect(() => {
    setLoading(true)
    setPosts([])
    void load(1, false)
  }, [load])

  async function toggleLike(post: Post) {
    try {
      const res = post.liked_by_me
        ? await postsApi.unlike(post.id)
        : await postsApi.like(post.id)
      setPosts((prev) => prev.map((p) => (p.id === post.id ? res.post : p)))
    } catch (err) {
      setError(toMessage(err, '按讚失敗'))
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner className="w-7 h-7" />
      </div>
    )
  }

  if (!profile) {
    return (
      <div className="card">
        <EmptyState title="找不到這個人" hint={error || undefined} />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="card p-5">
        <div className="flex items-start gap-4">
          <Avatar user={profile} size="lg" />
          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-bold truncate">{profile.display_name}</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">@{profile.username}</p>
            {profile.bio && <p className="mt-2 text-sm">{profile.bio}</p>}
            <p className="mt-2 text-xs text-gray-400">
              加入於 {profile.created_at ? formatTime(profile.created_at) : '—'}
            </p>
            {stats && (
              <div className="mt-3 flex gap-4 text-sm">
                <span>
                  <strong>{stats.post_count}</strong> 貼文
                </span>
                <span>
                  <strong>{stats.friend_count}</strong> 好友
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {error && <ErrorBanner message={error} onClose={() => setError('')} />}

      {posts.length === 0 ? (
        <div className="card">
          <EmptyState title="還沒有貼文" />
        </div>
      ) : (
        posts.map((post) => (
          <PostCard
            key={post.id}
            post={post}
            onToggleLike={toggleLike}
            onDelete={post.author.id === me?.id ? async () => {
              try {
                await postsApi.remove(post.id)
                setPosts((prev) => prev.filter((p) => p.id !== post.id))
              } catch (err) {
                setError(toMessage(err, '刪除失敗'))
              }
            } : undefined}
          />
        ))
      )}

      {hasMore && (
        <div className="text-center">
          <button onClick={() => load(page + 1, true)} className="btn-secondary">
            載入更多
          </button>
        </div>
      )}
    </div>
  )
}

import { useCallback, useEffect, useState } from 'react'
import { postsApi } from '../api'
import { toMessage } from '../api/client'
import type { Post } from '../api/types'
import PostCard from '../components/PostCard'
import PostComposer from '../components/PostComposer'
import CommentSection from '../components/CommentSection'
import { EmptyState, ErrorBanner, Spinner } from '../components/Feedback'
import { useAuth } from '../context/AuthContext'

export default function FeedPage() {
  const { user } = useAuth()
  const [posts, setPosts] = useState<Post[]>([])
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')
  const [openComments, setOpenComments] = useState<number | null>(null)

  const load = useCallback(async (targetPage: number, append: boolean) => {
    if (append) setLoadingMore(true)
    else setLoading(true)
    setError('')
    try {
      const data = await postsApi.list(targetPage, 20)
      setPosts((prev) => (append ? [...prev, ...data.posts] : data.posts))
      setHasMore(data.pagination.has_more)
      setPage(targetPage)
    } catch (err) {
      setError(toMessage(err, '載入動態牆失敗'))
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }, [])

  useEffect(() => {
    void load(1, false)
  }, [load])

  async function handleCreate(content: string, imageUrls: string[]) {
    const { post } = await postsApi.create(content, imageUrls)
    setPosts((prev) => [post, ...prev])
  }

  async function toggleLike(post: Post) {
    // optimistic update
    const wasLiked = post.liked_by_me
    setPosts((prev) =>
      prev.map((p) =>
        p.id === post.id
          ? {
              ...p,
              liked_by_me: !wasLiked,
              like_count: p.like_count + (wasLiked ? -1 : 1),
            }
          : p,
      ),
    )
    try {
      const res = wasLiked
        ? await postsApi.unlike(post.id)
        : await postsApi.like(post.id)
      setPosts((prev) => prev.map((p) => (p.id === post.id ? res.post : p)))
    } catch (err) {
      // 失敗就 rollback
      setPosts((prev) =>
        prev.map((p) =>
          p.id === post.id
            ? { ...p, liked_by_me: wasLiked, like_count: p.like_count + (wasLiked ? 1 : -1) }
            : p,
        ),
      )
      setError(toMessage(err, '按讚失敗'))
    }
  }

  async function handleDelete(post: Post) {
    if (!window.confirm('確定要刪除這則貼文嗎？')) return
    try {
      await postsApi.remove(post.id)
      setPosts((prev) => prev.filter((p) => p.id !== post.id))
    } catch (err) {
      setError(toMessage(err, '刪除失敗'))
    }
  }

  function updateCommentCount(postId: number, count: number) {
    setPosts((prev) => prev.map((p) => (p.id === postId ? { ...p, comment_count: count } : p)))
  }

  return (
    <div className="space-y-4">
      <PostComposer onSubmit={handleCreate} />

      {error && <ErrorBanner message={error} onClose={() => setError('')} />}

      {loading ? (
        <div className="flex justify-center py-10">
          <Spinner className="w-7 h-7" />
        </div>
      ) : posts.length === 0 ? (
        <div className="card">
          <EmptyState
            title="還沒有任何貼文"
            hint={user ? '成為第一個發文的人吧！' : undefined}
          />
        </div>
      ) : (
        posts.map((post) => (
          <div key={post.id} className="card overflow-hidden">
            <div className="p-4 pb-0">
              <PostCard
                post={post}
                onToggleLike={toggleLike}
                onDelete={post.author.id === user?.id ? handleDelete : undefined}
                onOpenComments={(p) =>
                  setOpenComments((cur) => (cur === p.id ? null : p.id))
                }
              />
            </div>
            {openComments === post.id && (
              <div className="px-4 pb-4">
                <CommentSection
                  postId={post.id}
                  onCountChange={(c) => updateCommentCount(post.id, c)}
                />
              </div>
            )}
          </div>
        ))
      )}

      {hasMore && (
        <div className="text-center">
          <button
            onClick={() => load(page + 1, true)}
            disabled={loadingMore}
            className="btn-secondary"
          >
            {loadingMore && <Spinner className="w-4 h-4" />} 載入更多
          </button>
        </div>
      )}
    </div>
  )
}

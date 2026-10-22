import { useEffect, useState } from 'react'
import { postsApi } from '../api'
import { toMessage } from '../api/client'
import type { Comment } from '../api/types'
import Avatar from './Avatar'
import { ErrorBanner, Spinner } from './Feedback'
import { timeAgo } from '../lib/utils'
import { useAuth } from '../context/AuthContext'

interface Props {
  postId: number
  onCountChange?: (count: number) => void
}

export default function CommentSection({ postId, onCountChange }: Props) {
  const { user } = useAuth()
  const [comments, setComments] = useState<Comment[]>([])
  const [loading, setLoading] = useState(true)
  const [text, setText] = useState('')
  const [replyTo, setReplyTo] = useState<Comment | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    setLoading(true)
    postsApi
      .comments(postId)
      .then((d) => {
        if (alive) setComments(d.comments)
      })
      .catch((err) => {
        if (alive) setError(toMessage(err, '載入留言失敗'))
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [postId])

  async function submit() {
    const content = text.trim()
    if (!content) return
    setBusy(true)
    setError('')
    try {
      const { comment } = await postsApi.addComment(postId, content, replyTo?.id ?? null)
      setComments((prev) => [...prev, comment])
      setText('')
      setReplyTo(null)
      onCountChange?.(comments.length + 1)
    } catch (err) {
      setError(toMessage(err, '留言失敗'))
    } finally {
      setBusy(false)
    }
  }

  async function remove(id: number) {
    try {
      await postsApi.deleteComment(id)
      setComments((prev) => {
        onCountChange?.(prev.length - 1)
        return prev.filter((c) => c.id !== id)
      })
    } catch (err) {
      setError(toMessage(err, '刪除留言失敗'))
    }
  }

  return (
    <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700">
      {loading ? (
        <div className="flex justify-center py-4">
          <Spinner />
        </div>
      ) : (
        <div className="space-y-3">
          {comments.length === 0 && (
            <p className="text-sm text-gray-400 py-2">還沒有人留言，來當第一個。</p>
          )}

          {comments.map((c) => (
            <div key={c.id} className="flex gap-2">
              <Avatar user={c.author} size="sm" />
              <div className="flex-1 min-w-0">
                <div className="bg-gray-100 dark:bg-gray-700 rounded-2xl px-3 py-2 inline-block max-w-full">
                  <p className="text-sm font-semibold">{c.author.display_name}</p>
                  <p className="text-sm break-words whitespace-pre-wrap">{c.content}</p>
                </div>
                <div className="flex items-center gap-3 mt-1 px-2 text-xs text-gray-500">
                  <span>{timeAgo(c.created_at)}</span>
                  <button onClick={() => setReplyTo(c)} className="hover:underline">
                    回覆
                  </button>
                  {c.author.id === user?.id && (
                    <button onClick={() => remove(c.id)} className="hover:text-red-500">
                      刪除
                    </button>
                  )}
                </div>
                {replyTo?.id === c.id && (
                  <p className="text-xs text-brand-600 mt-1 px-2">
                    回覆 {c.author.display_name}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="mt-3">
          <ErrorBanner message={error} onClose={() => setError('')} />
        </div>
      )}

      <div className="mt-3 flex gap-2 items-start">
        <Avatar user={user} size="sm" />
        <div className="flex-1">
          {replyTo && (
            <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
              回覆 {replyTo.author.display_name}
              <button onClick={() => setReplyTo(null)} className="hover:underline">
                取消
              </button>
            </div>
          )}
          <div className="flex gap-2">
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  void submit()
                }
              }}
              placeholder="寫個留言…"
              className="input"
              maxLength={2000}
            />
            <button onClick={submit} disabled={busy || !text.trim()} className="btn-primary shrink-0">
              {busy && <Spinner className="w-3.5 h-3.5" />} 送出
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

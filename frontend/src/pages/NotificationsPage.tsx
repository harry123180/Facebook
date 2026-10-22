import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { notificationsApi } from '../api'
import { toMessage } from '../api/client'
import type { AppNotification } from '../api/types'
import Avatar from '../components/Avatar'
import { EmptyState, ErrorBanner, Spinner } from '../components/Feedback'
import { timeAgo } from '../lib/utils'

const TYPE_TEXT: Record<string, string> = {
  like: ' liked your post',
  comment: ' commented on your post',
  friend_request: ' sent you a friend request',
  friend_accept: ' accepted your friend request',
  message: ' sent you a message',
}

const TYPE_LABEL: Record<string, string> = {
  like: '按讚',
  comment: '留言',
  friend_request: '好友請求',
  friend_accept: '好友通過',
  message: '訊息',
}

function targetLink(n: AppNotification): string | null {
  if (!n.target_id) return null
  if (n.target_type === 'post') return `/profile/${n.actor?.id ?? ''}`
  if (n.target_type === 'user') return `/profile/${n.target_id}`
  if (n.target_type === 'conversation') return '/messages'
  return null
}

export default function NotificationsPage() {
  const [items, setItems] = useState<AppNotification[]>([])
  const [unread, setUnread] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try {
      const d = await notificationsApi.list(1, 50)
      setItems(d.notifications)
      setUnread(d.unread_count)
    } catch (err) {
      setError(toMessage(err, '載入通知失敗'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
    const t = window.setInterval(() => void load(), 15_000)
    return () => window.clearInterval(t)
  }, [load])

  async function markAll() {
    try {
      await notificationsApi.markAllRead()
      setUnread(0)
      setItems((prev) => prev.map((n) => ({ ...n, is_read: true })))
    } catch (err) {
      setError(toMessage(err, '操作失敗'))
    }
  }

  async function markOne(id: number) {
    try {
      await notificationsApi.markRead(id)
      setUnread((c) => Math.max(0, c - 1))
      setItems((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)))
    } catch (err) {
      setError(toMessage(err, '操作失敗'))
    }
  }

  return (
    <div className="space-y-4">
      <div className="card p-4 flex items-center justify-between">
        <h1 className="font-bold">
          通知
          {unread > 0 && (
            <span className="ml-2 rounded-full bg-red-500 text-white text-xs px-2 py-0.5">
              {unread} 則未讀
            </span>
          )}
        </h1>
        {unread > 0 && (
          <button onClick={markAll} className="btn-secondary !px-3 !py-1.5 text-xs">
            全部標為已讀
          </button>
        )}
      </div>

      {error && <ErrorBanner message={error} onClose={() => setError('')} />}

      {loading ? (
        <div className="flex justify-center py-10">
          <Spinner className="w-7 h-7" />
        </div>
      ) : items.length === 0 ? (
        <div className="card">
          <EmptyState title="沒有任何通知" />
        </div>
      ) : (
        <div className="card divide-y divide-gray-100 dark:divide-gray-700">
          {items.map((n) => {
            const link = targetLink(n)
            const body = (
              <div className="flex items-start gap-3 p-4">
                <Avatar user={n.actor} size="md" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm">
                    <span className="font-semibold">{n.actor?.display_name ?? '有人'}</span>
                    <span className="text-gray-600 dark:text-gray-300">
                      {TYPE_TEXT[n.type] ?? ' 與你互動'}
                    </span>
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {TYPE_LABEL[n.type] ?? n.type} · {timeAgo(n.created_at)}
                  </p>
                </div>
                {!n.is_read && (
                  <span className="w-2 h-2 rounded-full bg-brand-500 shrink-0 mt-2" />
                )}
              </div>
            )
            return (
              <div key={n.id} className={n.is_read ? '' : 'bg-brand-50/50 dark:bg-brand-900/20'}>
                {link ? (
                  <Link to={link} onClick={() => void markOne(n.id)} className="block hover:bg-gray-50 dark:hover:bg-gray-700/40">
                    {body}
                  </Link>
                ) : (
                  <button onClick={() => void markOne(n.id)} className="block w-full text-left">
                    {body}
                  </button>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

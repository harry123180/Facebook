import { Link } from 'react-router-dom'
import { useState } from 'react'
import type { Post } from '../api/types'
import Avatar from './Avatar'
import { cx, timeAgo } from '../lib/utils'

interface Props {
  post: Post
  onToggleLike: (post: Post) => void
  onDelete?: (post: Post) => void
  onOpenComments?: (post: Post) => void
  showComments?: boolean
  commentCount?: number
}

export default function PostCard({
  post,
  onToggleLike,
  onDelete,
  onOpenComments,
  showComments = false,
  commentCount,
}: Props) {
  const [imgBroken, setImgBroken] = useState<Record<number, boolean>>({})
  const comments = commentCount ?? post.comment_count

  return (
    <article className="card p-4">
      <header className="flex items-start gap-3">
        <Link to={`/profile/${post.author.id}`}>
          <Avatar user={post.author} size="md" />
        </Link>
        <div className="flex-1 min-w-0">
          <Link to={`/profile/${post.author.id}`} className="font-semibold hover:underline block truncate">
            {post.author.display_name}
          </Link>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {timeAgo(post.created_at)}
          </p>
        </div>
        {onDelete && (
          <button
            onClick={() => onDelete(post)}
            className="text-gray-400 hover:text-red-500 text-sm"
            title="刪除貼文"
            aria-label="刪除貼文"
          >
            ✕
          </button>
        )}
      </header>

      {post.content && (
        <p className="mt-3 text-sm leading-relaxed whitespace-pre-wrap break-words">{post.content}</p>
      )}

      {post.images.length > 0 && (
        <div
          className={cx(
            'mt-3 grid gap-1 overflow-hidden rounded-lg',
            post.images.length === 1 ? 'grid-cols-1' : 'grid-cols-2',
          )}
        >
          {post.images.map((img) => (
            <img
              key={img.id}
              src={img.url}
              alt=""
              loading="lazy"
              onError={() => setImgBroken((s) => ({ ...s, [img.id]: true }))}
              className={cx(
                'w-full object-cover bg-gray-100 dark:bg-gray-700',
                post.images.length === 1 ? 'max-h-96' : 'aspect-square',
                imgBroken[img.id] && 'hidden',
              )}
            />
          ))}
          {Object.values(imgBroken).some(Boolean) && (
            <div className="col-span-full py-6 text-center text-xs text-gray-400">
              圖片載入失敗
            </div>
          )}
        </div>
      )}

      <footer className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700 flex items-center gap-1">
        <button
          onClick={() => onToggleLike(post)}
          className={cx(
            'flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-sm font-medium transition-colors',
            post.liked_by_me
              ? 'text-brand-600 bg-brand-50 dark:text-brand-300 dark:bg-brand-900/30'
              : 'text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700',
          )}
        >
          <span>{post.liked_by_me ? '👍' : '👍🏻'}</span>
          {post.like_count > 0 ? post.like_count : '讚'}
        </button>

        <button
          onClick={() => onOpenComments?.(post)}
          className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-sm font-medium text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700"
        >
          <span>💬</span>
          {comments > 0 ? comments : '留言'}
        </button>
      </footer>

      {showComments && (
        <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700">
          <p className="text-xs text-gray-400">留言區塊</p>
        </div>
      )}
    </article>
  )
}

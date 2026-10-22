import { colorFor, cx, initialsOf } from '../lib/utils'
import type { Author } from '../api/types'

interface Props {
  user: Author | null
  size?: 'xs' | 'sm' | 'md' | 'lg'
  className?: string
}

const SIZES = {
  xs: 'w-6 h-6 text-[10px]',
  sm: 'w-8 h-8 text-xs',
  md: 'w-10 h-10 text-sm',
  lg: 'w-20 h-20 text-2xl',
}

export default function Avatar({ user, size = 'md', className }: Props) {
  const name = user?.display_name || user?.username || '?'

  if (user?.avatar_url) {
    return (
      <img
        src={user.avatar_url}
        alt={name}
        className={cx('rounded-full object-cover bg-gray-200', SIZES[size], className)}
        onError={(e) => {
          // 圖片載入失敗時退回首字母
          e.currentTarget.style.display = 'none'
        }}
      />
    )
  }

  return (
    <div
      className={cx(
        'rounded-full flex items-center justify-center font-bold text-white select-none',
        colorFor(user?.id ?? 0),
        SIZES[size],
        className,
      )}
      title={name}
    >
      {initialsOf(name)}
    </div>
  )
}

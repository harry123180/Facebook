import { cx } from '../lib/utils'

export function Spinner({ className }: { className?: string }) {
  return (
    <div
      className={cx(
        'w-5 h-5 rounded-full border-2 border-gray-300 border-t-brand-500 animate-spin',
        className,
      )}
      role="status"
      aria-label="載入中"
    />
  )
}

export function FullPageSpinner() {
  return (
    <div className="flex items-center justify-center py-16">
      <Spinner className="w-8 h-8 border-3" />
    </div>
  )
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="text-center py-12 px-4">
      <p className="text-gray-500 dark:text-gray-400 font-medium">{title}</p>
      {hint && <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">{hint}</p>}
    </div>
  )
}

export function ErrorBanner({ message, onClose }: { message: string; onClose?: () => void }) {
  if (!message) return null
  return (
    <div className="flex items-start gap-2 rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:border-red-900 dark:text-red-300">
      <span className="flex-1">{message}</span>
      {onClose && (
        <button onClick={onClose} className="text-red-400 hover:text-red-600" aria-label="關閉">
          ✕
        </button>
      )}
    </div>
  )
}

/** 共用小工具。 */

/** 相對時間：3 分鐘前 / 昨天 / 2026-10-22 */
export function timeAgo(iso: string): string {
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const diff = Date.now() - then
  const min = Math.floor(diff / 60000)
  if (min < 1) return '剛剛'
  if (min < 60) return `${min} 分鐘前`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr} 小時前`
  const day = Math.floor(hr / 24)
  if (day === 1) return '昨天'
  if (day < 7) return `${day} 天前`
  const d = new Date(then)
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`
}

/** 本地時間 YYYY/MM/DD HH:mm */
export function formatTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}/${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** 產生一個有對應色的頭像（沒有頭像圖時用 initials 代替） */
export function initialsOf(name: string): string {
  const trimmed = name.trim()
  if (!trimmed) return '?'
  // 中文取第一個字，英文取第一個字母
  return /[\u4e00-\u9fff]/.test(trimmed[0]) ? trimmed[0] : trimmed[0].toUpperCase()
}

const AVATAR_COLORS = [
  'bg-brand-500',
  'bg-emerald-500',
  'bg-amber-500',
  'bg-rose-500',
  'bg-violet-500',
  'bg-cyan-500',
]

export function colorFor(id: number): string {
  return AVATAR_COLORS[Math.abs(id) % AVATAR_COLORS.length]
}

export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ')
}

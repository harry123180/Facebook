import { useRef, useState } from 'react'
import { uploadsApi } from '../api'
import { toMessage } from '../api/client'
import Avatar from './Avatar'
import { ErrorBanner, Spinner } from './Feedback'
import { useAuth } from '../context/AuthContext'

interface Props {
  onSubmit: (content: string, imageUrls: string[]) => Promise<void>
}

export default function PostComposer({ onSubmit }: Props) {
  const { user } = useAuth()
  const [content, setContent] = useState('')
  const [images, setImages] = useState<string[]>([])
  const [imageUrl, setImageUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const canSubmit = (content.trim() || images.length > 0) && !busy && !uploading

  async function handleUpload(file: File) {
    setUploading(true)
    setError('')
    try {
      const { url } = await uploadsApi.image(file)
      setImages((prev) => [...prev, url])
    } catch (err) {
      setError(toMessage(err, '圖片上傳失敗'))
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function handleSubmit() {
    if (!canSubmit) return
    setBusy(true)
    setError('')
    try {
      await onSubmit(content.trim(), images)
      setContent('')
      setImages([])
      setImageUrl('')
    } catch (err) {
      setError(toMessage(err, '發文失敗'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card p-4">
      <div className="flex gap-3">
        <Avatar user={user} size="md" />
        <div className="flex-1 min-w-0">
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="想說什麼？"
            rows={3}
            maxLength={5000}
            className="input resize-none"
          />

          {images.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {images.map((url) => (
                <div key={url} className="relative">
                  <img
                    src={url}
                    alt=""
                    className="w-16 h-16 object-cover rounded-lg border border-gray-200 dark:border-gray-600"
                  />
                  <button
                    onClick={() => setImages((prev) => prev.filter((u) => u !== url))}
                    className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-gray-800 text-white text-xs flex items-center justify-center"
                    aria-label="移除圖片"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}

          {imageUrl.trim() && (
            <p className="mt-2 text-xs text-gray-500 truncate">圖片網址：{imageUrl.trim()}</p>
          )}

          {error && (
            <div className="mt-2">
              <ErrorBanner message={error} onClose={() => setError('')} />
            </div>
          )}

          <div className="mt-3 flex items-center gap-2 flex-wrap">
            <input
              type="url"
              value={imageUrl}
              onChange={(e) => setImageUrl(e.target.value)}
              placeholder="貼上圖片網址（選填）"
              className="input !w-56 text-xs"
            />
            {imageUrl.trim() && (
              <button
                onClick={() => {
                  setImages((prev) => [...prev, imageUrl.trim()])
                  setImageUrl('')
                }}
                className="btn-secondary !px-3 !py-1.5 text-xs"
              >
                加入
              </button>
            )}

            <button
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              className="btn-secondary !px-3 !py-1.5 text-xs"
              title="上傳圖片"
            >
              {uploading ? <Spinner className="w-3 h-3" /> : '🖼️'} 上傳圖片
            </button>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) void handleUpload(f)
              }}
            />

            <div className="flex-1" />

            <span className="text-xs text-gray-400">{content.length}/5000</span>
            <button onClick={handleSubmit} disabled={!canSubmit} className="btn-primary">
              {busy && <Spinner className="w-3.5 h-3.5" />} 發布
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

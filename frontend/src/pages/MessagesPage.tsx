import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { messagesApi, npcApi } from '../api'
import { toMessage } from '../api/client'
import type { Conversation, Message, NpcCharacter } from '../api/types'
import Avatar from '../components/Avatar'
import { EmptyState, ErrorBanner, Spinner } from '../components/Feedback'
import { useAuth } from '../context/AuthContext'
import { formatTime } from '../lib/utils'

/** 短輪詢間隔（毫秒）。MVP 不用 WebSocket，理由見 PRD 技術決策。 */
const POLL_INTERVAL = 3000
/** 等待 NPC 回覆的逾時（毫秒），超過就把「輸入中」收掉 */
const REPLY_TIMEOUT = 120_000

function NpcBadge() {
  return (
    <span className="rounded-full bg-gradient-to-r from-fuchsia-500 to-violet-500 text-white text-[10px] font-bold px-2 py-0.5">
      AI NPC
    </span>
  )
}

export default function MessagesPage() {
  const { user: me } = useAuth()
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [npcs, setNpcs] = useState<NpcCharacter[]>([])
  const [activeId, setActiveId] = useState<number | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [awaitingReply, setAwaitingReply] = useState(false)
  const [showNpcs, setShowNpcs] = useState(true)
  const lastIdRef = useRef<number>(0)
  const bottomRef = useRef<HTMLDivElement>(null)
  const npcIdsRef = useRef<Set<number>>(new Set())

  const loadConversations = useCallback(async () => {
    try {
      const d = await messagesApi.conversations()
      setConversations(d.conversations)
      setActiveId((cur) => cur ?? d.conversations[0]?.id ?? null)
    } catch (err) {
      setError(toMessage(err, '載入對話失敗'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadConversations()
    npcApi
      .list()
      .then((d) => {
        setNpcs(d.npcs)
        npcIdsRef.current = new Set(d.npcs.map((n) => n.id))
      })
      .catch(() => undefined)
  }, [loadConversations])

  // 輪詢對話列表（更新最後訊息與未讀數）
  useEffect(() => {
    const t = window.setInterval(() => {
      void loadConversations()
    }, POLL_INTERVAL)
    return () => window.clearInterval(t)
  }, [loadConversations])

  // 輪詢目前對話的新訊息
  useEffect(() => {
    if (activeId === null) return
    let alive = true

    const poll = async () => {
      try {
        const d = await messagesApi.messages(activeId, lastIdRef.current)
        if (!alive || d.messages.length === 0) return
        lastIdRef.current = d.messages[d.messages.length - 1].id
        setMessages((prev) => [...prev, ...d.messages])
        // 收到對方的回覆就不再顯示「輸入中」
        if (d.messages.some((m) => m.sender_id !== me?.id)) {
          setAwaitingReply(false)
        }
      } catch {
        /* 輪詢失敗就等下一輪，不打擾使用者 */
      }
    }

    void poll()
    const t = window.setInterval(poll, POLL_INTERVAL)
    return () => {
      alive = false
      window.clearInterval(t)
    }
  }, [activeId, me?.id])

  // 切換對話時重載全部訊息
  useEffect(() => {
    if (activeId === null) return
    let alive = true
    lastIdRef.current = 0
    setMessages([])
    setAwaitingReply(false)
    messagesApi
      .messages(activeId, 0, 100)
      .then((d) => {
        if (!alive) return
        setMessages(d.messages)
        lastIdRef.current = d.messages.length ? d.messages[d.messages.length - 1].id : 0
      })
      .catch((err) => {
        if (alive) setError(toMessage(err, '載入訊息失敗'))
      })
    return () => {
      alive = false
    }
  }, [activeId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const active = conversations.find((c) => c.id === activeId) ?? null
  const activeIsNpc = active ? npcIdsRef.current.has(active.other_user?.id ?? -1) : false

  async function send() {
    if (activeId === null) return
    const body = text.trim()
    if (!body) return
    setSending(true)
    setError('')
    try {
      const { message } = await messagesApi.send(activeId, body)
      setMessages((prev) => [...prev, message])
      lastIdRef.current = Math.max(lastIdRef.current, message.id)
      setText('')
      if (activeIsNpc) {
        setAwaitingReply(true)
        // 保險：逾時就把「輸入中」收掉
        window.setTimeout(() => setAwaitingReply(false), REPLY_TIMEOUT)
      }
    } catch (err) {
      setError(toMessage(err, '傳送失敗'))
    } finally {
      setSending(false)
    }
  }

  async function startChatWith(npc: NpcCharacter) {
    try {
      const { conversation } = await messagesApi.createConversation(npc.id)
      setActiveId(conversation.id)
      await loadConversations()
    } catch (err) {
      setError(toMessage(err, '開啟對話失敗'))
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner className="w-7 h-7" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* NPC 角色入口 */}
      {npcs.length > 0 && (
        <div className="card p-4">
          <button
            onClick={() => setShowNpcs((v) => !v)}
            className="w-full flex items-center justify-between"
          >
            <span className="font-semibold text-sm flex items-center gap-2">
              <NpcBadge /> AI 角色
              <span className="text-gray-400 font-normal">（{npcs.length} 個）</span>
            </span>
            <span className="text-gray-400 text-xs">{showNpcs ? '收起 ▲' : '展開 ▼'}</span>
          </button>

          {showNpcs && (
            <div className="mt-3 grid sm:grid-cols-2 gap-2">
              {npcs.map((npc) => (
                <button
                  key={npc.id}
                  onClick={() => startChatWith(npc)}
                  className="flex items-center gap-3 p-2.5 rounded-lg border border-gray-200 hover:bg-gray-50 text-left transition-colors dark:border-gray-700 dark:hover:bg-gray-700/50"
                >
                  <Avatar user={npc} size="md" />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm truncate">{npc.display_name}</p>
                    <p className="text-xs text-gray-500 truncate">{npc.bio ?? '點我開始聊天'}</p>
                  </div>
                  <NpcBadge />
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="card overflow-hidden">
        <div className="grid md:grid-cols-[280px_1fr] min-h-[520px]">
          {/* 對話列表 */}
          <div className="border-r border-gray-200 dark:border-gray-700 max-h-[520px] overflow-y-auto">
            <div className="p-3 border-b border-gray-200 dark:border-gray-700 font-semibold text-sm">
              對話
            </div>
            {conversations.length === 0 ? (
              <EmptyState title="還沒有對話" hint="點上面的 AI 角色開始聊聊" />
            ) : (
              conversations.map((c) => {
                const isNpc = npcIdsRef.current.has(c.other_user?.id ?? -1)
                return (
                  <button
                    key={c.id}
                    onClick={() => setActiveId(c.id)}
                    className={
                      'w-full flex items-center gap-3 p-3 text-left hover:bg-gray-50 dark:hover:bg-gray-700/50 ' +
                      (c.id === activeId ? 'bg-gray-100 dark:bg-gray-700' : '')
                    }
                  >
                    <Avatar user={c.other_user} size="md" />
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm truncate flex items-center gap-1.5">
                        {c.other_user?.display_name ?? '（對話）'}
                        {isNpc && <NpcBadge />}
                      </p>
                      <p className="text-xs text-gray-500 truncate">
                        {c.last_message?.body ?? '（尚無訊息）'}
                      </p>
                    </div>
                    {c.unread_count > 0 && (
                      <span className="rounded-full bg-brand-500 text-white text-[10px] px-1.5 py-0.5 font-bold shrink-0">
                        {c.unread_count}
                      </span>
                    )}
                  </button>
                )
              })
            )}
          </div>

          {/* 聊天視窗 */}
          <div className="flex flex-col">
            {active ? (
              <>
                <div className="p-3 border-b border-gray-200 dark:border-gray-700 flex items-center gap-2">
                  <Avatar user={active.other_user} size="sm" />
                  {active.other_user && (
                    <Link
                      to={`/profile/${active.other_user.id}`}
                      className="font-semibold text-sm hover:underline"
                    >
                      {active.other_user.display_name}
                    </Link>
                  )}
                  {activeIsNpc && <NpcBadge />}
                  <span className="ml-auto text-[10px] text-gray-400">每 3 秒自動更新</span>
                </div>

                <div className="flex-1 p-4 space-y-2 overflow-y-auto max-h-[380px]">
                  {messages.length === 0 && (
                    <p className="text-sm text-gray-400 text-center py-8">開始聊天吧</p>
                  )}
                  {messages.map((m) => {
                    const mine = m.sender_id === me?.id
                    return (
                      <div key={m.id} className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
                        <div
                          className={
                            'max-w-[75%] px-3 py-2 rounded-2xl text-sm whitespace-pre-wrap break-words ' +
                            (mine
                              ? 'bg-brand-500 text-white rounded-br-sm'
                              : 'bg-gray-100 dark:bg-gray-700 rounded-bl-sm')
                          }
                        >
                          {m.body}
                          <div
                            className={
                              'text-[10px] mt-0.5 ' + (mine ? 'text-white/70' : 'text-gray-400')
                            }
                          >
                            {formatTime(m.created_at)}
                          </div>
                        </div>
                      </div>
                    )
                  })}

                  {awaitingReply && (
                    <div className="flex justify-start">
                      <div className="px-3 py-2 rounded-2xl rounded-bl-sm bg-gray-100 dark:bg-gray-700 text-sm text-gray-500 flex items-center gap-2">
                        <Spinner className="w-3.5 h-3.5" />
                        {active.other_user?.display_name} 正在輸入…
                      </div>
                    </div>
                  )}
                  <div ref={bottomRef} />
                </div>

                <div className="p-3 border-t border-gray-200 dark:border-gray-700">
                  {error && (
                    <div className="mb-2">
                      <ErrorBanner message={error} onClose={() => setError('')} />
                    </div>
                  )}
                  <div className="flex gap-2">
                    <input
                      value={text}
                      onChange={(e) => setText(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault()
                          void send()
                        }
                      }}
                      placeholder="輸入訊息…"
                      className="input"
                      maxLength={5000}
                    />
                    <button
                      onClick={send}
                      disabled={sending || !text.trim()}
                      className="btn-primary shrink-0"
                    >
                      {sending && <Spinner className="w-3.5 h-3.5" />} 送出
                    </button>
                  </div>
                </div>
              </>
            ) : (
              <EmptyState title="選一個對話開始聊天" />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

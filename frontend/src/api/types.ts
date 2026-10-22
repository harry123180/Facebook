/** 與後端 API 契約對應的型別（見 docs/API_CONTRACT.md）。 */

export interface User {
  id: number
  username: string
  display_name: string
  avatar_url: string | null
  bio: string | null
  is_verified: boolean
  created_at: string
  email?: string
}

export type Author = Pick<User, 'id' | 'username' | 'display_name' | 'avatar_url'>

export interface PostImage {
  id: number
  url: string
  position: number
}

export interface Post {
  id: number
  content: string
  created_at: string
  author: Author
  images: PostImage[]
  like_count: number
  comment_count: number
  liked_by_me: boolean
}

export interface Comment {
  id: number
  content: string
  created_at: string
  parent_id: number | null
  author: Author
}

export type NotificationType =
  | 'like'
  | 'comment'
  | 'friend_request'
  | 'friend_accept'
  | 'message'

export interface AppNotification {
  id: number
  type: NotificationType
  target_type: string | null
  target_id: number | null
  is_read: boolean
  created_at: string
  actor: Author | null
}

export interface FriendRequest {
  id: number
  direction: 'received' | 'sent'
  status: 'pending' | 'accepted' | 'declined'
  message: string | null
  created_at: string
  responded_at: string | null
  user: Author | null
}

export interface Message {
  id: number
  body: string
  created_at: string
  sender_id: number
}

export interface Conversation {
  id: number
  other_user: Author | null
  last_message: Message | null
  last_message_at: string | null
  unread_count: number
}

export interface Pagination {
  page: number
  limit: number
  total: number
  has_more: boolean
}

export interface Paginated {
  pagination: Pagination
}

/** NPC（AI 角色）：是一個真的使用者，多了角色設定與模型 */
export interface NpcCharacter extends Author {
  bio: string | null
  persona: string
  model: string
  has_session: boolean
}

/** 後端錯誤回應格式：{ error, message } */
export interface ApiErrorBody {
  error: string
  message: string
}

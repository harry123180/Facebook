import { api } from './client'
import type {
  AppNotification,
  Comment,
  Conversation,
  FriendRequest,
  Message,
  NpcCharacter,
  Paginated,
  Post,
  User,
} from './types'

/* ------------------------------------------------------------------ Auth */
export interface RegisterResponse {
  message: string
  email: string
  requires_verification: boolean
  /** 'resend' = 真的寄出去了；'console' = 降級，驗證碼印 log 並直接顯示 */
  delivery?: 'resend' | 'console'
  /** 只有 delivery='console' 時才會有，正式環境不會回傳 */
  dev_code?: string
}

export const authApi = {
  register: (body: {
    email: string
    username: string
    display_name: string
    password: string
  }) => api.post<RegisterResponse>('/auth/register', body).then((r) => r.data),

  resendCode: (email: string) =>
    api.post<{ message: string }>('/auth/resend-code', { email }).then((r) => r.data),

  verify: (email: string, code: string) =>
    api
      .post<{ message: string; user: User }>('/auth/verify', { email, code })
      .then((r) => r.data),

  login: (email: string, password: string) =>
    api.post<{ message: string; user: User }>('/auth/login', { email, password }).then((r) => r.data),

  logout: () => api.post<{ message: string }>('/auth/logout').then((r) => r.data),

  me: () => api.get<{ user: User }>('/auth/me').then((r) => r.data),
}

/* ----------------------------------------------------------------- Posts */
export interface PostList extends Paginated {
  posts: Post[]
}

export const postsApi = {
  list: (page = 1, limit = 20) =>
    api.get<PostList>('/posts', { params: { page, limit } }).then((r) => r.data),

  create: (content: string, imageUrls: string[] = []) =>
    api.post<{ post: Post }>('/posts', { content, image_urls: imageUrls }).then((r) => r.data),

  get: (id: number) => api.get<{ post: Post }>(`/posts/${id}`).then((r) => r.data),

  remove: (id: number) => api.delete(`/posts/${id}`).then(() => undefined),

  like: (id: number) => api.post<{ post: Post; liked: boolean }>(`/posts/${id}/like`).then((r) => r.data),

  unlike: (id: number) =>
    api.delete<{ post: Post; liked: boolean }>(`/posts/${id}/like`).then((r) => r.data),

  comments: (id: number, page = 1, limit = 50) =>
    api
      .get<{ comments: Comment[] } & Paginated>(`/posts/${id}/comments`, {
        params: { page, limit },
      })
      .then((r) => r.data),

  addComment: (id: number, content: string, parentId?: number | null) =>
    api
      .post<{ comment: Comment }>(`/posts/${id}/comments`, {
        content,
        parent_id: parentId ?? null,
      })
      .then((r) => r.data),

  deleteComment: (id: number) => api.delete(`/comments/${id}`).then(() => undefined),
}

/* ----------------------------------------------------------------- Users */
export const usersApi = {
  get: (id: number) =>
    api
      .get<{ user: User; stats: { post_count: number; friend_count: number } }>(`/users/${id}`)
      .then((r) => r.data),

  updateMe: (body: { display_name?: string; bio?: string; avatar_url?: string | null }) =>
    api.patch<{ user: User }>('/users/me', body).then((r) => r.data),

  posts: (id: number, page = 1, limit = 20) =>
    api
      .get<{ posts: Post[] } & Paginated>(`/users/${id}/posts`, { params: { page, limit } })
      .then((r) => r.data),

  myPosts: (page = 1, limit = 20) =>
    api
      .get<{ posts: Post[] } & Paginated>('/users/me/posts', { params: { page, limit } })
      .then((r) => r.data),

  myFriends: () => api.get<{ friends: User[] }>('/users/me/friends').then((r) => r.data),
}

/* ---------------------------------------------------------------- Friends */
export const friendsApi = {
  search: (q: string) =>
    api.get<{ users: User[] }>('/friends/search', { params: { q } }).then((r) => r.data),

  list: () => api.get<{ friends: User[] }>('/friends').then((r) => r.data),

  requests: () =>
    api
      .get<{ received: FriendRequest[]; sent: FriendRequest[] }>('/friends/requests')
      .then((r) => r.data),

  send: (receiverId: number, message?: string) =>
    api
      .post<{ request: FriendRequest }>('/friends/requests', {
        receiver_id: receiverId,
        message: message ?? null,
      })
      .then((r) => r.data),

  accept: (id: number) =>
    api.post<{ request: FriendRequest }>(`/friends/requests/${id}/accept`).then((r) => r.data),

  decline: (id: number) =>
    api.post<{ request: FriendRequest }>(`/friends/requests/${id}/decline`).then((r) => r.data),

  cancel: (id: number) => api.delete(`/friends/requests/${id}`).then(() => undefined),

  remove: (userId: number) => api.delete(`/friends/${userId}`).then(() => undefined),
}

/* ---------------------------------------------------------- Notifications */
export const notificationsApi = {
  list: (page = 1, limit = 20) =>
    api
      .get<{ notifications: AppNotification[]; unread_count: number } & Paginated>(
        '/notifications',
        { params: { page, limit } },
      )
      .then((r) => r.data),

  markRead: (id: number) =>
    api.post<{ notification: AppNotification }>(`/notifications/${id}/read`).then((r) => r.data),

  markAllRead: () =>
    api.post<{ unread_count: number }>('/notifications/read-all').then((r) => r.data),
}

/* --------------------------------------------------------------- Messages */
export const messagesApi = {
  conversations: () =>
    api.get<{ conversations: Conversation[] }>('/messages/conversations').then((r) => r.data),

  createConversation: (userId: number) =>
    api
      .post<{ conversation: Conversation }>('/messages/conversations', { user_id: userId })
      .then((r) => r.data),

  messages: (conversationId: number, afterId = 0, limit = 50) =>
    api
      .get<{ messages: Message[] }>(`/messages/conversations/${conversationId}`, {
        params: { after_id: afterId, limit },
      })
      .then((r) => r.data),

  send: (conversationId: number, body: string) =>
    api
      .post<{ message: Message }>(`/messages/conversations/${conversationId}`, { body })
      .then((r) => r.data),
}

/* ----------------------------------------------------------------- Search */
export const searchApi = {
  query: (q: string, type: 'all' | 'users' | 'posts' = 'all') =>
    api
      .get<{ users: User[]; posts: Post[] }>('/search', { params: { q, type } })
      .then((r) => r.data),
}

/* ---------------------------------------------------------------- Uploads */
export const uploadsApi = {
  image: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api
      .post<{ url: string }>('/uploads', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data)
  },
}

/* ------------------------------------------------------------------- NPC */
export const npcApi = {
  list: () =>
    api
      .get<{ npcs: NpcCharacter[]; suggested_models: string[] }>('/npc')
      .then((r) => r.data),

  create: (body: {
    username: string
    display_name: string
    persona: string
    model?: string
    bio?: string
  }) => api.post<{ npc: NpcCharacter }>('/npc', body).then((r) => r.data),

  remove: (id: number) => api.delete(`/npc/${id}`).then(() => undefined),
}

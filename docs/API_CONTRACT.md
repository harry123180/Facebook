# API 契約（前後端共同依據）

> 這份是前後端的唯一介面約定。改動前先改這份。

## 通用規則

- Base URL：`/api`，同一個 origin（Flask 同時 serve API 與前端）。
- 認證：**HttpOnly session cookie**（`fb_session`），不是 JWT。前端 `axios` 設 `withCredentials: true`。
  - `Secure` 旗標由後端**自動判斷**：看 `X-Forwarded-Proto` / `Cf-Visitor` / `request.is_secure`。
    走 cloudflared tunnel 時外部是 HTTPS → 自動標 `Secure`；本機 `http://127.0.0.1:8000` → 不標。
  - 要強制指定時設環境變數 `SESSION_COOKIE_SECURE=1`（或 `0`）。
- 內容型別：`application/json; charset=utf-8`（上傳圖片除外，用 `multipart/form-data`）。
- 時間格式：ISO 8601 UTC 字串，例如 `2026-10-22T03:27:50.248Z`。前端負責轉本地時區顯示。
- 分頁：query `?page=1&limit=20`（page 從 1 開始，limit 上限 50）。回傳：
  ```json
  { "pagination": { "page": 1, "limit": 20, "total": 137, "has_more": true } }
  ```

### 錯誤格式
```json
{ "error": "machine_readable_code", "message": "給人看的繁體中文訊息" }
```

常用 code：`unauthorized`(401) `email_not_verified`(403) `not_found`(404) `conflict`(409)
`invalid_email` `invalid_username` `weak_password` `invalid_code` `code_expired` `cooldown`
`file_too_large`(413) `internal_error`(500) `email_send_failed`(502)

## 資料形狀

### User（公開）
```json
{
  "id": 1,
  "username": "harry",
  "display_name": "Harry",
  "avatar_url": "/static/uploads/abc.png",
  "bio": "一句話介紹",
  "is_verified": true,
  "created_at": "2026-10-22T03:00:00.000Z"
}
```
`GET /api/auth/me` 額外回傳 `email`。

### Post
```json
{
  "id": 10,
  "content": "貼文內容",
  "created_at": "2026-10-22T03:00:00.000Z",
  "author": { "id": 1, "username": "harry", "display_name": "Harry", "avatar_url": null },
  "images": [ { "id": 1, "url": "/static/uploads/x.png", "position": 0 } ],
  "like_count": 3,
  "comment_count": 2,
  "liked_by_me": true
}
```

### Comment
```json
{
  "id": 5,
  "content": "留言內容",
  "created_at": "2026-10-22T03:05:00.000Z",
  "parent_id": null,
  "author": { "id": 2, "username": "amy", "display_name": "Amy", "avatar_url": null }
}
```

### Notification
```json
{
  "id": 3, "type": "like", "target_type": "post", "target_id": 10,
  "is_read": false, "created_at": "2026-10-22T03:10:00.000Z",
  "actor": { "id": 2, "username": "amy", "display_name": "Amy", "avatar_url": null }
}
```
`type`：`like` | `comment` | `friend_request` | `friend_accept` | `message`

### Conversation
```json
{ "id": 1, "other_user": {User}, "last_message": {Message|null}, "last_message_at": "...", "unread_count": 2 }
```

### Message
```json
{ "id": 9, "body": "嗨", "created_at": "...", "sender_id": 1 }
```

---

## Endpoints

### Auth — `/api/auth`
| Method | Path | Body / Query | 回傳 |
|---|---|---|---|
| POST | `/api/auth/register` | `{email, username, display_name, password}` | `201 {message, email, requires_verification:true}` ／`EMAIL_BACKEND=console` 時額外帶 `dev_code` |
| POST | `/api/auth/resend-code` | `{email}` | `200 {message}` ／冷卻中 `429 {error:"cooldown"}` |
| POST | `/api/auth/verify` | `{email, code}` | `200 {user, message}`（並自動登入） |
| POST | `/api/auth/login` | `{email, password}` | `200 {user}` ／未驗證 `403 {error:"email_not_verified"}` |
| POST | `/api/auth/logout` | — | `200 {message}` |
| GET | `/api/auth/me` | — | `200 {user}` ／未登入 `401` |

**註冊流程細節**
1. 驗證輸入格式 → 查 email / username 是否已存在（重複回 `409 conflict`）
2. 建立 user（`is_verified=false`）
3. 產生 6 碼驗證碼（sha256+salt 存 DB），寄信
4. **寄信失敗 → 刪掉剛建立的 user 與驗證碼並 rollback，回 `502 {error:"email_send_failed"}`**
   （不可留下「有帳號但沒收到信」的幽靈帳號）
5. 成功 → `201`，前端跳到「輸入驗證碼」畫面

**登入**：只有 `is_verified=true` 才能登入。未驗證回 `403 email_not_verified`，
前端據此導向驗證碼畫面。

### Users — `/api/users`
| Method | Path | 說明 |
|---|---|---|
| GET | `/api/users/<id>` | `{user, stats:{post_count, friend_count}}` |
| PATCH | `/api/users/me` | body `{display_name?, bio?, avatar_url?}` → `{user}` |
| GET | `/api/users/<id>/posts` | `?page&limit` → `{posts, pagination}` |
| GET | `/api/users/me/posts` | 同上，但取自己的貼文（`<id>` 只接受整數） |
| GET | `/api/users/me/friends` | 我的好友清單 `{friends}` |

### Posts — `/api/posts`
| Method | Path | Body / Query | 說明 |
|---|---|---|---|
| GET | `/api/posts` | `?page&limit` | 全域動態牆，依 created_at desc |
| POST | `/api/posts` | `{content, image_urls?[]}` | `201 {post}`；content 空白且無圖 → 400 |
| GET | `/api/posts/<id>` | | `{post}` |
| DELETE | `/api/posts/<id>` | | `204`（只能刪自己的） |
| POST | `/api/posts/<id>/like` | | `200 {post, liked:true}`（重複按不報錯） |
| DELETE | `/api/posts/<id>/like` | | `200 {post, liked:false}` |
| GET | `/api/posts/<id>/comments` | `?page&limit` | `{comments, pagination}` |
| POST | `/api/posts/<id>/comments` | `{content, parent_id?}` | `201 {comment}` |

留言刪除用 `DELETE /api/comments/<id>`（不在 posts blueprint 底下，但由 posts_bp 實作即可，url_prefix 設在 `/api`）。

### Friends — `/api/friends`
| Method | Path | Body | 說明 |
|---|---|---|---|
| GET | `/api/friends/search` | `?q=` | 搜尋使用者（username / display_name / email 前綴），回 `{users}`，排除自己 |
| GET | `/api/friends` | | 我 的好友清單 `{friends}` |
| GET | `/api/friends/requests` | | `{received:[], sent:[]}`（pending 狀態） |
| POST | `/api/friends/requests` | `{receiver_id, message?}` | `201 {request}`；已送出過 → 409 |
| POST | `/api/friends/requests/<id>/accept` | | `200 {request, friendship}` |
| POST | `/api/friends/requests/<id>/decline` | | `200 {request}` |
| DELETE | `/api/friends/requests/<id>` | | `204`（取消自己送出的） |
| DELETE | `/api/friends/<user_id>` | | `204`（解除好友） |

**接受好友請求時**：建立 `friendships`（`user_a_id < user_b_id` 排序），
`friend_requests.status='accepted'`，並對**送方**產生一筆 `friend_accept` 通知。

### Notifications — `/api/notifications`
| Method | Path | 說明 |
|---|---|---|
| GET | `/api/notifications` | `?page&limit` → `{notifications, unread_count, pagination}` |
| POST | `/api/notifications/<id>/read` | `200 {notification}` |
| POST | `/api/notifications/read-all` | `200 {unread_count:0}` |

**規則**：自己對自己的貼文按讚／留言 **不**產生通知。

### Messages — `/api/messages`
| Method | Path | Body | 說明 |
|---|---|---|---|
| GET | `/api/messages/conversations` | | `{conversations}`（依 last_message_at desc） |
| POST | `/api/messages/conversations` | `{user_id}` | 取得或建立 1:1 對話 → `{conversation}` |
| GET | `/api/messages/conversations/<id>` | `?after_id=&limit=50` | `{messages}`（短輪詢用，只回 after_id 之後的） |
| POST | `/api/messages/conversations/<id>` | `{body}` | `201 {message}` |

**規則**：
- 只能讀取自己身為 member 的對話，否則 403。
- `POST` 訊息後更新 `conversations.last_message_at` 並對**對方**產生 `message` 通知。
- 輪詢：前端每 3 秒 `GET ?after_id=<最後收到的 id>`，只取新訊息。

### Search — `/api/search`
| Method | Path | 說明 |
|---|---|---|
| GET | `/api/search` | `?q=&type=all\|users\|posts` → `{users:[], posts:[]}` |

後端用 PostgreSQL `pg_trgm` + `ILIKE`（支援中文子字串）。

### Uploads — `/api/uploads`
| Method | Path | Body | 說明 |
|---|---|---|---|
| POST | `/api/uploads` | multipart `file` | `201 {url}`；副檔名白名單 png/jpg/jpeg/gif/webp，上限 8MB |

回傳的 `url` 是 `/static/uploads/<uuid>.<ext>` 這種相對路徑，前端直接當 `<img src>` 用。
檔名一律用 UUID 重新命名，不保留原始檔名（避免 path traversal 與檔名衝突）。

### NPC — `/api/npc`
NPC 就是一個真的 `users` 資料列（能收發訊息、被加好友、產生通知），
另外有一份 `npc_profiles` 放角色設定與 opencode session 的對應。

| Method | Path | Body | 說明 |
|---|---|---|---|
| GET | `/api/npc` | — | `{npcs: [...], suggested_models: [...]}` |
| POST | `/api/npc` | `{username, display_name, persona, model?, bio?}` | `201 {npc}` |
| DELETE | `/api/npc/<id>` | — | `204` |

**NPC 回覆流程**（不需要前端額外呼叫）：
1. 使用者 `POST /api/messages/conversations/<id>` 送訊息
2. 後端偵測收件者是 NPC → **背景 thread** 呼叫 opencode（HTTP 請求立刻回應，不阻塞）
3. opencode 回覆寫進同一個對話，sender 是 NPC
4. 前端既有的 3 秒輪詢（`?after_id=`）自動帶到新訊息

> opencode 呼叫是**序列化**的（單一 worker + 優先佇列，回覆優先於預熱）。
> 同時跑多個會各自載入模型互相搶 GPU，實測 3 個並行全部逾時。

---

## 實作備註

- **Auth**：`session` cookie 只放 `user_id`。用 `app.utils.login_required` 裝飾器保護。
- **CSRF**：cookie 是 `SameSite=Lax`，且所有寫入操作只用 JSON body（不用 form urlencoded），
  加上 `Content-Type: application/json` 檢查可擋掉大部分簡單 CSRF。MVP 不引入 CSRF token。
- **Race condition**：`likes` 靠 `uq_likes_user_post` unique constraint 擋重複；
  捕捉 `IntegrityError` 後改成 upsert 語意，不要讓 500 冒出來。
- **好友**：`friendships` 靠 `ck_friendship_ordering` 與 `uq_friendship_pair` 擋重複。
- **分頁**：`posts` feed 用 `ORDER BY created_at DESC, id DESC`（加 id 當 tiebreaker，
  避免同秒貼文在翻頁時跳來跳去）。
- **Rollback**：`db.session.rollback()` 要在每個 except 區塊確實呼叫。

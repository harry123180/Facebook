# Facebook MVP

一個可運作的 Facebook 社群 clone MVP。
**React + TypeScript (Vite)** 前端 · **Flask** 後端 · **PostgreSQL 17** 資料庫 · **Resend** 寄驗證碼 · **cloudflared Quick Tunnel** 對外。

> 本專案與 Meta / Facebook 平台無關，不接入 Graph API，所有資料存放於自有資料庫。

---

## 文件

| 文件 | 內容 |
|---|---|
| [`_bmad-output/prd.md`](_bmad-output/prd.md) | 產品需求文件（範圍、功能需求、驗收標準、風險） |
| [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) | 前後端 API 契約 |
| [`_bmad-output/analysis/mvp-scope-analysis.md`](_bmad-output/analysis/mvp-scope-analysis.md) | MVP 範圍分析 |

## 現況

| 項目 | 狀態 |
|---|---|
| 後端 API | 39 條路由，8 個 blueprint |
| 前端 | 11 個路由，Tailwind v4 深色模式 |
| 資料庫 | 13 張表 + migration（含 `pg_trgm`） |
| 端到端測試 | `backend/scripts/smoke_test.py` — **102 項全過**（本機與外網 tunnel 都驗過） |
| 部署 | cloudflared Quick Tunnel，單一 origin |

---

## 環境需求

- Python 3.11+
- Node.js 20+ / pnpm
- Docker Desktop（只需要跑 PostgreSQL）
- cloudflared（`winget install Cloudflare.cloudflared`）
- Resend API Key（[resend.com/api-keys](https://resend.com/api-keys)）

---

## 快速開始

### 1. 設定環境變數

```powershell
Copy-Item .env.example .env
```

`.env` 至少要填：

```dotenv
POSTGRES_PASSWORD=<隨機密碼>
DATABASE_URL=postgresql+psycopg://fbapp:<同一個密碼>@127.0.0.1:5435/facebook_mvp
SECRET_KEY=<隨機字串>
RESEND_API_KEY=re_xxxxxxxx
```

> `RESEND_API_KEY` 目前用的是 **send-only restricted key**，只能寄信。
> 所以 `domains` / `contacts` / `templates` / `usage` 這類 Resend 查詢 API 會回 401，
> 這是預期行為，MVP 不依賴那些 API。
>
> ### ⚠️ 關於 Resend 的 testing mode
>
> Resend 帳號在還沒驗證網域前處於 **testing mode**，只能寄信給：
> - `onboarding@resend.dev` / `delivered@resend.dev` / `bounce@resend.dev` 等測試信箱
> - **帳號註冊者本人的信箱**（本案是 `harry123180@gmail.com`）
>
> 寄給其他人的信箱會被 Resend 擋下：
> `You can only send testing emails to your own email address (...)`
>
> 因此本專案預設 `EMAIL_BACKEND=auto`：
>
> | `EMAIL_BACKEND` | 行為 |
> |---|---|
> | `auto`（預設） | **先試真實寄信**。若 Resend 因 testing mode 擋下收件人，自動降級成 console（驗證碼印在 `backend/logs/server.log` 並在 API 回應裡帶 `dev_code`），註冊流程不會卡死 |
> | `console` | 一律不寄信，驗證碼印 log 並回傳 `dev_code` |
> | `resend` | 一律真實寄信，失敗就回 `502 email_send_failed` |
>
> API 回應會帶 `delivery` 欄位說明實際走了哪條路：
> - `delivery: "resend"` → 郵件真的寄出去了
> - `delivery: "console"` → 降級，驗證碼直接顯示在前端畫面上
>
> **要讓任意使用者收到真實驗證信**，需要先在 Resend 後台驗證一個網域
> （設定 SPF / DKIM / DMARC 的 DNS 記錄），然後把 `RESEND_FROM_EMAIL` 改成該網域的信箱。
> 驗證網域後 `auto` 模式就會對所有收件人走真實寄信。

### 2. 啟動資料庫

```powershell
docker compose up -d db
```

PostgreSQL 跑在 `127.0.0.1:5435`（刻意避開本機既有的 5432 服務），資料庫名 `facebook_mvp`。

### 3. 安裝後端依賴

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 4. 套用資料庫 migration

```powershell
cd backend
$envMap = @{}
Get-Content ..\.env | ForEach-Object { if ($_ -match "^([A-Z_]+)=(.*)$") { $envMap[$matches[1]] = $matches[2] } }
$env:DATABASE_URL = $envMap['DATABASE_URL']
$env:FLASK_APP = "wsgi.py"
.\.venv\Scripts\python.exe -m flask db upgrade
```

### 5. 安裝前端依賴

```powershell
cd frontend
pnpm install
```

---

## 啟動

### 開發模式（前後端分離，Vite proxy）

```powershell
.\scripts\dev.ps1
```

- 前端 http://localhost:5173
- 後端 http://127.0.0.1:8000/api/health

### 正式模式（單一 origin + 臨時網址）

```powershell
.\scripts\serve.ps1
```

會 build 前端、用 waitress 啟動 Flask（同時 serve API 與前端靜態檔），
再開 cloudflared Quick Tunnel。網址會印在畫面上，也會存到 `.tunnel-url`：

```
https://<random-word>.trycloudflare.com
```

> 這個網址是**臨時的**：關掉腳本就失效，無需帳號，適合 demo。
> 需要固定網址請改用 Cloudflare Named Tunnel。
>
> 收掉所有服務：`.\scripts\stop-all.ps1`

### 跑端到端測試

```powershell
cd backend
$env:BASE_URL = "http://127.0.0.1:8000"   # 或填 tunnel 網址
.\.venv\Scripts\python.exe scripts\smoke_test.py
```

會建立兩個測試帳號、跑完註冊→驗證→發文→按讚→留言→好友→私訊→上傳→搜尋
全流程，最後自動清掉測試資料。

### 診斷腳本

| 腳本 | 用途 |
|---|---|
| `backend/scripts/smoke_test.py` | 端到端測試（103 項） |
| `backend/scripts/test_resend.py` | 實測 Resend 能寄到哪些位址 |
| `backend/scripts/test_delivery_modes.py` | 驗證 `auto` 模式的真寄 / 降級行為 |

---

## 專案結構

```
Facebook/
├── backend/
│   ├── app/
│   │   ├── __init__.py          # app 工廠、錯誤處理、SPA fallback
│   │   ├── config.py            # 環境設定
│   │   ├── extensions.py        # db / migrate / cors 實例
│   │   ├── models.py            # 13 張表的 SQLAlchemy 模型
│   │   ├── utils.py             # 認證、驗證、錯誤、分頁
│   │   ├── api/                 # 8 個 blueprint
│   │   └── services/            # resend 寄信、驗證碼流程
│   ├── migrations/              # Alembic
│   ├── scripts/smoke_test.py    # 端到端測試
│   └── wsgi.py
├── frontend/
│   ├── src/
│   │   ├── api/                 # axios 封裝
│   │   ├── components/
│   │   ├── context/             # AuthContext
│   │   ├── hooks/
│   │   └── pages/
│   └── vite.config.ts           # 含 /api proxy 與 tailwind plugin
├── docs/API_CONTRACT.md
├── scripts/dev.ps1
├── scripts/serve.ps1
├── docker-compose.yml           # PostgreSQL 17
└── .env.example
```

---

## 註冊流程

1. `POST /api/auth/register` → 建立 user（`is_verified=false`）
2. 產生 6 碼驗證碼（sha256+salt 存 DB），透過 Resend 寄出
3. 寄信失敗 → **rollback 並刪掉剛建立的 user**（不留幽靈帳號）
4. `POST /api/auth/verify` → 驗證成功 → 設 `is_verified=true` 並自動登入
5. `POST /api/auth/login` → 登入（未驗證會回 403）

驗證碼規則：10 分鐘有效、60 秒重發冷卻、最多嘗試 5 次。

---

## AI NPC 角色（用 opencode 當 LLM 引擎）

專案內建幾個 AI NPC，可以直接用 Messenger 介面跟他們聊天，測試私訊的完整路徑
（3 秒輪詢、未讀數、通知、對話列表）。

預設角色：

| 角色 | 個性 |
|---|---|
| 小美 | 活潑開朗的台灣女生 |
| 阿哲 | 理性直接的資深工程師 |
| 喵喵 | 傲嬌貓娘 |

### 建立 NPC

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\create_npcs.py
```

也可以透過 API 建立（`POST /api/npc`）：

```json
{
  "username": "npc_xiaomei",
  "display_name": "小美",
  "persona": "你是「小美」，一個 24 歲的台灣女生，個性活潑開朗…",
  "model": "ollama/qwen36-nothink",
  "bio": "活潑開朗的台灣女生，很愛聊天 ☀️"
}
```

### 運作原理

```
你在前端傳訊息
  → POST /api/messages/conversations/<id>
  → 偵測收件者是 NPC
  → 背景 thread 呼叫 opencode（HTTP 立刻回應，不阻塞）
  → opencode 回覆寫進同一個對話
  → 前端既有的 3 秒輪詢自動帶到新訊息
```

NPC 的回覆會帶進 opencode session，所以**它記得聊天脈絡**
（你問「剛剛我說什麼」它會答得出來）。

### 效能

| 情境 | 耗時 |
|---|---|
| 第一次回覆（session 還沒建） | ~30s |
| 第一次回覆（已預熱） | ~12s |
| 後續回覆 | ~12s |

建立 NPC 時會在背景「預熱」session（`NPC_WARMUP=1`），讓第一則回覆不用等。
另外 opencode 呼叫是**序列化**的：同時跑多個會各自載入模型互相搶 GPU，
實測 3 個並行全部逾時（>120s），改成循序執行就正常了。

### 用到的 opencode 參數

```
opencode run --session <id> --model <provider/model> --format json "<prompt>"
```

- `--session`：每個 NPC 一個 session，帶 `--session` 重用比每次新建快 4 倍（41s → 10s）
- `--format json`：每行一個 JSON event，取 `type=="text"` 的 `part.text`
- 執行時會設 `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1` 與
  `OPENCODE_DISABLE_CLAUDE_CODE_PROMPT=1`，避免載入全域的 ~80 個 skill

### 診斷腳本

| 腳本 | 用途 |
|---|---|
| `backend/scripts/create_npcs.py` | 建立預設的 3 個 NPC |
| `backend/scripts/test_npc_chat.py` | 端到端測試 NPC 聊天（回覆內容、session 記憶、通知） |

---

## 已知限制

- **私人訊息用 3 秒短輪詢**，不是 WebSocket。Quick Tunnel 對 WebSocket 支援較脆弱，取穩定優先。
- **動態牆是全域時間排序**，沒有「僅好友」篩選。
- **Resend key 是 send-only**，所有讀取型 Resend API 都不可用。
- **Resend 帳號在 testing mode**，寄不到第三方信箱（會自動降級成 console，見上文）。
- **沒有忘記密碼功能**（MVP 非目標）。
- **沒有 Email 推播通知**，通知只在站內。

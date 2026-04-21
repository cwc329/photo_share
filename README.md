# photo-share

整合 **Facebook / Instagram Business** 登入與排程發文的單體應用：後端為 **FastAPI**，前端為 **Vue 3 + Vite**，上傳圖檔存放於本機 `uploads/`（或 Docker volume）。

---

## 功能概覽

- Facebook Login for Business：授權、取得 Page、關聯 IG 商業帳號
- Instagram Business Login：獨立 IG 登入流程
- 圖片上傳、排程發佈（APScheduler）
- 上傳後以 **exiftool**（主）／**piexif**（備援）讀取 EXIF，提供 hashtag 建議

---

## 專案結構

```
photo_share/
├── backend/              # FastAPI
│   ├── main.py           # 應用入口、Session / CORS、靜態 /uploads
│   ├── config.py         # 環境變數
│   ├── routers/          # auth, media, posts
│   ├── services/         # meta_api, scheduler, exif_service, image_upload_prep
│   ├── logging_uvicorn.yaml
│   └── Dockerfile
├── frontend/             # Vue 3 + Vite
│   ├── src/
│   └── Dockerfile
├── uploads/              # 上傳檔（僅 .gitkeep 進版控，實際檔案被 .gitignore）
├── docker-compose.yml
├── .env.example          # 環境變數範本（勿放真實密鑰）
└── README.md
```

---

## 環境需求

| 項目 | 說明 |
|------|------|
| Python | 建議 **3.12**（與 `backend/Dockerfile` 一致） |
| Node.js | **22**（見根目錄 `.nvmrc`） |
| exiftool | 建議安裝；未安裝時 hashtag 讀取會退回 piexif（功能較受限） |
| Docker | 選用；用於與正式環境一致的 compose 部署 |

---

## 快速設定（環境變數）

1. 複製範本並自行填寫（**不要** commit 真實 `.env`）：

   ```bash
   cp .env.example .env
   ```

2. 機密與網址請參考根目錄 **`.env.example`** 內註解；常見變數包括：

   - `FRONTEND_URL`：前端來源（CORS `allow_origins` 只允許此值）
   - `VITE_API_BASE_URL`：**build 時**燒進前端；執行時 axios 以此為 API 基底（須與後端實際網址一致）
   - `SERVER_BASE_URL`：對外公開的 API base（例如 Meta IG `image_url`）
   - `META_*` / `META_IG_*`：Meta 應用程式與 OAuth redirect
   - `SECRET_KEY`、`COOKIE_DOMAIN`、`COOKIE_SECURE`、`DATABASE_URL`
   - `TOKEN_ENCRYPTION_KEY`：**Fernet** 金鑰，用於加密寫入 DB 的 access token（OAuth 回存前必填；見 `.env.example` 產生指令）
   - Docker 對外埠：`FRONTEND_BIND` / `FRONTEND_PORT`、`BACKEND_BIND` / `BACKEND_PORT`

### 既有 DB：把明文 token 改成密文（一次性）

1. 先在 `.env` 設好 **`TOKEN_ENCRYPTION_KEY`**（之後與正式環境請固定同一支金鑰，或規劃輪替流程）。
2. 在 **`backend/`** 目錄執行：

   ```bash
   cd backend
   python scripts/migrate_encrypt_tokens.py --dry-run
   python scripts/migrate_encrypt_tokens.py
   ```

腳本會略過「已能用目前金鑰成功解密」的欄位，只把仍為明文的 `users.user_access_token`、`pages.page_access_token`、`ig_accounts.access_token` 加密後寫回。

---

## 本機開發（不使用 Docker）

### 後端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8001 --log-config logging_uvicorn.yaml
```

- 健康檢查：`GET http://localhost:8001/health`
- 預設 SQLite 路徑見 `config.py` 的 `DATABASE_URL` 預設值；本機可改 `.env` 指向你既有的 db 檔（建議放在 repo 外，例如 `~/photo_share_data/...`）。

### 前端

```bash
cd frontend
npm ci
```

在 `frontend/` 建立 `.env.local`（已被 gitignore），例如：

```env
VITE_API_BASE_URL=http://localhost:8001
```

```bash
npm run dev
```

- 前端必須以 **`withCredentials`** 呼叫 API（已於 `src/api.js` 設定），後端 `FRONTEND_URL` 需與 Vite 顯示的 origin 一致（預設常為 `http://localhost:5173`）。

---

## Docker Compose 部署

根目錄：

```bash
docker compose --env-file .env.production up -d --build
```

說明：

- **backend** 使用 `env_file: .env.production`（請在主機準備該檔，勿進版控）。
- **frontend** build 需要 **`VITE_API_BASE_URL`**（compose 會展開 `${VITE_API_BASE_URL:?...}`，未設會直接失敗）。
- 對外埠預設：`127.0.0.1:3000` → 前端 Nginx、`127.0.0.1:3001` → 後端（可於 `.env` 調整 `FRONTEND_*` / `BACKEND_*`）。
- SQLite 預設寫入 container 內 **`/data`**，並以 **named volume `db_data`** 持久化。
- 上傳目錄：`./uploads` bind mount 至後端。

若前後端分開網域（例如 Cloudflare Tunnel 指到不同 port），請確保：

- `FRONTEND_URL` 與實際前端 HTTPS origin 完全一致
- 跨子網域 session 時：`COOKIE_DOMAIN`、**`COOKIE_SECURE=true`**（HTTPS）設定正確

---

## 常用指令

| 目的 | 指令 |
|------|------|
| 後端本機 | `cd backend && uvicorn main:app --reload --port 8001 --log-config logging_uvicorn.yaml` |
| 前端本機 | `cd frontend && npm run dev` |
| Compose 重建 | `docker compose up -d --build` |

---

## 授權

本 repo 若未另附 `LICENSE` 檔，預設為「未宣告授權」；若要開源請自行補上授權條款。

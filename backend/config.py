"""集中從環境變數載入設定；其餘模組由此匯入。"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _bool_env(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() == "true"


def _normalize_database_url(url: str) -> str:
    if url.startswith("sqlite:///") and not url.startswith("sqlite+aiosqlite"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return url


# --- App / session ---
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
COOKIE_DOMAIN: str | None = os.getenv("COOKIE_DOMAIN") or None
COOKIE_SECURE = _bool_env("COOKIE_SECURE", "false")

# --- Token storage（Fernet）---
# 產生方式：python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
TOKEN_ENCRYPTION_KEY = os.getenv("TOKEN_ENCRYPTION_KEY", "")

# --- Database ---
DATABASE_URL = _normalize_database_url(
    os.getenv("DATABASE_URL", "sqlite+aiosqlite:////data/photo_share.db"))

# --- Meta / Facebook Login ---
META_APP_ID = os.getenv("META_APP_ID", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")
META_REDIRECT_URI = os.getenv("META_REDIRECT_URI", "http://localhost:8001/auth/callback")

# --- Meta / Instagram Business Login ---
META_IG_APP_ID = os.getenv("META_IG_APP_ID", "")
META_IG_APP_SECRET = os.getenv("META_IG_APP_SECRET", "")
META_IG_REDIRECT_URI = os.getenv("META_IG_REDIRECT_URI", "http://localhost:8001/auth/ig/callback")

# --- Public API base（IG image_url 等）---
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "http://localhost:8001")

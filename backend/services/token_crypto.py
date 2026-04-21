"""以 Fernet 加密／解密存於資料庫的 access token。"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from config import TOKEN_ENCRYPTION_KEY

# 注意：不可與函式同名；`def _fernet` 會覆蓋模組層 `_fernet` 變數導致回傳成函式物件。
_fernet_instance: Fernet | None = None


def _get_fernet() -> Fernet | None:
    global _fernet_instance
    if not TOKEN_ENCRYPTION_KEY:
        return None
    if _fernet_instance is None:
        _fernet_instance = Fernet(TOKEN_ENCRYPTION_KEY.strip().encode())
    return _fernet_instance


def encrypt_token(plain: str) -> str:
    """寫入 DB 前加密；未設定 TOKEN_ENCRYPTION_KEY 則拋錯。"""
    f = _get_fernet()
    if f is None:
        raise RuntimeError(
            "TOKEN_ENCRYPTION_KEY is required to store access tokens. "
            "Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return f.encrypt(plain.encode()).decode()


def decrypt_token(stored: str) -> str:
    """從 DB 讀出後解密；若無金鑰或為舊版明文則原樣回傳。"""
    if not stored:
        return stored
    f = _get_fernet()
    if f is None:
        return stored
    try:
        return f.decrypt(stored.encode()).decode()
    except (InvalidToken, ValueError):
        return stored


def token_is_encrypted(stored: str) -> bool:
    """若字串可用目前 TOKEN_ENCRYPTION_KEY 成功解密，視為已是 Fernet 密文（遷移用）。"""
    if not stored or not TOKEN_ENCRYPTION_KEY.strip():
        return False
    try:
        Fernet(TOKEN_ENCRYPTION_KEY.strip().encode()).decrypt(stored.encode())
        return True
    except (InvalidToken, ValueError):
        return False

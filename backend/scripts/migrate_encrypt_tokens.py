"""
一次性：將 DB 內仍為明文的 access token 改為 Fernet 密文。

使用前請在環境變數設定 TOKEN_ENCRYPTION_KEY（與執行中後端相同）。

在 repo 根目錄或 backend 目錄皆可執行：

  cd backend && python scripts/migrate_encrypt_tokens.py
  cd backend && python scripts/migrate_encrypt_tokens.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# 先載入專案根目錄 .env（再 import config）
_root = Path(__file__).resolve().parents[2]
_backend = Path(__file__).resolve().parents[1]
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

from dotenv import load_dotenv

load_dotenv(_root / ".env")
load_dotenv(_backend / ".env", override=False)

from sqlalchemy import select

from config import TOKEN_ENCRYPTION_KEY
from database import AsyncSessionLocal
from models import IgAccount, Page, User
from services.token_crypto import encrypt_token, token_is_encrypted


async def _run(dry_run: bool) -> None:
    if not TOKEN_ENCRYPTION_KEY.strip():
        print("ERROR: 請先在 .env 設定 TOKEN_ENCRYPTION_KEY（與執行後端時相同）", file=sys.stderr)
        sys.exit(1)
    updated = 0
    async with AsyncSessionLocal() as db:
        users = (await db.execute(select(User))).scalars().all()
        for u in users:
            if not u.user_access_token or token_is_encrypted(u.user_access_token):
                continue
            enc = encrypt_token(u.user_access_token)
            if not dry_run:
                u.user_access_token = enc
            updated += 1

        pages = (await db.execute(select(Page))).scalars().all()
        for p in pages:
            if not p.page_access_token or token_is_encrypted(p.page_access_token):
                continue
            enc = encrypt_token(p.page_access_token)
            if not dry_run:
                p.page_access_token = enc
            updated += 1

        igs = (await db.execute(select(IgAccount))).scalars().all()
        for ig in igs:
            if not ig.access_token or token_is_encrypted(ig.access_token):
                continue
            enc = encrypt_token(ig.access_token)
            if not dry_run:
                ig.access_token = enc
            updated += 1

        if not dry_run and updated:
            await db.commit()

    action = "Would update" if dry_run else "Updated"
    print(f"{action} {updated} token field(s).")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="只列出會加密的筆數，不寫回 DB")
    args = p.parse_args()
    asyncio.run(_run(args.dry_run))


if __name__ == "__main__":
    main()

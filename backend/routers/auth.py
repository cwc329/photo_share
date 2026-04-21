import secrets
import time
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import (FRONTEND_URL, META_APP_ID, META_APP_SECRET, META_IG_APP_ID, META_IG_APP_SECRET,
                    META_IG_REDIRECT_URI, META_REDIRECT_URI)
from database import get_db
from models import IgAccount, Page, User
from services.token_crypto import encrypt_token

router = APIRouter()

FB_SCOPES = ",".join([
    "pages_manage_posts",
    "pages_read_engagement",
    "pages_show_list",
    "instagram_basic",
    "instagram_content_publish",
])
IG_SCOPES = ",".join([
    "instagram_business_basic",
    "instagram_business_content_publish",
])

# ── State store（in-memory，單 process 足夠） ──────────────────
# state_token -> (created_at, session_payload | None)
# session_payload: {"user_id": int} or {"ig_account_id": int}
_STATE_TTL = 300  # 5 minutes
_state_store: dict[str, tuple[float, dict | None]] = {}


def _new_state() -> str:
    state = secrets.token_urlsafe(32)
    _state_store[state] = (time.monotonic(), None)
    return state


def _store_payload(state: str, payload: dict) -> bool:
    if state not in _state_store:
        return False
    _state_store[state] = (time.monotonic(), payload)
    return True


def _consume_state(state: str) -> dict | None:
    """Return payload and delete the state (one-time use)."""
    entry = _state_store.pop(state, None)
    if entry is None:
        return None
    created_at, payload = entry
    if time.monotonic() - created_at > _STATE_TTL:
        return None
    return payload


def _purge_expired():
    now = time.monotonic()
    expired = [k for k, (t, _) in _state_store.items() if now - t > _STATE_TTL]
    for k in expired:
        _state_store.pop(k, None)


# ── Facebook Login ────────────────────────────────────────────


@router.get("/login")
async def fb_login(request: Request):
    _purge_expired()
    state = _new_state()
    url = ("https://www.facebook.com/v25.0/dialog/oauth"
           f"?client_id={META_APP_ID}"
           f"&redirect_uri={META_REDIRECT_URI}"
           f"&scope={FB_SCOPES}"
           f"&state={state}"
           "&response_type=code")
    return RedirectResponse(url)


@router.get("/callback")
async def fb_callback(
        request: Request,
        code: str = "",
        state: str = "",
        error: str = "",
        db: AsyncSession = Depends(get_db),
):
    if error:
        return RedirectResponse(f"{FRONTEND_URL}/oauth/callback?error={error}")
    if not state or state not in _state_store:
        return RedirectResponse(f"{FRONTEND_URL}/oauth/callback?error=invalid_state")

    async with httpx.AsyncClient() as client:
        token_resp = await client.get(
            "https://graph.facebook.com/v25.0/oauth/access_token",
            params={
                "client_id": META_APP_ID,
                "client_secret": META_APP_SECRET,
                "redirect_uri": META_REDIRECT_URI,
                "code": code,
            },
        )
        token_data = token_resp.json()
        if "error" in token_data:
            _state_store.pop(state, None)
            return RedirectResponse(
                f"{FRONTEND_URL}/auth/callback?error={token_data['error'].get('message', 'token_error')}"
            )

        short_lived_token = token_data["access_token"]
        ll_resp = await client.get(
            "https://graph.facebook.com/v25.0/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": META_APP_ID,
                "client_secret": META_APP_SECRET,
                "fb_exchange_token": short_lived_token,
            },
        )
        long_lived_token = ll_resp.json().get("access_token", short_lived_token)

        me_data = (await client.get(
            "https://graph.facebook.com/v25.0/me",
            params={
                "fields": "id,name",
                "access_token": long_lived_token
            },
        )).json()
        fb_user_id = me_data["id"]

        pages_data = (await client.get(
            f"https://graph.facebook.com/v25.0/{fb_user_id}/accounts",
            params={"access_token": long_lived_token},
        )).json()

    # Upsert User
    result = await db.execute(select(User).where(User.fb_user_id == fb_user_id))
    user = result.scalar_one_or_none()
    enc_user_token = encrypt_token(long_lived_token)
    if user is None:
        user = User(fb_user_id=fb_user_id, name=me_data["name"], user_access_token=enc_user_token)
        db.add(user)
    else:
        user.name = me_data["name"]
        user.user_access_token = enc_user_token
    await db.flush()

    # Upsert Pages
    async with httpx.AsyncClient() as client:
        for page_info in pages_data.get("data", []):
            page_id = page_info["id"]
            page_token = page_info["access_token"]
            ig_data = (await client.get(
                f"https://graph.facebook.com/v25.0/{page_id}",
                params={
                    "fields": "instagram_business_account",
                    "access_token": page_token
                },
            )).json()
            ig_account_id = None
            ig_account_name = None
            if "instagram_business_account" in ig_data:
                ig_id = ig_data["instagram_business_account"]["id"]
                ig_info = (await client.get(
                    f"https://graph.facebook.com/v25.0/{ig_id}",
                    params={
                        "fields": "id,name,username",
                        "access_token": page_token
                    },
                )).json()
                ig_account_id = ig_id
                ig_account_name = ig_info.get("username") or ig_info.get("name")

            result = await db.execute(
                select(Page).where(Page.page_id == page_id, Page.user_id == user.id))
            page = result.scalar_one_or_none()
            enc_page_token = encrypt_token(page_token)
            if page is None:
                db.add(
                    Page(
                        user_id=user.id,
                        page_id=page_id,
                        page_name=page_info["name"],
                        page_access_token=enc_page_token,
                        ig_account_id=ig_account_id,
                        ig_account_name=ig_account_name,
                    ))
            else:
                page.page_name = page_info["name"]
                page.page_access_token = enc_page_token
                page.ig_account_id = ig_account_id
                page.ig_account_name = ig_account_name

    await db.commit()

    # Store session payload under the state token
    _store_payload(state, {"user_id": user.id})
    return RedirectResponse(f"{FRONTEND_URL}/oauth/callback?state={state}")


# ── Instagram Business Login ──────────────────────────────────


@router.get("/ig/login")
async def ig_login(request: Request):
    _purge_expired()
    state = _new_state()
    url = ("https://www.instagram.com/oauth/authorize"
           f"?client_id={META_IG_APP_ID}"
           f"&redirect_uri={META_IG_REDIRECT_URI}"
           f"&scope={IG_SCOPES}"
           f"&state={state}"
           "&response_type=code")
    return RedirectResponse(url)


@router.get("/ig/callback")
async def ig_callback(
        request: Request,
        code: str = "",
        state: str = "",
        error: str = "",
        db: AsyncSession = Depends(get_db),
):
    if error:
        return RedirectResponse(f"{FRONTEND_URL}/oauth/ig/callback?error={error}")
    if not state or state not in _state_store:
        return RedirectResponse(f"{FRONTEND_URL}/oauth/ig/callback?error=invalid_state")

    clean_code = code.split("#")[0]

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://api.instagram.com/oauth/access_token",
            data={
                "client_id": META_IG_APP_ID,
                "client_secret": META_IG_APP_SECRET,
                "grant_type": "authorization_code",
                "redirect_uri": META_IG_REDIRECT_URI,
                "code": clean_code,
            },
        )
        token_data = token_resp.json()
        if "error_type" in token_data or "error" in token_data:
            _state_store.pop(state, None)
            msg = token_data.get("error_message", "token_error")
            return RedirectResponse(f"{FRONTEND_URL}/auth/ig/callback?error={msg}")

        short_lived_token = token_data["access_token"]
        ig_user_id = str(token_data["user_id"])

        ll_resp = await client.get(
            "https://graph.instagram.com/access_token",
            params={
                "grant_type": "ig_exchange_token",
                "client_secret": META_IG_APP_SECRET,
                "access_token": short_lived_token,
            },
        )
        ll_data = ll_resp.json()
        long_lived_token = ll_data.get("access_token", short_lived_token)
        expires_in = ll_data.get("expires_in", 5184000)
        token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        me_data = (await client.get(
            f"https://graph.instagram.com/v25.0/{ig_user_id}",
            params={
                "fields": "id,username,name",
                "access_token": long_lived_token
            },
        )).json()

    username = me_data.get("username", ig_user_id)
    name = me_data.get("name")

    result = await db.execute(select(IgAccount).where(IgAccount.ig_user_id == ig_user_id))
    ig_account = result.scalar_one_or_none()
    enc_ig_token = encrypt_token(long_lived_token)
    if ig_account is None:
        ig_account = IgAccount(
            ig_user_id=ig_user_id,
            username=username,
            name=name,
            access_token=enc_ig_token,
            token_expires_at=token_expires_at,
        )
        db.add(ig_account)
    else:
        ig_account.username = username
        ig_account.name = name
        ig_account.access_token = enc_ig_token
        ig_account.token_expires_at = token_expires_at

    await db.commit()
    await db.refresh(ig_account)

    # Store session payload under the state token
    _store_payload(state, {"ig_account_id": ig_account.id})
    return RedirectResponse(f"{FRONTEND_URL}/oauth/ig/callback?state={state}")


# ── State verification ────────────────────────────────────────
# Frontend calls this cross-origin (VITE_API_BASE_URL → localhost:8001 or api. subdomain).
# CORS + withCredentials ensure the session cookie is correctly set on the response.


@router.post("/verify")
async def verify_state(request: Request, state: str):
    """Exchange a one-time state token for a session cookie."""
    payload = _consume_state(state)
    if payload is None:
        raise HTTPException(status_code=400, detail="Invalid or expired state token")
    for key, value in payload.items():
        request.session[key] = value
    return {"ok": True}


# ── /me & logout ──────────────────────────────────────────────


@router.get("/me")
async def me(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = request.session.get("user_id")
    ig_account_id = request.session.get("ig_account_id")

    if not user_id and not ig_account_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    response: dict = {}

    if user_id:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            pages_result = await db.execute(select(Page).where(Page.user_id == user.id))
            pages = pages_result.scalars().all()
            response["fb_user"] = {
                "id":
                user.id,
                "name":
                user.name,
                "pages": [{
                    "id": p.id,
                    "page_id": p.page_id,
                    "page_name": p.page_name,
                    "ig_account_id": p.ig_account_id,
                    "ig_account_name": p.ig_account_name,
                } for p in pages],
            }

    if ig_account_id:
        result = await db.execute(select(IgAccount).where(IgAccount.id == ig_account_id))
        ig_acc = result.scalar_one_or_none()
        if ig_acc:
            response["ig_accounts"] = [{
                "id": ig_acc.id,
                "ig_user_id": ig_acc.ig_user_id,
                "username": ig_acc.username,
                "name": ig_acc.name,
                "token_expires_at": ig_acc.token_expires_at,
            }]

    if not response:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return response


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return {"message": "Logged out"}

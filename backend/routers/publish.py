import io
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from PIL import Image
from pydantic import BaseModel, ValidationError, field_validator, model_validator
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import IgAccount, Page, ScheduledPost
from services.scheduler import scheduler_service

router = APIRouter()

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
MAX_SIZE_MB = 20
UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads"

def _parse_client_datetime_to_utc(dt_str: str) -> datetime:
    """
    規則：
    - 若字串無時區資訊（naive），視為 UTC。
    - 若字串有時區資訊（offset / Z），轉成 UTC。
    回傳 tz-aware UTC datetime。
    """
    s = (dt_str or "").strip()
    if not s:
        raise ValueError("Empty datetime")
    # Allow 'Z' suffix
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _utc_aware_to_db_naive(dt_utc: datetime) -> datetime:
    """DB 一律存 naive datetime，語意固定為 UTC。"""
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    return dt_utc.astimezone(timezone.utc).replace(tzinfo=None)


def _db_naive_utc_to_iso_z(dt_utc_naive: datetime | None) -> str | None:
    """將 DB naive UTC datetime 轉成帶 Z 的 ISO 字串。"""
    if dt_utc_naive is None:
        return None
    dt_aware = (dt_utc_naive.replace(tzinfo=timezone.utc)
                if dt_utc_naive.tzinfo is None else dt_utc_naive.astimezone(timezone.utc))
    return dt_aware.isoformat().replace("+00:00", "Z")


class PublishIntent(BaseModel):
    """建立排程時的欄位驗證（不含圖檔；圖檔於路由內驗證並寫入 uploads）。"""

    page_db_id: int | None = None
    ig_account_db_id: int | None = None
    caption: str
    platforms: list[Literal["facebook", "instagram"]]
    scheduled_at: datetime

    @model_validator(mode="after")
    def check_account(self) -> "PublishIntent":
        if self.page_db_id is None and self.ig_account_db_id is None:
            raise ValueError("Either page_db_id or ig_account_db_id must be provided")
        if self.page_db_id is not None and self.ig_account_db_id is not None:
            raise ValueError("Only one of page_db_id or ig_account_db_id can be provided")
        return self

    @field_validator("platforms")
    @classmethod
    def platforms_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("At least one platform must be selected")
        return v

    @field_validator("scheduled_at")
    @classmethod
    def scheduled_at_must_be_future(cls, v: datetime) -> datetime:
        now = datetime.now(timezone.utc)
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if v <= now:
            raise ValueError("scheduled_at must be in the future")
        return v


def _save_image_file(image_bytes: bytes, original_filename: str | None) -> str:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(original_filename or "image.jpg").suffix.lower() or ".jpg"
    name = f"{uuid.uuid4().hex}{ext}"
    (UPLOAD_DIR / name).write_bytes(image_bytes)
    return name


@router.post("")
async def create_post(
        request: Request,
        db: AsyncSession = Depends(get_db),
        file: UploadFile = File(...),
        caption: str = Form(...),
        platforms: str = Form(...),
        scheduled_at: str = Form(...),
        page_db_id: str | None = Form(None),
        ig_account_db_id: str | None = Form(None),
):
    user_id = request.session.get("user_id")
    ig_account_id_session = request.session.get("ig_account_id")

    if not user_id and not ig_account_id_session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported image type")

    image_bytes = await file.read()
    if len(image_bytes) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large (max {MAX_SIZE_MB}MB)")

    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.verify()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file")

    try:
        sched_utc = _parse_client_datetime_to_utc(scheduled_at)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid scheduled_at")

    try:
        platforms_list = json.loads(platforms)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid platforms JSON")

    pid = page_db_id.strip() if page_db_id else ""
    iid = ig_account_db_id.strip() if ig_account_db_id else ""

    try:
        intent = PublishIntent(
            page_db_id=int(pid) if pid else None,
            ig_account_db_id=int(iid) if iid else None,
            caption=caption,
            platforms=platforms_list,
            scheduled_at=sched_utc,
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())

    image_filename = _save_image_file(image_bytes, file.filename)

    post_kwargs = dict(
        image_path=image_filename,
        caption=intent.caption,
        platforms=intent.platforms,
        scheduled_at=_utc_aware_to_db_naive(intent.scheduled_at),
        status="pending",
    )

    if intent.page_db_id is not None:
        if not user_id:
            raise HTTPException(status_code=401, detail="Facebook login required")
        result = await db.execute(
            select(Page).where(Page.id == intent.page_db_id, Page.user_id == user_id))
        page = result.scalar_one_or_none()
        if not page:
            (UPLOAD_DIR / image_filename).unlink(missing_ok=True)
            raise HTTPException(status_code=404, detail="Page not found")
        if "instagram" in intent.platforms and not page.ig_account_id:
            (UPLOAD_DIR / image_filename).unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="This page has no linked Instagram account")
        post_kwargs["page_id"] = page.id

    else:
        if not ig_account_id_session:
            (UPLOAD_DIR / image_filename).unlink(missing_ok=True)
            raise HTTPException(status_code=401, detail="Instagram login required")
        if intent.ig_account_db_id != ig_account_id_session:
            (UPLOAD_DIR / image_filename).unlink(missing_ok=True)
            raise HTTPException(status_code=403, detail="Access denied")
        result = await db.execute(select(IgAccount).where(IgAccount.id == intent.ig_account_db_id))
        ig_acc = result.scalar_one_or_none()
        if not ig_acc:
            (UPLOAD_DIR / image_filename).unlink(missing_ok=True)
            raise HTTPException(status_code=404, detail="Instagram account not found")
        if "facebook" in intent.platforms:
            (UPLOAD_DIR / image_filename).unlink(missing_ok=True)
            raise HTTPException(status_code=400,
                                detail="Instagram-only login cannot publish to Facebook")
        post_kwargs["ig_account_id"] = ig_acc.id

    post = ScheduledPost(**post_kwargs)
    db.add(post)
    await db.commit()
    await db.refresh(post)

    scheduler_service.schedule_post(post.id, intent.scheduled_at)

    return {
        "id": post.id,
        "status": post.status,
        "scheduled_at": _db_naive_utc_to_iso_z(post.scheduled_at),
        "platforms": post.platforms,
    }


@router.get("")
async def list_posts(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = request.session.get("user_id")
    ig_account_id_session = request.session.get("ig_account_id")

    if not user_id and not ig_account_id_session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conditions = []

    if user_id:
        pages_result = await db.execute(select(Page).where(Page.user_id == user_id))
        page_ids = [p.id for p in pages_result.scalars().all()]
        if page_ids:
            conditions.append(ScheduledPost.page_id.in_(page_ids))

    if ig_account_id_session:
        conditions.append(ScheduledPost.ig_account_id == ig_account_id_session)

    if not conditions:
        return []

    posts_result = await db.execute(
        select(ScheduledPost).where(or_(*conditions)).order_by(ScheduledPost.scheduled_at.desc()))
    posts = posts_result.scalars().all()

    return [{
        "id": p.id,
        "page_id": p.page_id,
        "ig_account_id": p.ig_account_id,
        "image_path": p.image_path,
        "caption": p.caption,
        "platforms": p.platforms,
        "scheduled_at": _db_naive_utc_to_iso_z(p.scheduled_at),
        "status": p.status,
        "error_message": p.error_message,
        "created_at": _db_naive_utc_to_iso_z(p.created_at),
    } for p in posts]


@router.delete("/{post_id}")
async def cancel_post(post_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user_id = request.session.get("user_id")
    ig_account_id_session = request.session.get("ig_account_id")

    if not user_id and not ig_account_id_session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conditions = [ScheduledPost.id == post_id]
    sub_conditions = []

    if user_id:
        pages_result = await db.execute(select(Page).where(Page.user_id == user_id))
        page_ids = [p.id for p in pages_result.scalars().all()]
        if page_ids:
            sub_conditions.append(ScheduledPost.page_id.in_(page_ids))

    if ig_account_id_session:
        sub_conditions.append(ScheduledPost.ig_account_id == ig_account_id_session)

    if not sub_conditions:
        raise HTTPException(status_code=404, detail="Post not found")

    conditions.append(or_(*sub_conditions))
    result = await db.execute(select(ScheduledPost).where(*conditions))
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending posts can be cancelled")

    scheduler_service.cancel_post(post_id)
    post.status = "cancelled"
    await db.commit()
    return {"message": "Post cancelled"}

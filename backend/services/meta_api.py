import asyncio
import logging
from pathlib import Path

import httpx

from config import SERVER_BASE_URL
from services.image_upload_prep import ImagePreparationError, prepare_image_for_upload

GRAPH_BASE = "https://graph.facebook.com/v25.0"
IG_GRAPH_BASE = "https://graph.instagram.com/v25.0"

UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads"

logger = logging.getLogger(__name__)

# Instagram Graph「以 URL 建立媒體容器」常見限制（由呼叫端傳入 prepare_image_for_upload）
_INSTAGRAM_IMAGE_MAX_BYTES = 8 * 1024 * 1024
_INSTAGRAM_MIN_LONG_EDGE_PX = 320

# Meta 偶發無法從 image_url 擷取圖片（CDN MISS、自家 fetch 逾時等），短暫重試常可成功
_IG_MEDIA_CREATE_MAX_ATTEMPTS = 3
_IG_MEDIA_CREATE_RETRY_DELAY_SEC = 12


class MetaAPIError(Exception):
    pass


def _ig_media_create_error_should_retry(err: dict) -> bool:
    """依 Graph `error.code` + `error.error_subcode` 決定是否重試建立 media 容器。"""
    try:
        code = int(err.get("code"))
        sub = int(err.get("error_subcode"))
    except (TypeError, ValueError):
        return False
    return code == 9004 and sub == 2207052


async def publish_to_facebook(page_id: str, page_access_token: str, image_path: str,
                              caption: str) -> str:
    """Post a photo to a Facebook Page. Returns the post ID."""
    full_path = UPLOAD_DIR / Path(image_path).name

    async with httpx.AsyncClient(timeout=30.0) as client:
        with open(full_path, "rb") as f:
            resp = await client.post(
                f"{GRAPH_BASE}/{page_id}/photos",
                data={
                    "caption": caption,
                    "access_token": page_access_token
                },
                files={"source": (full_path.name, f, "image/jpeg")},
            )
        data = resp.json()

    if "error" in data:
        raise MetaAPIError(f"Facebook publish error: {data['error']['message']}")
    return data.get("post_id") or data.get("id", "")


async def _ig_container_flow(
    ig_user_id: str,
    access_token: str,
    image_path: str,
    caption: str,
    host_base: str,
) -> str:
    """Shared container-based IG publishing logic."""
    try:
        img_path, is_temp = prepare_image_for_upload(
            UPLOAD_DIR,
            image_path,
            max_bytes=_INSTAGRAM_IMAGE_MAX_BYTES,
            min_long_edge_px=_INSTAGRAM_MIN_LONG_EDGE_PX,
        )
    except ImagePreparationError as e:
        raise MetaAPIError(str(e)) from e
    try:
        return await _ig_container_flow_inner(ig_user_id, access_token, img_path, caption,
                                              host_base)
    finally:
        if is_temp:
            img_path.unlink(missing_ok=True)


async def _ig_container_flow_inner(
    ig_user_id: str,
    access_token: str,
    img_path: Path,
    caption: str,
    host_base: str,
) -> str:
    image_url = f"{SERVER_BASE_URL}/uploads/{img_path.name}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Step 1: Create container
        # image_url must be publicly accessible (not localhost).
        # Set SERVER_BASE_URL to the public domain in .env.
        container_id: str | None = None
        for attempt in range(_IG_MEDIA_CREATE_MAX_ATTEMPTS):
            container_resp = await client.post(
                f"{host_base}/{ig_user_id}/media",
                data={
                    "image_url": image_url,
                    "media_type": "IMAGE",
                    "caption": caption,
                    "access_token": access_token,
                },
            )
            container_data = container_resp.json()
            if "error" not in container_data:
                container_id = container_data["id"]
                break
            err = container_data["error"]
            logger.info("IG media container error response: %s", container_data)
            if _ig_media_create_error_should_retry(err) and attempt + 1 < _IG_MEDIA_CREATE_MAX_ATTEMPTS:
                logger.warning(
                    "IG media container transient error (attempt %d/%d), retry in %ds: %s",
                    attempt + 1,
                    _IG_MEDIA_CREATE_MAX_ATTEMPTS,
                    _IG_MEDIA_CREATE_RETRY_DELAY_SEC,
                    err.get("message", err),
                )
                await asyncio.sleep(_IG_MEDIA_CREATE_RETRY_DELAY_SEC)
                continue
            raise MetaAPIError(f"IG container creation error: {err.get('message', err)}")
        if not container_id:
            raise MetaAPIError("IG container creation failed after retries")

        # Step 2: Poll until FINISHED (max 60s)
        for _ in range(20):
            await asyncio.sleep(3)
            status_resp = await client.get(
                f"{host_base}/{container_id}",
                params={
                    "fields": "status_code",
                    "access_token": access_token
                },
            )
            status_data = status_resp.json()
            status_code = status_data.get("status_code", "IN_PROGRESS")
            if status_code == "FINISHED":
                break
            if status_code in ("ERROR", "EXPIRED"):
                raise MetaAPIError(f"IG container failed with status: {status_code}")
        else:
            raise MetaAPIError("IG container processing timed out")

        # Step 3: Publish
        publish_resp = await client.post(
            f"{host_base}/{ig_user_id}/media_publish",
            data={
                "creation_id": container_id,
                "access_token": access_token
            },
        )
        publish_data = publish_resp.json()

    if "error" in publish_data:
        raise MetaAPIError(f"IG publish error: {publish_data['error']['message']}")
    return publish_data.get("id", "")


async def publish_to_instagram(ig_user_id: str, page_access_token: str, image_path: str,
                               caption: str) -> str:
    """Publish via Facebook Login for Business (Page Access Token → graph.facebook.com)."""
    return await _ig_container_flow(ig_user_id, page_access_token, image_path, caption, GRAPH_BASE)


async def publish_to_instagram_direct(ig_user_id: str, ig_access_token: str, image_path: str,
                                      caption: str) -> str:
    """Publish via Instagram Business Login (Instagram User Token → graph.instagram.com)."""
    return await _ig_container_flow(ig_user_id, ig_access_token, image_path, caption, IG_GRAPH_BASE)

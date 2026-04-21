import io
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from PIL import Image

from services.exif_service import extract_hashtag_suggestions

router = APIRouter()

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
MAX_SIZE_MB = 20
UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads"


@router.post("/analyze")
async def analyze_image(request: Request, file: UploadFile = File(...)):
    """
    讀取圖片並回傳尺寸與 hashtag 建議，不寫入磁碟。
    正式儲存於建立排程時 POST /posts（multipart）一併上傳。
    """
    if not request.session.get("user_id") and not request.session.get("ig_account_id"):
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

    img = Image.open(io.BytesIO(image_bytes))
    width, height = img.size

    hashtag_suggestions = await extract_hashtag_suggestions(image_bytes)

    return {
        "width": width,
        "height": height,
        "size_bytes": len(image_bytes),
        "hashtag_suggestions": hashtag_suggestions,
    }

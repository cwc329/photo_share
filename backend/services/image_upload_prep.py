"""依目標檔案大小與長邊下限，將圖檔整理為適合上傳的 JPEG（必要時產生暫存檔）。"""

import io
from pathlib import Path

from PIL import Image, ImageCms, ImageOps


class ImagePreparationError(Exception):
    """找不到檔案、無法解讀圖檔，或無法壓縮至指定限制時拋出。"""


def _to_rgb_flatten(img: Image.Image) -> Image.Image:
    """無 ICC 或 ICC 失敗時：透明合成白底、調色盤／CMYK 轉 RGB。"""
    if img.mode in ("RGBA", "LA"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        layer = img.convert("RGBA")
        background.paste(layer, mask=layer.split()[-1])
        return background
    if img.mode == "P":
        if "transparency" in img.info:
            layer = img.convert("RGBA")
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(layer, mask=layer.split()[-1])
            return background
        return img.convert("RGB", dither=Image.Dither.NONE)
    if img.mode == "CMYK":
        return img.convert("RGB")
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def _build_master_rgb(orig: Path) -> Image.Image:
    """EXIF 轉正、ICC 轉 sRGB（若可）、其餘轉 RGB，作為後續 JPEG 重壓縮的主圖。"""
    img = Image.open(orig)
    img = ImageOps.exif_transpose(img)

    icc_bytes = img.info.get("icc_profile")
    if icc_bytes:
        try:
            src_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_bytes))
            dst_profile = ImageCms.createProfile("sRGB")
            img = ImageCms.profileToProfile(img, src_profile, dst_profile, outputMode="RGB")
        except Exception:
            img = _to_rgb_flatten(img)
    else:
        img = _to_rgb_flatten(img)

    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def _quality_loop_save(work: Image.Image, tmp_path: Path, max_bytes: int) -> bool:
    """JPEG quality 95→50（步距 5）；若任一步檔案小於 max_bytes 則成功。"""
    for quality in range(95, 45, -5):
        work.save(tmp_path, format="JPEG", quality=quality, optimize=True)
        if tmp_path.stat().st_size < max_bytes:
            return True
    return False


def prepare_image_for_upload(
    upload_dir: Path,
    image_path: str,
    *,
    max_bytes: int,
    min_long_edge_px: int,
    temp_stem_suffix: str = "_prep_tmp",
) -> tuple[Path, bool]:
    """若原檔已小於 max_bytes 則沿用原檔；否則產生暫存 JPEG。回傳 (路徑, 是否暫存)。"""
    orig = upload_dir / Path(image_path).name
    if not orig.is_file():
        raise ImagePreparationError(f"Image file not found: {orig}")
    if orig.stat().st_size < max_bytes:
        return orig, False

    master = _build_master_rgb(orig)
    tmp = orig.with_stem(orig.stem + temp_stem_suffix).with_suffix(".jpg")

    work = master.copy()
    if _quality_loop_save(work, tmp, max_bytes):
        return tmp, True

    long_edge = max(master.size)
    while True:
        L = int(long_edge * 0.9)
        if L < min_long_edge_px:
            mb = max_bytes / (1024 * 1024)
            raise ImagePreparationError(f"無法將圖片壓縮至約 {mb:g} MB 以下且仍符合最小長邊 {min_long_edge_px}px。")
        long_edge = L
        work = master.copy()
        work.thumbnail((L, L), Image.LANCZOS)
        if _quality_loop_save(work, tmp, max_bytes):
            return tmp, True

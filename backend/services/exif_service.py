"""
EXIF hashtag suggestion service.

Primary reader : exiftool (system binary, all brands, full MakerNote support)
Fallback reader: piexif  (pure-Python, used when exiftool is not installed)

System dependency
-----------------
macOS  : brew install exiftool
Debian : apt-get install -y libimage-exiftool-perl
Docker : see backend/Dockerfile
"""

import asyncio
import json
import os
import tempfile
from typing import Any

import httpx
import piexif

# ── Camera brand → base hashtags ──────────────────────────────
CAMERA_BRAND_TAGS: dict[str, list[str]] = {
    "canon": ["#Canon", "#CanonPhotography"],
    "nikon": ["#Nikon", "#NikonPhotography"],
    "sony": ["#Sony", "#SonyPhotography", "#SonyAlpha"],
    "fujifilm": ["#Fujifilm", "#FujiPhotography"],
    "olympus": ["#Olympus", "#OlympusPhotography"],
    "panasonic": ["#Panasonic", "#Lumix"],
    "leica": ["#Leica", "#LeicaCamera"],
    "hasselblad": ["#Hasselblad"],
    "ricoh": ["#Ricoh", "#RicohGR"],
    "dji": ["#DJI", "#DronePhotography", "#AerialPhoto"],
    "apple": ["#ShotOniPhone", "#iPhonePhotography"],
    "samsung": ["#SamsungPhotography"],
    "google": ["#TeamPixel", "#GooglePixel"],
}

SOFTWARE_TAGS: dict[str, list[str]] = {
    "lightroom": ["#LightroomEdits", "#AdobeLightroom", "#LRPresets"],
    "photoshop": ["#Photoshop", "#AdobePhotoshop", "#PSEdits"],
    "capture one": ["#CaptureOne", "#C1Edits"],
    "darktable": ["#Darktable"],
    "luminar": ["#Luminar", "#LuminarAI"],
    "snapseed": ["#Snapseed"],
    "vsco": ["#VSCO", "#VSCOcam"],
}

# ── Helper functions ───────────────────────────────────────────

import re as _re

# IG / FB / Threads 的公分母：只允許字母、數字、底線
# 所有其他字元（. - / ( ) ' & ! 等）都必須移除
_TAG_SAFE = _re.compile(r"[^\w]", _re.UNICODE)  # \w = [a-zA-Z0-9_] + unicode letters


def _sanitize_tag_text(s: str) -> str:
    """
    Remove every character that is not a letter, digit, or underscore.
    Safe for Instagram, Facebook, and Threads hashtags.

    Examples
    --------
    'AF-S NIKKOR 24-70mm f/2.8E'  → 'AFSNikkor2470mmf28E'
    "St. John's"                  → 'StJohns'
    'f/2.8'                       → 'f28'
    '(Canon)'                     → 'Canon'
    """
    return _TAG_SAFE.sub("", s)


def _model_slug(s: str) -> str:
    """Full model/lens name → hashtag-safe slug (no spaces, no special chars)."""
    return _sanitize_tag_text(s)


# ── Lens spec helpers ──────────────────────────────────────────


def _lens_is_zoom(lens_name: str) -> bool:
    """True if the lens name contains a focal range (e.g. '24-70mm')."""
    return bool(_re.search(r"\d+[-–]\d+\s*mm", lens_name, _re.IGNORECASE))


# 各廠牌鏡頭規格縮寫 → hashtag
# key: 在鏡頭名稱中要比對的 pattern（word-boundary aware）
# value: 要產生的 hashtag
_LENS_SPEC_MAP: list[tuple[str, str]] = [
    # ── Nikon ───────────────────────────────────────────────────
    (r"\bAF-S\b", "#AFS"),  # Silent Wave Motor
    (r"\bAF-P\b", "#AFP"),  # Pulse Motor
    (r"\bAF-I\b", "#AFI"),  # Internal AF Motor
    (r"\bAF-D\b|(?<!\w)AF(?!\w|-[SPI])", "#AF"),  # generic AF（不重複 AFS/AFP/AFI）
    (r"\bVR\b", "#VR"),  # Vibration Reduction (Nikon)
    (r"\bED\b", "#ED"),  # Extra-low Dispersion
    (r"\bIF\b", "#IF"),  # Internal Focus
    (r"\bDC\b", "#DC"),  # Defocus Control
    (r"\bPC-E?\b", "#PCLens"),  # Perspective Control
    (r"\bFL\b", "#FLens"),  # Fluorite
    (r"\bDX\b", "#DX"),  # Crop sensor
    (r"\bNIKKOR Z\b", "#ZMount"),  # Z mount mirrorless
    (r"\bMicro\b", "#MacroLens"),  # Macro / Micro
    (r"\bTC\b", "#Teleconverter"),
    # Nikkor lens grade suffix  ' S' (only at end, preceded by space)
    (r"\bS\b$", "#SLine"),  # Nikon Z S-Line

    # ── Canon ───────────────────────────────────────────────────
    (r"\bL\b", "#LLens"),  # L-series (luxury)
    (r"\bIS\b", "#IS"),  # Image Stabilizer
    (r"\bUSM\b", "#USM"),  # Ultrasonic Motor
    (r"\bSTM\b", "#STM"),  # Stepping Motor
    (r"\bDO\b", "#DOLens"),  # Diffractive Optics
    (r"\bRF\b", "#RFLens"),  # RF mount mirrorless
    (r"\bEF-S\b", "#EFS"),  # EF-S crop
    (r"\bEF-M\b", "#EFM"),  # EF-M mirrorless
    (r"(?<!\w)EF(?!\w|-[SM])", "#EF"),  # EF (not EF-S / EF-M)

    # ── Sony ────────────────────────────────────────────────────
    (r"\bG\s*M\b|\bGM\b|\bG Master\b", "#GMaster"),  # G Master / GM
    (r"(?<!\w)G(?!\s*M\b)(?!\s*Master)(?!\w)", "#GSeries"),  # G series (not G Master / GM)
    (r"\bZA\b", "#ZeissAlpha"),
    (r"\bSSM\b", "#SSM"),  # Super Sonic Motor
    (r"\bSAM\b", "#SAM"),  # Smooth Autofocus Motor
    (r"\bOSS\b", "#OSS"),  # Optical SteadyShot
    (r"\bFE\b", "#FELens"),  # Full-frame E-mount
    (r"(?<!\w)E(?!\w|-mount)", "#EMount"),  # E-mount (not FE)

    # ── Fujifilm ─────────────────────────────────────────────────
    (r"\bWR\b", "#WR"),  # Weather Resistant
    (r"\bOIS\b", "#OIS"),  # Optical Image Stabilizer
    (r"\bLM\b", "#LM"),  # Linear Motor
    (r"\bRed Badge\b", "#RedBadge"),  # Pro grade

    # ── Sigma ─────────────────────────────────────────────────────
    (r"\bArt\b", "#SigmaArt"),
    (r"\bSports\b", "#SigmaSports"),
    (r"\bContemporary\b", "#SigmaContemporary"),
    (r"\bDG\b", "#DGLens"),  # Full-frame
    (r"\bDC\b", "#DCLens"),  # Crop
    (r"\bHSM\b", "#HSM"),  # Hyper Sonic Motor
    (r"\bOS\b", "#OS"),  # Optical Stabilizer (Sigma)

    # ── Tamron ─────────────────────────────────────────────────────
    (r"\bVC\b", "#VC"),  # Vibration Compensation
    (r"\bUSD\b", "#USD"),  # Ultrasonic Silent Drive
    (r"\bSP\b", "#SP"),  # Super Performance

    # ── Zeiss ─────────────────────────────────────────────────────
    (r"\bOtus\b", "#ZeissOtus"),
    (r"\bMilvus\b", "#ZeissMilvus"),
    (r"\bLoxia\b", "#ZeissLoxia"),
    (r"\bBatis\b", "#ZeissBatis"),
]


def _lens_spec_tags(lens_name: str) -> list[str]:
    """
    Parse the full lens name and return a list of spec hashtags.

    Examples
    --------
    'AF-S NIKKOR 24-70mm f/2.8E ED VR' → ['#ZoomLens', '#AFS', '#ED', '#VR']
    'AF-S NIKKOR 50mm f/1.4G'          → ['#PrimeLens', '#AFS']
    'EF 50mm f/1.8 STM'                → ['#PrimeLens', '#EF', '#STM']
    """
    tags: list[str] = []

    # Prime / Zoom
    tags.append("#ZoomLens" if _lens_is_zoom(lens_name) else "#PrimeLens")

    seen: set[str] = set()
    for pattern, hashtag in _LENS_SPEC_MAP:
        if hashtag in seen:
            continue
        if _re.search(pattern, lens_name, _re.IGNORECASE):
            tags.append(hashtag)
            seen.add(hashtag)

    return tags


def _aperture_tag(fn: float) -> str:
    """2.8 → '#F2_8'、1.8 → '#F1_8'、11.0 → '#F11'（小數用 _ 與整數 F32 區隔）"""
    if fn == round(fn):
        return f"#F{int(fn)}"
    return "#F" + str(round(fn, 1)).replace(".", "_")


def _shutter_tag(exp: float) -> str:
    """0.001 → '#1_1000s'、0.5 → '#1_2s'、25.0 → '#25s'"""
    if exp >= 1:
        return f"#{round(exp)}s"
    denom = round(1 / exp)
    return f"#1_{denom}s"


def _camera_tags(make: str, model: str) -> list[str]:
    make_lower = make.lower()
    for brand, base_tags in CAMERA_BRAND_TAGS.items():
        if brand in make_lower:
            tags = list(base_tags)
            if model:
                tags.append(f"#{_model_slug(model)}")
            return tags
    return []


def _focal_length_tags(fl_mm: float) -> list[str]:
    fl_int = round(fl_mm)
    return [f"#{fl_int}mm", f"#{fl_int}mmLens"]


def _focal_35mm_tags(fl35: int) -> list[str]:
    tags = [f"#{fl35}mm35mm"]
    if fl35 <= 24:
        tags += ["#UltraWideAngle", "#WideAngle", "#WideAnglePhotography"]
    elif fl35 <= 35:
        tags += ["#WideAngle", "#WideAnglePhotography"]
    elif fl35 <= 55:
        tags += ["#StandardLens", "#NormalLens"]
    elif fl35 <= 135:
        tags += ["#ShortTelephoto", "#PortraitLens"]
    else:
        tags += ["#Telephoto", "#TelephotoLens"]
    return tags


def _iso_tags(iso: int) -> list[str]:
    tags = [f"#ISO{iso}"]
    if iso <= 200:
        tags += ["#LowISO", "#CleanImage"]
    elif iso <= 800:
        tags += ["#MidISO"]
    else:
        tags += ["#HighISO", "#NightPhotography", "#GrainEffect"]
    return tags


def _aperture_tags(fn: float) -> list[str]:
    ap = _aperture_tag(fn)
    tags = [ap, f"#Aperture{ap[1:]}"]
    if fn <= 1.8:
        tags += ["#Bokeh", "#ShallowDOF", "#PortraitPhotography"]
    elif fn <= 2.8:
        tags += ["#Bokeh", "#DepthOfField"]
    elif fn <= 5.6:
        tags += ["#StreetPhotography", "#Documentary"]
    else:
        tags += ["#LandscapePhotography", "#DeepFocus"]
    return tags


def _shutter_tags(exp: float) -> list[str]:
    tags = [_shutter_tag(exp)]
    if exp >= 1:
        tags += ["#LongExposure", "#SlowShutter", "#NightPhotography"]
    elif exp >= 0.1:
        tags += ["#SlowShutter"]
    elif exp <= 1 / 500:
        tags += ["#FreezeMotion", "#ActionPhotography", "#FastShutter"]
    return tags


def _software_tags(sw: str) -> list[str]:
    sw_lower = sw.lower()
    for key, tags in SOFTWARE_TAGS.items():
        if key in sw_lower:
            return tags
    return []


# ── exiftool primary reader ────────────────────────────────────


def _parse_exiftool_float(value: Any) -> float | None:
    """
    Parse a value that exiftool may return as float, int, or string.

    Without -n, exiftool returns:
      ExposureTime        "1/1000"  or  "0.001"
      FocalLength         "50.0 mm"
      FocalLength35efl    "50 mm"
      FNumber / ISO       already numeric
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    # "1/1000" fraction
    if "/" in s:
        try:
            num, den = s.split("/", 1)
            return float(num) / float(den)
        except (ValueError, ZeroDivisionError):
            return None
    # "50.0 mm" → "50.0"
    s = s.split()[0] if " " in s else s
    try:
        return float(s)
    except ValueError:
        return None


async def _run_exiftool(image_bytes: bytes) -> dict | None:
    """
    Write image to a temp file, run exiftool (without -n so lens names are
    resolved from MakerNote), return parsed JSON dict.

    GPS tags are requested with '#' suffix to force decimal-degree output
    even without the global -n flag.
    """
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(image_bytes)
            tmp_path = f.name

        proc = await asyncio.create_subprocess_exec(
            "exiftool",
            "-json",
            "-quiet",
            tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10.0)
        result = json.loads(stdout.decode("utf-8", errors="ignore"))
        return result[0] if result else None
    except FileNotFoundError:
        return None
    except Exception:
        return None
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _suggestions_from_exiftool(data: dict) -> dict[str, list[str]]:
    """Map exiftool JSON fields to hashtag suggestion categories."""
    s: dict[str, list[str]] = {
        k: []
        for k in (
            "camera",
            "lens",
            "focal_length",
            "focal_length_35mm",
            "iso",
            "aperture",
            "shutter",
            "software",
            "location",
        )
    }

    # Camera
    make = str(data.get("Make") or "").strip()
    model = str(data.get("Model") or "").strip()
    if make:
        s["camera"] = _camera_tags(make, model)

    # Lens — without -n, exiftool resolves LensID from MakerNote to full name.
    # "LensModel" = standard EXIF tag (Sony/Canon/Fuji/modern Nikon)
    # "LensID"    = exiftool composite resolved from MakerNote (Nikon F/Z)
    # "Lens" intentionally excluded: returns spec-only string like "50 50 1.8 1.8"
    for key in ("LensModel", "LensID"):
        lens = str(data.get(key) or "").strip()
        # Reject: empty, pure-number IDs, hex byte strings, spec-only values
        if lens and not lens.isdigit() and _re.search(r"[A-Za-z]{2,}", lens):
            s["lens"] = [f"#{_model_slug(lens)}"] + _lens_spec_tags(lens)
            break

    # Focal length  ("50.0 mm" or 50.0)
    fl = _parse_exiftool_float(data.get("FocalLength"))
    if fl:
        s["focal_length"] = _focal_length_tags(fl)

    # 35mm equivalent  ("50 mm" or 50)
    fl35 = _parse_exiftool_float(
        data.get("FocalLengthIn35mmFormat") or data.get("FocalLength35efl"))
    if fl35:
        s["focal_length_35mm"] = _focal_35mm_tags(int(fl35))

    # ISO  (numeric without -n)
    iso = _parse_exiftool_float(data.get("ISO"))
    if iso:
        s["iso"] = _iso_tags(int(iso))

    # Aperture  (numeric without -n)
    fn = _parse_exiftool_float(data.get("FNumber") or data.get("Aperture"))
    if fn:
        s["aperture"] = _aperture_tags(fn)

    # Shutter speed  ("1/1000" or 0.001)
    exp = _parse_exiftool_float(data.get("ExposureTime") or data.get("ShutterSpeed"))
    if exp and exp > 0:
        s["shutter"] = _shutter_tags(exp)

    # Software
    sw = str(data.get("Software") or "").strip()
    if sw:
        s["software"] = _software_tags(sw)

    return s


# ── piexif fallback reader ─────────────────────────────────────


def _get_rational(value: Any) -> float | None:
    try:
        if isinstance(value, tuple) and len(value) == 2:
            return value[0] / value[1] if value[1] != 0 else None
        return float(value)
    except Exception:
        return None


def _decode(raw: Any) -> str:
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="ignore").strip()
    return str(raw).strip()


def _gps_dms_to_decimal(dms: tuple, ref: str) -> float:
    degrees = _get_rational(dms[0]) or 0
    minutes = _get_rational(dms[1]) or 0
    seconds = _get_rational(dms[2]) or 0
    decimal = degrees + minutes / 60 + seconds / 3600
    if ref in ("S", "W"):
        decimal = -decimal
    return decimal


def _suggestions_from_piexif(image_bytes: bytes) -> dict[str, list[str]]:
    """Fallback EXIF reader using piexif (pure Python, no MakerNote support)."""
    s: dict[str, list[str]] = {
        k: []
        for k in (
            "camera",
            "lens",
            "focal_length",
            "focal_length_35mm",
            "iso",
            "aperture",
            "shutter",
            "software",
            "location",
        )
    }

    try:
        exif_data = piexif.load(image_bytes)
    except Exception:
        return s

    ifd0 = exif_data.get("0th", {})
    exif_ifd = exif_data.get("Exif", {})

    # Camera
    make_raw = ifd0.get(piexif.ImageIFD.Make)
    model_raw = ifd0.get(piexif.ImageIFD.Model)
    if make_raw:
        make = _decode(make_raw)
        model = _decode(model_raw) if model_raw else ""
        s["camera"] = _camera_tags(make, model)

    # Lens
    lens_raw = exif_ifd.get(piexif.ExifIFD.LensModel)
    if lens_raw:
        lens = _decode(lens_raw)
        if lens:
            s["lens"] = [f"#{_model_slug(lens)}"] + _lens_spec_tags(lens)

    # Focal length
    fl_raw = exif_ifd.get(piexif.ExifIFD.FocalLength)
    if fl_raw:
        fl = _get_rational(fl_raw)
        if fl:
            s["focal_length"] = _focal_length_tags(fl)

    # 35mm equivalent
    fl35_raw = exif_ifd.get(piexif.ExifIFD.FocalLengthIn35mmFilm)
    if fl35_raw:
        fl35 = fl35_raw if isinstance(fl35_raw, int) else int(_get_rational(fl35_raw) or 0)
        if fl35 > 0:
            s["focal_length_35mm"] = _focal_35mm_tags(fl35)

    # ISO (piexif returns SHORT array as tuple)
    iso_raw = exif_ifd.get(piexif.ExifIFD.ISOSpeedRatings)
    if iso_raw is not None:
        if isinstance(iso_raw, int):
            iso = iso_raw
        elif isinstance(iso_raw, (tuple, list)) and len(iso_raw) > 0:
            iso = int(iso_raw[0])
        else:
            iso = 0
        if iso > 0:
            s["iso"] = _iso_tags(iso)

    # Aperture
    fn_raw = exif_ifd.get(piexif.ExifIFD.FNumber)
    if fn_raw:
        fn = _get_rational(fn_raw)
        if fn is not None:
            s["aperture"] = _aperture_tags(fn)

    # Shutter
    exp_raw = exif_ifd.get(piexif.ExifIFD.ExposureTime)
    if exp_raw:
        exp = _get_rational(exp_raw)
        if exp is not None and exp > 0:
            s["shutter"] = _shutter_tags(exp)

    # Software
    sw_raw = ifd0.get(piexif.ImageIFD.Software)
    if sw_raw:
        s["software"] = _software_tags(_decode(sw_raw))

    return s


# ── GPS reverse geocoding ──────────────────────────────────────


async def _reverse_geocode(lat: float, lon: float) -> list[str]:
    tags: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "lat": lat,
                    "lon": lon,
                    "format": "json"
                },
                headers={"User-Agent": "PhotoShare/1.0"},
            )
            data = resp.json()
            address = data.get("address", {})
            for key in ("city", "town", "village", "county", "state", "country"):
                val = address.get(key)
                if val:
                    slug = _sanitize_tag_text(val)
                    if slug:
                        tags.append(f"#{slug}")
    except Exception:
        pass
    return tags


async def _get_gps_location(image_bytes: bytes, exiftool_data: dict | None) -> list[str]:
    """Extract GPS from exiftool data (preferred) or piexif fallback."""
    lat: float | None = None
    lon: float | None = None

    if exiftool_data:
        # Without -n, exiftool returns GPS as DMS string ("25 deg 2' 50.04\" N")
        # which _parse_exiftool_float cannot handle. Only attempt if the value
        # is already numeric (unlikely without -n, but safe to try).
        raw_lat = _parse_exiftool_float(exiftool_data.get("GPSLatitude"))
        raw_lon = _parse_exiftool_float(exiftool_data.get("GPSLongitude"))
        if raw_lat is not None and raw_lon is not None:
            lat_ref = str(exiftool_data.get("GPSLatitudeRef") or "N")
            lon_ref = str(exiftool_data.get("GPSLongitudeRef") or "E")
            lat = raw_lat * (-1 if lat_ref == "S" else 1)
            lon = raw_lon * (-1 if lon_ref == "W" else 1)

    if lat is None:
        try:
            exif_data = piexif.load(image_bytes)
            gps_ifd = exif_data.get("GPS", {})
            lat_dms = gps_ifd.get(piexif.GPSIFD.GPSLatitude)
            lat_ref_raw = gps_ifd.get(piexif.GPSIFD.GPSLatitudeRef)
            lon_dms = gps_ifd.get(piexif.GPSIFD.GPSLongitude)
            lon_ref_raw = gps_ifd.get(piexif.GPSIFD.GPSLongitudeRef)
            if lat_dms and lon_dms and lat_ref_raw and lon_ref_raw:
                lat_ref = _decode(lat_ref_raw)
                lon_ref = _decode(lon_ref_raw)
                lat = _gps_dms_to_decimal(lat_dms, lat_ref)
                lon = _gps_dms_to_decimal(lon_dms, lon_ref)
        except Exception:
            pass

    if lat is not None and lon is not None:
        return await _reverse_geocode(lat, lon)
    return []


# ── Public API ─────────────────────────────────────────────────


async def extract_hashtag_suggestions(image_bytes: bytes) -> dict[str, list[str]]:
    """
    Extract EXIF metadata and return hashtag suggestions.

    Uses exiftool when available (full MakerNote, all brands).
    Falls back to piexif (pure Python) when exiftool is not installed.
    GPS location is always resolved via Nominatim reverse geocoding.
    """
    exiftool_data = await _run_exiftool(image_bytes)

    if exiftool_data:
        suggestions = _suggestions_from_exiftool(exiftool_data)
    else:
        suggestions = _suggestions_from_piexif(image_bytes)

    suggestions["location"] = await _get_gps_location(image_bytes, exiftool_data)
    return suggestions

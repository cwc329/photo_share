import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from config import COOKIE_DOMAIN, COOKIE_SECURE, FRONTEND_URL, SECRET_KEY
from database import init_db
from routers import auth, media, publish
from services.scheduler import scheduler_service

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")

# Cookie settings（值來自 config / .env）:
#   Dev  : COOKIE_DOMAIN=""（cookie 限定 localhost）, COOKIE_SECURE=false
#   Prod : COOKIE_DOMAIN=".cwc329.com"（讓 photo-share. 與 api. 共享）, COOKIE_SECURE=true


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await scheduler_service.start()
    yield
    scheduler_service.shutdown()


logger = logging.getLogger(__name__)


class UploadsLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/uploads/") or request.url.path.endswith("/robots.txt"):
            ua = request.headers.get("user-agent", "<none>")
            logger.info("UPLOADS request: %s %s | UA: %s | IP: %s",
                        request.method, request.url.path, ua,
                        request.headers.get("cf-connecting-ip") or request.client.host)
        return await call_next(request)


app = FastAPI(title="Photo Share API", lifespan=lifespan)

app.add_middleware(UploadsLoggingMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    same_site="lax",
    https_only=COOKIE_SECURE,
    domain=COOKIE_DOMAIN,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(media.router, prefix="/media", tags=["media"])
app.include_router(publish.router, prefix="/posts", tags=["posts"])


_ROBOTS_TXT = (
    "User-agent: facebookexternalhit\n"
    "Allow: /\n\n"
    "User-agent: facebookexternalhit/1.1\n"
    "Allow: /\n\n"
    "User-agent: meta-externalagent\n"
    "Allow: /\n\n"
    "User-agent: Facebot\n"
    "Allow: /\n\n"
    "User-agent: *\n"
    "Allow: /\n"
).encode()


@app.get("/robots.txt")
async def robots_txt(request: Request):
    total = len(_ROBOTS_TXT)
    range_header = request.headers.get("range")
    if range_header:
        range_val = range_header.removeprefix("bytes=")
        start_str, _, end_str = range_val.partition("-")
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else total - 1
        end = min(end, total - 1)
        return Response(
            content=_ROBOTS_TXT[start:end + 1],
            status_code=206,
            headers={
                "Content-Type": "text/plain; charset=utf-8",
                "Content-Range": f"bytes {start}-{end}/{total}",
                "Accept-Ranges": "bytes",
            },
        )
    return Response(
        content=_ROBOTS_TXT,
        status_code=200,
        headers={
            "Content-Type": "text/plain; charset=utf-8",
            "Accept-Ranges": "bytes",
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok"}

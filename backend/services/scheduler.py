import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from sqlalchemy import select

from database import AsyncSessionLocal
from models import IgAccount, Page, ScheduledPost
from services.meta_api import (MetaAPIError, publish_to_facebook, publish_to_instagram,
                               publish_to_instagram_direct)
from services.token_crypto import decrypt_token

logger = logging.getLogger(__name__)


async def _execute_post(post_id: int) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ScheduledPost).where(ScheduledPost.id == post_id))
        post = result.scalar_one_or_none()
        if not post or post.status != "pending":
            return

        errors: list[str] = []

        # ── Path A: posted via Facebook Login (has page_id) ──────────
        if post.page_id is not None:
            page_result = await db.execute(select(Page).where(Page.id == post.page_id))
            page = page_result.scalar_one_or_none()
            if not page:
                post.status = "failed"
                post.error_message = "Page not found"
                await db.commit()
                return

            for platform in post.platforms:
                try:
                    page_token = decrypt_token(page.page_access_token)
                    if platform == "facebook":
                        await publish_to_facebook(
                            page.page_id,
                            page_token,
                            post.image_path,
                            post.caption,
                        )
                    elif platform == "instagram":
                        if not page.ig_account_id:
                            errors.append("instagram: no linked IG account on this Page")
                            continue
                        await publish_to_instagram(
                            page.ig_account_id,
                            page_token,
                            post.image_path,
                            post.caption,
                        )
                except MetaAPIError as e:
                    errors.append(f"{platform}: {e}")
                except Exception as e:
                    errors.append(f"{platform}: unexpected error - {e}")
                    logger.exception("Error publishing post %d to %s", post_id, platform)

        # ── Path B: posted via Instagram Business Login (has ig_account_id) ─
        elif post.ig_account_id is not None:
            ig_result = await db.execute(
                select(IgAccount).where(IgAccount.id == post.ig_account_id))
            ig_account = ig_result.scalar_one_or_none()
            if not ig_account:
                post.status = "failed"
                post.error_message = "Instagram account not found"
                await db.commit()
                return

            try:
                await publish_to_instagram_direct(
                    ig_account.ig_user_id,
                    decrypt_token(ig_account.access_token),
                    post.image_path,
                    post.caption,
                )
            except MetaAPIError as e:
                errors.append(f"instagram: {e}")
            except Exception as e:
                errors.append(f"instagram: unexpected error - {e}")
                logger.exception("Error publishing post %d via IG direct", post_id)

        else:
            post.status = "failed"
            post.error_message = "No account linked to post"
            await db.commit()
            return

        post.status = "failed" if errors else "published"
        post.error_message = "; ".join(errors) if errors else None
        await db.commit()
        logger.info("Post %d finished with status: %s", post_id, post.status)


class SchedulerService:

    def __init__(self):
        self._scheduler = AsyncIOScheduler(timezone="UTC")

    async def start(self):
        self._scheduler.start()
        await self._restore_pending_jobs()
        logger.info("Scheduler started")

    def shutdown(self):
        self._scheduler.shutdown(wait=False)

    async def _restore_pending_jobs(self):
        now = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ScheduledPost).where(ScheduledPost.status == "pending"))
            posts = result.scalars().all()

        for post in posts:
            run_at = post.scheduled_at
            if run_at.tzinfo is None:
                run_at = run_at.replace(tzinfo=timezone.utc)
            if run_at <= now:
                run_at = now
            self._add_job(post.id, run_at)
        logger.info("Restored %d pending jobs", len(posts))

    def _add_job(self, post_id: int, run_at: datetime):
        job_id = f"post_{post_id}"
        if self._scheduler.get_job(job_id):
            self._scheduler.reschedule_job(job_id, trigger=DateTrigger(run_date=run_at))
        else:
            self._scheduler.add_job(
                _execute_post,
                trigger=DateTrigger(run_date=run_at),
                args=[post_id],
                id=job_id,
                replace_existing=True,
            )

    def schedule_post(self, post_id: int, run_at: datetime):
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=timezone.utc)
        self._add_job(post_id, run_at)

    def cancel_post(self, post_id: int):
        job_id = f"post_{post_id}"
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)


scheduler_service = SchedulerService()

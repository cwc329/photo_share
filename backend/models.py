from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fb_user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    user_access_token: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=lambda: datetime.now(timezone.utc))

    pages: Mapped[list["Page"]] = relationship("Page",
                                               back_populates="user",
                                               cascade="all, delete-orphan")


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    page_id: Mapped[str] = mapped_column(String(64), index=True)
    page_name: Mapped[str] = mapped_column(String(255))
    page_access_token: Mapped[str] = mapped_column(Text)
    ig_account_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ig_account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="pages")
    scheduled_posts: Mapped[list["ScheduledPost"]] = relationship(
        "ScheduledPost",
        back_populates="page",
        cascade="all, delete-orphan",
        foreign_keys="ScheduledPost.page_id",
    )


class IgAccount(Base):
    """Instagram professional account logged in via Business Login for Instagram."""
    __tablename__ = "ig_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ig_user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_token: Mapped[str] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),
                                                              nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=lambda: datetime.now(timezone.utc))

    scheduled_posts: Mapped[list["ScheduledPost"]] = relationship(
        "ScheduledPost",
        back_populates="ig_account",
        cascade="all, delete-orphan",
        foreign_keys="ScheduledPost.ig_account_id",
    )


class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Exactly one of these two FKs will be set:
    # - page_id: post via Facebook Login for Business (can publish to FB and/or IG linked to the Page)
    # - ig_account_id: post via Instagram Business Login (IG-only, no FB Page)
    page_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("pages.id"), nullable=True)
    ig_account_id: Mapped[int | None] = mapped_column(Integer,
                                                      ForeignKey("ig_accounts.id"),
                                                      nullable=True)

    image_path: Mapped[str] = mapped_column(String(512))
    caption: Mapped[str] = mapped_column(Text)
    platforms: Mapped[list] = mapped_column(JSON)  # ["facebook", "instagram"]
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        String(32), default="pending")  # pending / published / failed / cancelled
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=lambda: datetime.now(timezone.utc))

    page: Mapped["Page | None"] = relationship("Page",
                                               back_populates="scheduled_posts",
                                               foreign_keys=[page_id])
    ig_account: Mapped["IgAccount | None"] = relationship("IgAccount",
                                                          back_populates="scheduled_posts",
                                                          foreign_keys=[ig_account_id])

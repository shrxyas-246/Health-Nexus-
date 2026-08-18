from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ReminderSource, ThreadKind
from app.db.base import Base


class Review(Base):
    """Polymorphic review pointed at any provider type via (target_kind, target_id)."""

    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("author_user_id", "target_kind", "target_id", name="uq_one_review_each"),
    )

    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    target_kind: Mapped[str] = mapped_column(String(20), index=True)
    target_id: Mapped[int] = mapped_column(Integer, index=True)
    rating: Mapped[int] = mapped_column(Integer)  # 1..5
    title: Mapped[str | None] = mapped_column(String(160))
    comment: Mapped[str | None] = mapped_column(Text)
    encounter_id: Mapped[int | None] = mapped_column(ForeignKey("encounters.id", ondelete="SET NULL"))
    is_verified_visit: Mapped[bool] = mapped_column(Boolean, default=False)
    provider_response: Mapped[str | None] = mapped_column(Text)


class ChatThread(Base):
    __tablename__ = "chat_threads"

    kind: Mapped[str] = mapped_column(String(30), default=ThreadKind.PATIENT_DOCTOR, index=True)
    subject: Mapped[str | None] = mapped_column(String(200))
    # For doctor-to-doctor consults about a shared patient.
    about_patient_id: Mapped[int | None] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="SET NULL"), index=True
    )
    condition_id: Mapped[int | None] = mapped_column(ForeignKey("conditions.id", ondelete="SET NULL"))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    participants: Mapped[list[ChatParticipant]] = relationship(
        back_populates="thread", cascade="all, delete-orphan"
    )
    messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="thread", cascade="all, delete-orphan"
    )


class ChatParticipant(Base):
    __tablename__ = "chat_participants"
    __table_args__ = (UniqueConstraint("thread_id", "user_id", name="uq_thread_user"),)

    thread_id: Mapped[int] = mapped_column(
        ForeignKey("chat_threads.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    thread: Mapped[ChatThread] = relationship(back_populates="participants")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    thread_id: Mapped[int] = mapped_column(
        ForeignKey("chat_threads.id", ondelete="CASCADE"), index=True
    )
    sender_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text)
    attachment_url: Mapped[str | None] = mapped_column(String(600))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    thread: Mapped[ChatThread] = relationship(back_populates="messages")


class Post(Base):
    """Health articles and research notes published by doctors."""

    __tablename__ = "posts"

    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    excerpt: Mapped[str | None] = mapped_column(String(400))
    body: Mapped[str] = mapped_column(Text)
    tags: Mapped[str | None] = mapped_column(String(240))
    audience: Mapped[str] = mapped_column(String(20), default="everyone")  # everyone | doctors
    cover_image_url: Mapped[str | None] = mapped_column(String(600))
    read_minutes: Mapped[int] = mapped_column(Integer, default=3)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)


class Reminder(Base):
    """Daily nudges — set by the patient, the treating doctor, or the ML agent."""

    __tablename__ = "reminders"

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(400))
    # "08:00,20:00" — local times the nudge fires at.
    times_of_day: Mapped[str | None] = mapped_column(String(120))
    # "mon,tue,..." — empty means every day.
    days_of_week: Mapped[str | None] = mapped_column(String(60))
    prescription_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("prescription_items.id", ondelete="CASCADE")
    )
    source: Mapped[str] = mapped_column(String(20), default=ReminderSource.SELF)
    target_value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    logs: Mapped[list[ReminderLog]] = relationship(
        back_populates="reminder", cascade="all, delete-orphan"
    )


class ReminderLog(Base):
    __tablename__ = "reminder_logs"

    reminder_id: Mapped[int] = mapped_column(
        ForeignKey("reminders.id", ondelete="CASCADE"), index=True
    )
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    value: Mapped[float | None] = mapped_column(Float)

    reminder: Mapped[Reminder] = relationship(back_populates="logs")


class MLRecommendation(Base):
    """Cached output of the model team's service, kept so the UI reads instantly."""

    __tablename__ = "ml_recommendations"

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(240))
    rationale: Mapped[str | None] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Float, default=0)
    # Free-form model output: ranked entity ids, prices, diet plans, etc.
    payload: Mapped[dict | None] = mapped_column(JSON)
    model_version: Mapped[str | None] = mapped_column(String(40))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False)


class ChatbotMessage(Base):
    """Transcript of the general-question assistant, separate from clinical chat."""

    __tablename__ = "chatbot_messages"

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(12))  # user | assistant
    body: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    escalated_to_doctor: Mapped[bool] = mapped_column(Boolean, default=False)


class Notification(Base):
    __tablename__ = "notifications"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(String(400))
    link: Mapped[str | None] = mapped_column(String(300))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class ChatMessageOut(ORMModel):
    id: int
    thread_id: int
    sender_user_id: int
    sender_name: str | None = None
    sender_role: str | None = None
    body: str
    attachment_url: str | None = None
    sent_at: datetime


class ChatMessageCreate(BaseModel):
    body: str
    attachment_url: str | None = None


class ChatThreadOut(ORMModel):
    id: int
    kind: str
    subject: str | None = None
    about_patient_id: int | None = None
    condition_id: int | None = None
    last_message_at: datetime | None = None
    participant_names: list[str] = []
    unread_count: int = 0
    last_message: str | None = None


class ChatThreadCreate(BaseModel):
    # The other side of the conversation.
    with_user_id: int
    kind: str = "patient_doctor"
    subject: str | None = None
    about_patient_id: int | None = None
    condition_id: int | None = None


class PostOut(ORMModel):
    id: int
    author_user_id: int
    author_name: str | None = None
    author_specialization: str | None = None
    title: str
    excerpt: str | None = None
    body: str | None = None
    tags: str | None = None
    audience: str
    cover_image_url: str | None = None
    read_minutes: int
    like_count: int
    published_at: datetime | None = None


class PostCreate(BaseModel):
    title: str
    body: str
    excerpt: str | None = None
    tags: str | None = None
    audience: str = "everyone"
    cover_image_url: str | None = None
    read_minutes: int = 3


class ReminderOut(ORMModel):
    id: int
    patient_id: int
    kind: str
    title: str
    description: str | None = None
    times_of_day: str | None = None
    days_of_week: str | None = None
    prescription_item_id: int | None = None
    source: str
    target_value: float | None = None
    unit: str | None = None
    is_active: bool


class ReminderCreate(BaseModel):
    kind: str
    title: str
    description: str | None = None
    times_of_day: str | None = None
    days_of_week: str | None = None
    target_value: float | None = None
    unit: str | None = None
    source: str = "self"


class ReminderUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    times_of_day: str | None = None
    days_of_week: str | None = None
    target_value: float | None = None
    is_active: bool | None = None


class ReminderTick(BaseModel):
    """One firing of a reminder on the patient's day view."""

    reminder_id: int
    kind: str
    title: str
    description: str | None = None
    due_at: datetime
    completed: bool
    log_id: int | None = None


class ReminderComplete(BaseModel):
    due_at: datetime
    value: float | None = None
    skipped: bool = False


class RecommendationOut(ORMModel):
    id: int
    kind: str
    title: str
    rationale: str | None = None
    score: float
    payload: dict | None = None
    model_version: str | None = None
    generated_at: datetime
    expires_at: datetime | None = None


class ChatbotMessageOut(ORMModel):
    id: int
    role: str
    body: str
    sent_at: datetime
    escalated_to_doctor: bool


class ChatbotAsk(BaseModel):
    question: str


class NotificationOut(ORMModel):
    id: int
    kind: str
    title: str
    body: str | None = None
    link: str | None = None
    read_at: datetime | None = None
    created_at: datetime

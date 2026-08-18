"""Reviews, chat, posts, notifications — the community layer."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import desc, func, or_, select

from app.api.deps import CurrentUser, DbSession, doctor_can_access_patient
from app.api.v1 import serializers as ser
from app.core.enums import Role, ThreadKind
from app.models import (
    ChatMessage,
    ChatParticipant,
    ChatThread,
    DoctorProfile,
    Encounter,
    Notification,
    Post,
    Review,
    User,
)
from app.schemas.common import Message
from app.schemas.providers import ReviewCreate, ReviewOut
from app.schemas.social import (
    ChatMessageCreate,
    ChatMessageOut,
    ChatThreadCreate,
    ChatThreadOut,
    NotificationOut,
    PostCreate,
    PostOut,
)
from app.services.clock import as_aware
from app.services.ratings import recompute_rating, resolve_target

router = APIRouter(tags=["social"])


# --- reviews -------------------------------------------------------------------


@router.post("/reviews", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def write_review(payload: ReviewCreate, db: DbSession, user: CurrentUser) -> ReviewOut:
    if not 1 <= payload.rating <= 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
    if resolve_target(db, payload.target_kind, payload.target_id) is None:
        raise HTTPException(status_code=404, detail="Review target not found")

    existing = db.scalar(
        select(Review).where(
            Review.author_user_id == user.id,
            Review.target_kind == payload.target_kind,
            Review.target_id == payload.target_id,
        )
    )
    if existing:
        # One review per provider per user: an update replaces it.
        existing.rating = payload.rating
        existing.title = payload.title
        existing.comment = payload.comment
        review = existing
    else:
        verified = False
        if payload.encounter_id and user.patient:
            encounter = db.get(Encounter, payload.encounter_id)
            verified = bool(encounter and encounter.patient_id == user.patient.id)
        review = Review(
            author_user_id=user.id,
            is_verified_visit=verified,
            **payload.model_dump(exclude={"encounter_id"}),
            encounter_id=payload.encounter_id,
        )
        db.add(review)

    db.flush()
    recompute_rating(db, payload.target_kind, payload.target_id)
    db.commit()
    db.refresh(review)
    return _review_out(db, review)


def _review_out(db, review: Review) -> ReviewOut:
    author = db.get(User, review.author_user_id)
    return ReviewOut(
        id=review.id,
        author_user_id=review.author_user_id,
        author_name=author.full_name if author else None,
        target_kind=review.target_kind,
        target_id=review.target_id,
        rating=review.rating,
        title=review.title,
        comment=review.comment,
        is_verified_visit=review.is_verified_visit,
        provider_response=review.provider_response,
        created_at=review.created_at,
    )


@router.get("/reviews", response_model=list[ReviewOut])
def list_reviews(
    db: DbSession, target_kind: str, target_id: int, limit: int = Query(30, le=100), offset: int = 0
) -> list[ReviewOut]:
    rows = db.scalars(
        select(Review)
        .where(Review.target_kind == target_kind, Review.target_id == target_id)
        .order_by(desc(Review.created_at))
        .limit(limit)
        .offset(offset)
    ).all()
    return [_review_out(db, r) for r in rows]


@router.delete("/reviews/{review_id}", response_model=Message)
def delete_review(review_id: int, db: DbSession, user: CurrentUser) -> Message:
    review = db.get(Review, review_id)
    if not review or (review.author_user_id != user.id and user.role != Role.ADMIN):
        raise HTTPException(status_code=404, detail="Review not found")
    kind, target = review.target_kind, review.target_id
    db.delete(review)
    db.flush()
    recompute_rating(db, kind, target)
    db.commit()
    return Message(detail="Review removed")


# --- chat ----------------------------------------------------------------------


def _thread_out(db, thread: ChatThread, for_user_id: int) -> ChatThreadOut:
    names = []
    unread = 0
    for participant in thread.participants:
        member = db.get(User, participant.user_id)
        if member and member.id != for_user_id:
            names.append(member.full_name)
        if participant.user_id == for_user_id:
            last_read = as_aware(participant.last_read_at)
            unread = (
                db.query(ChatMessage)
                .filter(
                    ChatMessage.thread_id == thread.id,
                    ChatMessage.sender_user_id != for_user_id,
                    *( [ChatMessage.sent_at > last_read] if last_read else [] ),
                )
                .count()
            )
    last = db.scalar(
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread.id)
        .order_by(desc(ChatMessage.sent_at))
    )
    return ChatThreadOut(
        id=thread.id,
        kind=thread.kind,
        subject=thread.subject,
        about_patient_id=thread.about_patient_id,
        condition_id=thread.condition_id,
        last_message_at=thread.last_message_at,
        participant_names=names,
        unread_count=unread,
        last_message=last.body[:120] if last else None,
    )


@router.post("/chat/threads", response_model=ChatThreadOut, status_code=status.HTTP_201_CREATED)
def open_thread(payload: ChatThreadCreate, db: DbSession, user: CurrentUser) -> ChatThreadOut:
    other = db.get(User, payload.with_user_id)
    if not other or not other.is_active:
        raise HTTPException(status_code=404, detail="User not found")
    if other.id == user.id:
        raise HTTPException(status_code=400, detail="Cannot open a thread with yourself")

    # Guard the pairing rules: patients talk to their doctors; doctors talk to
    # patients they treat and to fellow doctors about shared patients.
    pair = {user.role, other.role}
    if pair == {Role.PATIENT, Role.DOCTOR}:
        patient_user = user if user.role == Role.PATIENT else other
        doctor_user = other if user.role == Role.PATIENT else user
        doctor = db.scalar(select(DoctorProfile).where(DoctorProfile.user_id == doctor_user.id))
        if not (
            doctor
            and patient_user.patient
            and doctor_can_access_patient(db, doctor.id, patient_user.patient.id)
        ):
            raise HTTPException(
                status_code=403, detail="Chat opens after an appointment or consultation"
            )
        kind = ThreadKind.PATIENT_DOCTOR
    elif pair == {Role.DOCTOR}:
        kind = ThreadKind.DOCTOR_DOCTOR
        if payload.about_patient_id:
            my_doctor = db.scalar(select(DoctorProfile).where(DoctorProfile.user_id == user.id))
            if not (my_doctor and doctor_can_access_patient(db, my_doctor.id, payload.about_patient_id)):
                raise HTTPException(status_code=403, detail="No care relationship with that patient")
    else:
        raise HTTPException(status_code=403, detail="This pairing cannot chat")

    # Reuse an existing thread between the same two people on the same subject.
    mine = select(ChatParticipant.thread_id).where(ChatParticipant.user_id == user.id)
    theirs = select(ChatParticipant.thread_id).where(ChatParticipant.user_id == other.id)
    existing = db.scalar(
        select(ChatThread).where(
            ChatThread.id.in_(mine),
            ChatThread.id.in_(theirs),
            ChatThread.kind == kind,
            ChatThread.about_patient_id.is_(None)
            if payload.about_patient_id is None
            else ChatThread.about_patient_id == payload.about_patient_id,
        )
    )
    if existing:
        return _thread_out(db, existing, user.id)

    thread = ChatThread(
        kind=kind,
        subject=payload.subject,
        about_patient_id=payload.about_patient_id,
        condition_id=payload.condition_id,
    )
    db.add(thread)
    db.flush()
    db.add(ChatParticipant(thread_id=thread.id, user_id=user.id))
    db.add(ChatParticipant(thread_id=thread.id, user_id=other.id))
    db.commit()
    db.refresh(thread)
    return _thread_out(db, thread, user.id)


@router.get("/chat/threads", response_model=list[ChatThreadOut])
def list_my_threads(db: DbSession, user: CurrentUser) -> list[ChatThreadOut]:
    thread_ids = select(ChatParticipant.thread_id).where(ChatParticipant.user_id == user.id)
    threads = db.scalars(
        select(ChatThread)
        .where(ChatThread.id.in_(thread_ids))
        .order_by(desc(func.coalesce(ChatThread.last_message_at, ChatThread.created_at)))
    ).all()
    return [_thread_out(db, t, user.id) for t in threads]


def _membership(db, thread_id: int, user_id: int) -> ChatParticipant:
    participant = db.scalar(
        select(ChatParticipant).where(
            ChatParticipant.thread_id == thread_id, ChatParticipant.user_id == user_id
        )
    )
    if not participant:
        raise HTTPException(status_code=403, detail="Not a participant in this thread")
    return participant


@router.get("/chat/threads/{thread_id}/messages", response_model=list[ChatMessageOut])
def read_messages(
    thread_id: int, db: DbSession, user: CurrentUser, limit: int = Query(50, le=200), offset: int = 0
) -> list[ChatMessageOut]:
    participant = _membership(db, thread_id, user.id)
    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread_id)
        .order_by(desc(ChatMessage.sent_at))
        .limit(limit)
        .offset(offset)
    ).all()
    participant.last_read_at = datetime.now(UTC)
    db.commit()

    out = []
    for message in reversed(rows):
        sender = db.get(User, message.sender_user_id)
        out.append(
            ChatMessageOut(
                id=message.id,
                thread_id=message.thread_id,
                sender_user_id=message.sender_user_id,
                sender_name=sender.full_name if sender else None,
                sender_role=sender.role if sender else None,
                body=message.body,
                attachment_url=message.attachment_url,
                sent_at=message.sent_at,
            )
        )
    return out


@router.post(
    "/chat/threads/{thread_id}/messages",
    response_model=ChatMessageOut,
    status_code=status.HTTP_201_CREATED,
)
def send_message(
    thread_id: int, payload: ChatMessageCreate, db: DbSession, user: CurrentUser
) -> ChatMessageOut:
    _membership(db, thread_id, user.id)
    thread = db.get(ChatThread, thread_id)

    message = ChatMessage(
        thread_id=thread_id,
        sender_user_id=user.id,
        body=payload.body,
        attachment_url=payload.attachment_url,
        sent_at=datetime.now(UTC),
    )
    db.add(message)
    thread.last_message_at = message.sent_at

    for participant in thread.participants:
        if participant.user_id != user.id:
            db.add(
                Notification(
                    user_id=participant.user_id,
                    kind="chat_message",
                    title=f"Message from {user.full_name}",
                    body=payload.body[:120],
                    link=f"/chat/{thread_id}",
                )
            )
    db.commit()
    db.refresh(message)
    return ChatMessageOut(
        id=message.id,
        thread_id=message.thread_id,
        sender_user_id=user.id,
        sender_name=user.full_name,
        sender_role=user.role,
        body=message.body,
        attachment_url=message.attachment_url,
        sent_at=message.sent_at,
    )


# --- posts ---------------------------------------------------------------------


@router.get("/posts", response_model=list[PostOut])
def list_posts(
    db: DbSession,
    user: CurrentUser,
    tag: str | None = None,
    q: str | None = None,
    limit: int = Query(20, le=100),
    offset: int = 0,
) -> list[PostOut]:
    query = select(Post).where(Post.is_published.is_(True))
    # Doctor-only research posts stay out of patient feeds.
    if user.role != Role.DOCTOR:
        query = query.where(Post.audience == "everyone")
    if tag:
        query = query.where(Post.tags.ilike(f"%{tag}%"))
    if q:
        query = query.where(or_(Post.title.ilike(f"%{q}%"), Post.body.ilike(f"%{q}%")))
    rows = db.scalars(
        query.order_by(desc(Post.published_at)).limit(limit).offset(offset)
    ).all()
    return [ser.post_out(db, p) for p in rows]


@router.post("/posts", response_model=PostOut, status_code=status.HTTP_201_CREATED)
def publish_post(payload: PostCreate, db: DbSession, user: CurrentUser) -> PostOut:
    if user.role != Role.DOCTOR:
        raise HTTPException(status_code=403, detail="Only doctors can publish posts")
    post = Post(
        author_user_id=user.id,
        published_at=datetime.now(UTC),
        **payload.model_dump(),
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return ser.post_out(db, post)


@router.post("/posts/{post_id}/like", response_model=PostOut)
def like_post(post_id: int, db: DbSession, user: CurrentUser) -> PostOut:
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    post.like_count += 1
    db.commit()
    db.refresh(post)
    return ser.post_out(db, post)


# --- notifications -------------------------------------------------------------


@router.get("/notifications/me", response_model=list[NotificationOut])
def list_my_notifications(
    db: DbSession, user: CurrentUser, unread_only: bool = False, limit: int = Query(30, le=100)
) -> list[Notification]:
    query = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    return db.scalars(query.order_by(desc(Notification.created_at)).limit(limit)).all()


@router.post("/notifications/read-all", response_model=Message)
def mark_all_read(db: DbSession, user: CurrentUser) -> Message:
    db.query(Notification).filter(
        Notification.user_id == user.id, Notification.read_at.is_(None)
    ).update({"read_at": datetime.now(UTC)}, synchronize_session=False)
    db.commit()
    return Message(detail="All notifications marked read")

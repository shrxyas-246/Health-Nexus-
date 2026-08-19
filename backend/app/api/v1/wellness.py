"""Reminders, the daily agent, and the general-question chatbot."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import desc, select

from app.api.deps import CurrentPatient, DbSession
from app.core.enums import ConditionStatus, PrescriptionStatus
from app.models import (
    ChatbotMessage,
    Condition,
    Prescription,
    PrescriptionItem,
    Reminder,
    ReminderLog,
)
from app.schemas.common import Message
from app.schemas.social import (
    ChatbotAsk,
    ChatbotMessageOut,
    ReminderComplete,
    ReminderCreate,
    ReminderOut,
    ReminderTick,
    ReminderUpdate,
)
from app.services import ml_client

router = APIRouter(prefix="/wellness", tags=["wellness"])

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


# --- reminders -----------------------------------------------------------------


@router.get("/reminders", response_model=list[ReminderOut])
def list_reminders(
    db: DbSession, patient: CurrentPatient, active_only: bool = True
) -> list[Reminder]:
    query = select(Reminder).where(Reminder.patient_id == patient.id)
    if active_only:
        query = query.where(Reminder.is_active.is_(True))
    return db.scalars(query.order_by(Reminder.kind)).all()


@router.post("/reminders", response_model=ReminderOut, status_code=status.HTTP_201_CREATED)
def create_reminder(
    payload: ReminderCreate, db: DbSession, patient: CurrentPatient
) -> Reminder:
    reminder = Reminder(patient_id=patient.id, **payload.model_dump())
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.patch("/reminders/{reminder_id}", response_model=ReminderOut)
def update_reminder(
    reminder_id: int, payload: ReminderUpdate, db: DbSession, patient: CurrentPatient
) -> Reminder:
    reminder = db.get(Reminder, reminder_id)
    if not reminder or reminder.patient_id != patient.id:
        raise HTTPException(status_code=404, detail="Reminder not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(reminder, field, value)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.delete("/reminders/{reminder_id}", response_model=Message)
def delete_reminder(reminder_id: int, db: DbSession, patient: CurrentPatient) -> Message:
    reminder = db.get(Reminder, reminder_id)
    if not reminder or reminder.patient_id != patient.id:
        raise HTTPException(status_code=404, detail="Reminder not found")
    db.delete(reminder)
    db.commit()
    return Message(detail="Reminder removed")


@router.get("/reminders/today", response_model=list[ReminderTick])
def todays_schedule(db: DbSession, patient: CurrentPatient) -> list[ReminderTick]:
    """Expand active reminders into today's concrete due times, with completion state."""
    now = datetime.now(UTC)
    day_key = WEEKDAYS[now.weekday()]
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    reminders = db.scalars(
        select(Reminder).where(Reminder.patient_id == patient.id, Reminder.is_active.is_(True))
    ).all()

    ticks: list[ReminderTick] = []
    for reminder in reminders:
        if reminder.days_of_week and day_key not in reminder.days_of_week.lower():
            continue
        for time_str in (reminder.times_of_day or "09:00").split(","):
            time_str = time_str.strip()
            try:
                hour, minute = (int(x) for x in time_str.split(":"))
            except ValueError:
                continue
            due = start.replace(hour=hour, minute=minute)

            log = db.scalar(
                select(ReminderLog).where(
                    ReminderLog.reminder_id == reminder.id,
                    ReminderLog.due_at >= start,
                    ReminderLog.due_at < end,
                    ReminderLog.due_at == due,
                )
            )
            ticks.append(
                ReminderTick(
                    reminder_id=reminder.id,
                    kind=reminder.kind,
                    title=reminder.title,
                    description=reminder.description,
                    due_at=due,
                    completed=bool(log and log.completed_at),
                    log_id=log.id if log else None,
                )
            )
    ticks.sort(key=lambda t: t.due_at)
    return ticks


@router.post("/reminders/{reminder_id}/complete", response_model=Message)
def complete_reminder(
    reminder_id: int, payload: ReminderComplete, db: DbSession, patient: CurrentPatient
) -> Message:
    reminder = db.get(Reminder, reminder_id)
    if not reminder or reminder.patient_id != patient.id:
        raise HTTPException(status_code=404, detail="Reminder not found")

    log = db.scalar(
        select(ReminderLog).where(
            ReminderLog.reminder_id == reminder.id, ReminderLog.due_at == payload.due_at
        )
    )
    if not log:
        log = ReminderLog(reminder_id=reminder.id, due_at=payload.due_at)
        db.add(log)
    log.completed_at = None if payload.skipped else datetime.now(UTC)
    log.skipped = payload.skipped
    log.value = payload.value
    db.commit()
    return Message(detail="Marked as skipped" if payload.skipped else "Done — nice work")


# --- chatbot -------------------------------------------------------------------

# Rule-based answers for the most common general questions. Model 1 (the trained
# guidance assistant in the ML service) answers when it is reachable; these rules
# are the fallback for when it is not, so the assistant never goes dark.
FAQ_RULES: list[tuple[tuple[str, ...], str]] = [
    (
        ("water", "hydrat"),
        "Most adults do well on 2–3 litres of water a day, more in hot weather or with exercise. "
        "Your water reminders can help you spread it across the day.",
    ),
    (
        ("sleep",),
        "Adults generally need 7–9 hours of sleep. A consistent bedtime and less screen time "
        "before bed make the biggest difference.",
    ),
    (
        ("bmi",),
        "BMI is weight (kg) divided by height (m) squared. 18.5–24.9 is considered the normal "
        "range. Your profile shows yours automatically once height and weight are set.",
    ),
    (
        ("fever", "temperature"),
        "A fever above 38°C that lasts more than 2–3 days, or any fever with severe symptoms, "
        "deserves a doctor's attention. You can book a consultation right from the app.",
    ),
    (
        ("headache", "migraine"),
        "Occasional headaches are usually harmless — hydration, rest and regular meals help. "
        "Sudden severe headaches or ones with vision changes need prompt medical review.",
    ),
    (
        ("diet", "food", "eat"),
        "A balanced plate: half vegetables and fruit, a quarter whole grains, a quarter protein. "
        "If your doctor has given you diet advice, it's saved with your current prescription.",
    ),
    (
        ("exercise", "workout"),
        "Aim for about 150 minutes of moderate activity a week — brisk walking counts. "
        "Start small and build up; consistency beats intensity.",
    ),
    (
        ("medicine", "tablet", "dose", "missed"),
        "If you missed a dose, take it when you remember unless it's nearly time for the next one — "
        "never double up. For anything specific to your prescription, message your doctor in the app.",
    ),
]

ESCALATION_KEYWORDS = (
    "chest pain", "breathless", "can't breathe", "cannot breathe", "unconscious",
    "suicide", "self harm", "bleeding heavily", "stroke", "seizure", "overdose",
)

DISCLAIMER = " (General guidance only — not a diagnosis. For anything serious, please consult your doctor.)"


def _answer(question: str) -> tuple[str, bool]:
    lowered = question.lower()
    if any(keyword in lowered for keyword in ESCALATION_KEYWORDS):
        return (
            "This sounds urgent. Please use the Emergency button in the app or call your local "
            "emergency number right away — a chatbot is not the right help for this.",
            True,
        )
    for keywords, response in FAQ_RULES:
        if any(k in lowered for k in keywords):
            return response + DISCLAIMER, False
    return (
        "I can help with general questions about sleep, diet, hydration, exercise and your "
        "medicines schedule. For anything about your specific condition, your doctor is one "
        "tap away in the chat tab." ,
        False,
    )


def _chat_context(db, patient) -> dict:
    """The slice of the record the assistant is allowed to personalise from.

    Only what a general-guidance answer can legitimately use: current medicines,
    active conditions and BMI. No reports, no notes, no free text — the model is
    answering general questions, not reading the chart.
    """
    prescription = db.scalar(
        select(Prescription)
        .where(
            Prescription.patient_id == patient.id,
            Prescription.status == PrescriptionStatus.ACTIVE,
        )
        .order_by(desc(Prescription.issued_at))
    )
    medicines: list[str] = []
    if prescription:
        items = db.scalars(
            select(PrescriptionItem).where(PrescriptionItem.prescription_id == prescription.id)
        ).all()
        medicines = [
            " ".join(filter(None, [item.medicine_name, item.strength])) for item in items
        ]

    conditions = db.scalars(
        select(Condition).where(
            Condition.patient_id == patient.id, Condition.status != ConditionStatus.RESOLVED
        )
    ).all()

    return {
        "bmi": patient.bmi,
        "medicines": medicines,
        "conditions": [{"name": c.name, "category": c.category} for c in conditions],
    }


@router.post("/chatbot/ask", response_model=list[ChatbotMessageOut])
def ask_chatbot(payload: ChatbotAsk, db: DbSession, patient: CurrentPatient) -> list[ChatbotMessage]:
    now = datetime.now(UTC)
    question = ChatbotMessage(
        patient_id=patient.id, role="user", body=payload.question, sent_at=now
    )

    reply = ml_client.get_chat_reply(payload.question, _chat_context(db, patient))
    if reply:
        answer_text, escalate = reply["answer"], reply["escalate"]
    else:
        answer_text, escalate = _answer(payload.question)

    answer = ChatbotMessage(
        patient_id=patient.id,
        role="assistant",
        body=answer_text,
        sent_at=now,
        escalated_to_doctor=escalate,
    )
    db.add_all([question, answer])
    db.commit()
    db.refresh(question)
    db.refresh(answer)
    return [question, answer]


@router.get("/chatbot/history", response_model=list[ChatbotMessageOut])
def chatbot_history(
    db: DbSession, patient: CurrentPatient, limit: int = Query(50, le=200)
) -> list[ChatbotMessage]:
    rows = db.scalars(
        select(ChatbotMessage)
        .where(ChatbotMessage.patient_id == patient.id)
        .order_by(desc(ChatbotMessage.sent_at))
        .limit(limit)
    ).all()
    return list(reversed(rows))

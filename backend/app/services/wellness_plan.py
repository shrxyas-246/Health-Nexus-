"""Builds the patient record model 2 needs, and caches the plan it returns.

The daily plan is generated once per patient per day and stored as
``MLRecommendation`` rows, so the Plus tab reads instantly and the same advice is
shown all day rather than shifting between page loads. A patient can force a
regeneration from the UI.

Nothing here calls the model directly — it goes through ``ml_client``, which
returns ``None`` when the ML service is unreachable. In that case the caller
serves whatever plan is already cached, and the patient sees yesterday's plan
rather than an error.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.enums import ConditionStatus, PrescriptionStatus, VitalType
from app.models import (
    Condition,
    MLRecommendation,
    PatientProfile,
    Prescription,
    PrescriptionItem,
    Surgery,
    VitalReading,
)
from app.services import ml_client

PLAN_KINDS = ("diet", "workout", "lifestyle")

# Vitals the wellness model reads, mapped to the names it expects.
VITAL_KINDS = {
    VitalType.BP_SYSTOLIC: "systolic",
    VitalType.BP_DIASTOLIC: "diastolic",
    VitalType.HEART_RATE: "heart_rate",
    VitalType.HBA1C: "hba1c",
}

# Daily step count -> the model's 0–3 activity scale.
STEP_BANDS = ((4000, 0), (7500, 1), (11000, 2))


def _age(patient: PatientProfile) -> int | None:
    if not patient.date_of_birth:
        return None
    today = date.today()
    return today.year - patient.date_of_birth.year - (
        (today.month, today.day) < (patient.date_of_birth.month, patient.date_of_birth.day)
    )


def _recent_average(db: Session, patient_id: int, kind: str, days: int = 30) -> float | None:
    since = datetime.now(UTC) - timedelta(days=days)
    values = db.scalars(
        select(VitalReading.value).where(
            VitalReading.patient_id == patient_id,
            VitalReading.kind == kind,
            VitalReading.recorded_at >= since,
        )
    ).all()
    return round(sum(values) / len(values), 2) if values else None


def build_patient_record(db: Session, patient: PatientProfile) -> dict:
    """Assemble everything model 2 was trained to read, from the live record."""
    conditions = db.scalars(
        select(Condition).where(
            Condition.patient_id == patient.id, Condition.status != ConditionStatus.RESOLVED
        )
    ).all()

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
        medicines = [
            item.medicine_name
            for item in db.scalars(
                select(PrescriptionItem).where(
                    PrescriptionItem.prescription_id == prescription.id
                )
            ).all()
        ]

    vitals = {}
    for kind, name in VITAL_KINDS.items():
        # A month's average, not a single reading: one high afternoon BP should
        # not flip a patient onto a different plan.
        value = _recent_average(db, patient.id, kind)
        if value is not None:
            vitals[name] = value

    steps = _recent_average(db, patient.id, VitalType.STEPS, days=14)
    activity_level = None
    if steps is not None:
        activity_level = next((level for threshold, level in STEP_BANDS if steps < threshold), 3)

    last_surgery = db.scalar(
        select(Surgery)
        .where(Surgery.patient_id == patient.id)
        .order_by(desc(Surgery.performed_on))
    )
    days_since_surgery = (
        (date.today() - last_surgery.performed_on).days
        if last_surgery and last_surgery.performed_on
        else None
    )

    return {
        "patient_id": patient.id,
        "age": _age(patient),
        "gender": patient.gender,
        "height_cm": patient.height_cm,
        "weight_kg": patient.weight_kg,
        "bmi": patient.bmi,
        "conditions": [
            {"name": c.name, "category": c.category, "severity": c.severity} for c in conditions
        ],
        "medicines": medicines,
        "vitals": vitals,
        "sleep_hours": _recent_average(db, patient.id, VitalType.SLEEP_HOURS, days=14),
        "activity_level": activity_level,
        "days_since_surgery": days_since_surgery,
    }


def cached_plan(db: Session, patient: PatientProfile) -> list[MLRecommendation]:
    """Today's stored plan cards, newest first, excluding dismissed ones."""
    now = datetime.now(UTC)
    rows = db.scalars(
        select(MLRecommendation)
        .where(
            MLRecommendation.patient_id == patient.id,
            MLRecommendation.dismissed.is_(False),
            MLRecommendation.kind.in_(PLAN_KINDS),
        )
        .order_by(desc(MLRecommendation.generated_at))
        .limit(10)
    ).all()
    return [
        row
        for row in rows
        if row.expires_at is None or _as_aware(row.expires_at) > now
    ]


def _as_aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def generate_plan(db: Session, patient: PatientProfile) -> list[MLRecommendation]:
    """Ask model 2 for today's plan and cache it. Returns [] if the model is down."""
    plan = ml_client.get_wellness_plan(build_patient_record(db, patient))
    if not plan:
        return []

    now = datetime.now(UTC)
    # Retire the cards this run replaces, rather than letting them accumulate.
    for stale in db.scalars(
        select(MLRecommendation).where(
            MLRecommendation.patient_id == patient.id,
            MLRecommendation.kind.in_(PLAN_KINDS),
        )
    ).all():
        stale.dismissed = True

    created: list[MLRecommendation] = []
    for card in plan["cards"]:
        row = MLRecommendation(
            patient_id=patient.id,
            kind=card["kind"],
            title=card["title"],
            rationale=card.get("rationale"),
            score=float(card.get("score") or 0),
            payload=card.get("payload"),
            model_version=plan.get("model_version"),
            generated_at=now,
            expires_at=now + timedelta(days=1),
            dismissed=False,
        )
        db.add(row)
        created.append(row)

    db.commit()
    for row in created:
        db.refresh(row)
    return created


def plan_is_stale(rows: list[MLRecommendation]) -> bool:
    """True when there is no plan from the last 24 hours."""
    if not rows:
        return True
    newest = max(_as_aware(row.generated_at) for row in rows)
    return datetime.now(UTC) - newest > timedelta(hours=24)

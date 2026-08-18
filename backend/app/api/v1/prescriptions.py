from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select

from app.api.deps import (
    CurrentDoctor,
    CurrentUser,
    DbSession,
    doctor_can_access_patient,
    resolve_patient_access,
)
from app.api.v1 import serializers as ser
from app.core.enums import PrescriptionStatus, ReminderKind, ReminderSource, Role, TimelineKind
from app.models import (
    CareTeamLink,
    Prescription,
    PrescriptionItem,
    Reminder,
    TestRequest,
    User,
)
from app.schemas.clinical import (
    PrescriptionCreate,
    PrescriptionOut,
    PrescriptionRevise,
    PrescriptionVersion,
)
from app.schemas.common import Message

router = APIRouter(prefix="/prescriptions", tags=["prescriptions"])

# Frequency phrasing -> the times of day a medicine reminder should fire.
FREQUENCY_TIMES = {
    "once daily": "08:00",
    "daily": "08:00",
    "twice daily": "08:00,20:00",
    "thrice daily": "08:00,14:00,20:00",
    "three times daily": "08:00,14:00,20:00",
    "four times daily": "06:00,12:00,18:00,22:00",
    "nightly": "21:00",
    "at bedtime": "22:00",
    "weekly": "09:00",
}


def _reminder_times(frequency: str | None) -> str:
    if not frequency:
        return "09:00"
    return FREQUENCY_TIMES.get(frequency.strip().lower(), "09:00")


def _build_items_and_tests(db, prescription: Prescription, payload: PrescriptionCreate) -> None:
    for item in payload.items:
        db.add(PrescriptionItem(prescription_id=prescription.id, **item.model_dump()))
    for test in payload.test_requests:
        db.add(
            TestRequest(
                prescription_id=prescription.id,
                patient_id=prescription.patient_id,
                doctor_id=prescription.doctor_id,
                **test.model_dump(),
            )
        )
    db.flush()


def _sync_medicine_reminders(db, prescription: Prescription) -> None:
    """Keep the patient's medicine reminders in step with the live prescription."""
    old = (
        db.query(Reminder)
        .filter(
            Reminder.patient_id == prescription.patient_id,
            Reminder.kind == ReminderKind.MEDICINE,
            Reminder.source == ReminderSource.DOCTOR,
        )
        .all()
    )
    for reminder in old:
        reminder.is_active = False

    for item in prescription.items:
        db.add(
            Reminder(
                patient_id=prescription.patient_id,
                kind=ReminderKind.MEDICINE,
                title=f"Take {item.medicine_name}"
                + (f" {item.strength}" if item.strength else ""),
                description=" · ".join(
                    part for part in [item.dosage, item.frequency, item.timing] if part
                ),
                times_of_day=_reminder_times(item.frequency),
                prescription_item_id=item.id,
                source=ReminderSource.DOCTOR,
                is_active=True,
            )
        )
    db.flush()


@router.post(
    "/patients/{patient_id}",
    response_model=PrescriptionOut,
    status_code=status.HTTP_201_CREATED,
)
def write_prescription(
    patient_id: int,
    payload: PrescriptionCreate,
    db: DbSession,
    user: CurrentUser,
    doctor: CurrentDoctor,
) -> PrescriptionOut:
    """Doctor writes a new prescription; medicine reminders are created from it."""
    patient = resolve_patient_access(db, user, patient_id)

    prescription = Prescription(
        patient_id=patient.id,
        doctor_id=doctor.id,
        encounter_id=payload.encounter_id,
        condition_id=payload.condition_id,
        version=1,
        status=PrescriptionStatus.ACTIVE,
        issued_at=datetime.now(UTC),
        valid_until=payload.valid_until,
        diagnosis_summary=payload.diagnosis_summary,
        diet_advice=payload.diet_advice,
        lifestyle_advice=payload.lifestyle_advice,
        notes=payload.notes,
    )
    db.add(prescription)
    db.flush()
    _build_items_and_tests(db, prescription, payload)
    db.refresh(prescription)
    _sync_medicine_reminders(db, prescription)

    # Writing a prescription puts the doctor on the patient's care team.
    if not db.scalar(
        select(CareTeamLink.id).where(
            CareTeamLink.patient_id == patient.id, CareTeamLink.doctor_id == doctor.id
        )
    ):
        db.add(CareTeamLink(patient_id=patient.id, doctor_id=doctor.id))

    from app.services.timeline import record_event

    doctor_user = db.get(User, doctor.user_id)
    record_event(
        db,
        patient_id=patient.id,
        kind=TimelineKind.PRESCRIPTION,
        occurred_at=prescription.issued_at,
        title=f"Prescription from {doctor_user.full_name}",
        summary=", ".join(i.medicine_name for i in prescription.items) or payload.diagnosis_summary,
        doctor_id=doctor.id,
        condition_id=payload.condition_id,
        ref_table="prescriptions",
        ref_id=prescription.id,
    )
    db.commit()
    db.refresh(prescription)
    return ser.prescription_out(db, prescription)


@router.post("/{prescription_id}/revise", response_model=PrescriptionOut)
def revise_prescription(
    prescription_id: int,
    payload: PrescriptionRevise,
    db: DbSession,
    doctor: CurrentDoctor,
) -> PrescriptionOut:
    """Supersede a prescription with a new version. The old one is never mutated."""
    previous = db.get(Prescription, prescription_id)
    if not previous:
        raise HTTPException(status_code=404, detail="Prescription not found")
    if not doctor_can_access_patient(db, doctor.id, previous.patient_id):
        raise HTTPException(status_code=403, detail="No care relationship with this patient")

    previous.status = PrescriptionStatus.SUPERSEDED

    revision = Prescription(
        patient_id=previous.patient_id,
        doctor_id=doctor.id,
        encounter_id=payload.encounter_id or previous.encounter_id,
        condition_id=payload.condition_id or previous.condition_id,
        supersedes_id=previous.id,
        version=previous.version + 1,
        status=PrescriptionStatus.ACTIVE,
        issued_at=datetime.now(UTC),
        valid_until=payload.valid_until,
        diagnosis_summary=payload.diagnosis_summary or previous.diagnosis_summary,
        diet_advice=payload.diet_advice,
        lifestyle_advice=payload.lifestyle_advice,
        change_note=payload.change_note,
        notes=payload.notes,
    )
    db.add(revision)
    db.flush()
    _build_items_and_tests(db, revision, payload)
    db.refresh(revision)
    _sync_medicine_reminders(db, revision)

    from app.services.timeline import record_event

    record_event(
        db,
        patient_id=revision.patient_id,
        kind=TimelineKind.PRESCRIPTION,
        occurred_at=revision.issued_at,
        title=f"Prescription updated (v{revision.version})",
        summary=payload.change_note,
        doctor_id=doctor.id,
        condition_id=revision.condition_id,
        ref_table="prescriptions",
        ref_id=revision.id,
    )
    db.commit()
    db.refresh(revision)
    return ser.prescription_out(db, revision)


@router.get("/patients/{patient_id}", response_model=list[PrescriptionOut])
def list_for_patient(
    patient_id: int,
    db: DbSession,
    user: CurrentUser,
    include_superseded: bool = True,
) -> list[PrescriptionOut]:
    patient = resolve_patient_access(db, user, patient_id)
    query = select(Prescription).where(Prescription.patient_id == patient.id)
    if not include_superseded:
        query = query.where(Prescription.status == PrescriptionStatus.ACTIVE)
    rows = db.scalars(query.order_by(desc(Prescription.issued_at))).all()
    return [ser.prescription_out(db, p) for p in rows]


@router.get("/patients/{patient_id}/current", response_model=PrescriptionOut | None)
def current_for_patient(patient_id: int, db: DbSession, user: CurrentUser) -> PrescriptionOut | None:
    patient = resolve_patient_access(db, user, patient_id)
    prescription = db.scalar(
        select(Prescription)
        .where(
            Prescription.patient_id == patient.id,
            Prescription.status == PrescriptionStatus.ACTIVE,
        )
        .order_by(desc(Prescription.issued_at))
    )
    return ser.prescription_out(db, prescription) if prescription else None


@router.get("/{prescription_id}", response_model=PrescriptionOut)
def read_prescription(prescription_id: int, db: DbSession, user: CurrentUser) -> PrescriptionOut:
    prescription = db.get(Prescription, prescription_id)
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")
    resolve_patient_access(db, user, prescription.patient_id)
    return ser.prescription_out(db, prescription)


@router.get("/{prescription_id}/versions", response_model=list[PrescriptionVersion])
def read_versions(prescription_id: int, db: DbSession, user: CurrentUser) -> list[PrescriptionVersion]:
    """Walk the supersede chain in both directions and return every version."""
    prescription = db.get(Prescription, prescription_id)
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")
    resolve_patient_access(db, user, prescription.patient_id)

    chain: list[Prescription] = []

    # Walk backwards to the original.
    node = prescription
    while node:
        chain.append(node)
        node = db.get(Prescription, node.supersedes_id) if node.supersedes_id else None

    # Walk forwards to the newest revision.
    node = db.scalar(select(Prescription).where(Prescription.supersedes_id == prescription.id))
    while node:
        chain.append(node)
        node = db.scalar(select(Prescription).where(Prescription.supersedes_id == node.id))

    chain.sort(key=lambda p: p.version, reverse=True)
    return [
        PrescriptionVersion(
            id=p.id,
            version=p.version,
            issued_at=p.issued_at,
            status=p.status,
            change_note=p.change_note,
            doctor_name=ser._doctor_name(db, p.doctor_id),
        )
        for p in chain
    ]


@router.post("/{prescription_id}/complete", response_model=Message)
def mark_completed(prescription_id: int, db: DbSession, user: CurrentUser) -> Message:
    prescription = db.get(Prescription, prescription_id)
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")
    resolve_patient_access(db, user, prescription.patient_id)
    prescription.status = PrescriptionStatus.COMPLETED
    db.commit()
    return Message(detail="Prescription marked complete")

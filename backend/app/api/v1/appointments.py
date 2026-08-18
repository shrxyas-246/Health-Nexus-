from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import desc, select

from app.api.deps import CurrentPatient, CurrentUser, DbSession
from app.api.v1 import serializers as ser
from app.core.enums import (
    AppointmentStatus,
    EncounterType,
    PaymentPurpose,
    Role,
    TimelineKind,
)
from app.models import Appointment, CareTeamLink, DoctorProfile, Encounter, User
from app.schemas.common import Message
from app.schemas.orders import (
    AppointmentCreate,
    AppointmentOut,
    AppointmentStatusUpdate,
)
from app.services.payments import record_payment
from app.services.timeline import record_event

router = APIRouter(prefix="/appointments", tags=["appointments"])

CANCELLABLE = {AppointmentStatus.REQUESTED, AppointmentStatus.CONFIRMED}


def _load_for_actor(db, appointment_id: int, user: User) -> Appointment:
    """Fetch an appointment only if this user is one of its two parties."""
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if user.role == Role.PATIENT:
        if not user.patient or appointment.patient_id != user.patient.id:
            raise HTTPException(status_code=403, detail="Not your appointment")
    elif user.role == Role.DOCTOR:
        if not user.doctor or appointment.doctor_id != user.doctor.id:
            raise HTTPException(status_code=403, detail="Not your appointment")
    elif user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Not permitted")
    return appointment


@router.post("", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
def book_appointment(
    payload: AppointmentCreate, db: DbSession, patient: CurrentPatient
) -> AppointmentOut:
    doctor = db.get(DoctorProfile, payload.doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    clash = db.scalar(
        select(Appointment.id).where(
            Appointment.doctor_id == doctor.id,
            Appointment.scheduled_at == payload.scheduled_at,
            Appointment.status.in_([AppointmentStatus.REQUESTED, AppointmentStatus.CONFIRMED]),
        )
    )
    if clash:
        raise HTTPException(status_code=409, detail="That slot is already taken")

    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        hospital_id=payload.hospital_id or doctor.hospital_id,
        scheduled_at=payload.scheduled_at,
        mode=payload.mode,
        reason=payload.reason,
        fee=doctor.consultation_fee,
        is_follow_up=payload.is_follow_up,
        status=AppointmentStatus.REQUESTED,
    )
    db.add(appointment)
    db.flush()

    # Consultation fee is collected up front; the platform commission is split
    # out on the payment row.
    if doctor.consultation_fee:
        record_payment(
            db,
            patient_id=patient.id,
            purpose=PaymentPurpose.APPOINTMENT,
            amount=doctor.consultation_fee,
            payee_kind="doctor",
            payee_id=doctor.id,
            ref_table="appointments",
            ref_id=appointment.id,
            description=f"Consultation — {ser._doctor_name(db, doctor.id)}",
        )

    db.commit()
    db.refresh(appointment)
    return ser.appointment_out(db, appointment)


@router.get("/me", response_model=list[AppointmentOut])
def list_my_appointments(
    db: DbSession,
    user: CurrentUser,
    upcoming_only: bool = False,
    status_filter: str | None = Query(None, alias="status"),
) -> list[AppointmentOut]:
    if user.role == Role.PATIENT and user.patient:
        query = select(Appointment).where(Appointment.patient_id == user.patient.id)
    elif user.role == Role.DOCTOR and user.doctor:
        query = select(Appointment).where(Appointment.doctor_id == user.doctor.id)
    else:
        raise HTTPException(status_code=403, detail="Only patients and doctors have appointments")

    if status_filter:
        query = query.where(Appointment.status == status_filter)
    if upcoming_only:
        query = query.where(Appointment.scheduled_at >= datetime.now(UTC))

    rows = db.scalars(query.order_by(desc(Appointment.scheduled_at))).all()
    return [ser.appointment_out(db, a) for a in rows]


@router.get("/{appointment_id}", response_model=AppointmentOut)
def read_appointment(appointment_id: int, db: DbSession, user: CurrentUser) -> AppointmentOut:
    return ser.appointment_out(db, _load_for_actor(db, appointment_id, user))


@router.patch("/{appointment_id}/status", response_model=AppointmentOut)
def update_status(
    appointment_id: int, payload: AppointmentStatusUpdate, db: DbSession, user: CurrentUser
) -> AppointmentOut:
    appointment = _load_for_actor(db, appointment_id, user)
    new_status = payload.status

    if new_status == AppointmentStatus.CANCELLED:
        if appointment.status not in CANCELLABLE:
            raise HTTPException(
                status_code=409, detail=f"A {appointment.status} appointment cannot be cancelled"
            )
        appointment.cancelled_reason = payload.cancelled_reason
    elif new_status in {AppointmentStatus.CONFIRMED, AppointmentStatus.NO_SHOW} and user.role != Role.DOCTOR:
        raise HTTPException(status_code=403, detail="Only the doctor can set this status")

    appointment.status = new_status

    # Completing an appointment opens the clinical encounter it belongs to.
    if new_status == AppointmentStatus.COMPLETED and not appointment.encounter_id:
        encounter = Encounter(
            patient_id=appointment.patient_id,
            doctor_id=appointment.doctor_id,
            hospital_id=appointment.hospital_id,
            kind=EncounterType.FOLLOW_UP if appointment.is_follow_up else EncounterType.CONSULTATION,
            started_at=appointment.scheduled_at,
            ended_at=datetime.now(UTC),
            chief_complaint=appointment.reason,
        )
        db.add(encounter)
        db.flush()
        appointment.encounter_id = encounter.id

        if not db.scalar(
            select(CareTeamLink.id).where(
                CareTeamLink.patient_id == appointment.patient_id,
                CareTeamLink.doctor_id == appointment.doctor_id,
            )
        ):
            db.add(
                CareTeamLink(
                    patient_id=appointment.patient_id, doctor_id=appointment.doctor_id
                )
            )

        record_event(
            db,
            patient_id=appointment.patient_id,
            kind=TimelineKind.CONSULTATION,
            occurred_at=appointment.scheduled_at,
            title=f"Consultation with {ser._doctor_name(db, appointment.doctor_id)}",
            summary=appointment.reason,
            doctor_id=appointment.doctor_id,
            hospital_id=appointment.hospital_id,
            ref_table="encounters",
            ref_id=encounter.id,
        )

    db.commit()
    db.refresh(appointment)
    return ser.appointment_out(db, appointment)


@router.get("/doctors/{doctor_id}/availability", response_model=list[datetime])
def read_taken_slots(
    doctor_id: int, db: DbSession, day: datetime | None = None
) -> list[datetime]:
    """Slots already booked for a doctor, so the client can grey them out."""
    query = select(Appointment.scheduled_at).where(
        Appointment.doctor_id == doctor_id,
        Appointment.status.in_([AppointmentStatus.REQUESTED, AppointmentStatus.CONFIRMED]),
    )
    if day:
        start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(hour=23, minute=59, second=59)
        query = query.where(Appointment.scheduled_at.between(start, end))
    return [row[0] for row in db.execute(query.order_by(Appointment.scheduled_at)).all()]


@router.delete("/{appointment_id}", response_model=Message)
def cancel_appointment(appointment_id: int, db: DbSession, user: CurrentUser) -> Message:
    appointment = _load_for_actor(db, appointment_id, user)
    if appointment.status not in CANCELLABLE:
        raise HTTPException(status_code=409, detail="This appointment can no longer be cancelled")
    appointment.status = AppointmentStatus.CANCELLED
    db.commit()
    return Message(detail="Appointment cancelled")

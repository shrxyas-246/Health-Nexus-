from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc, func, or_, select

from app.api.deps import CurrentDoctor, DbSession, doctor_can_access_patient
from app.api.v1 import serializers as ser
from app.core.enums import AppointmentStatus, ReviewTarget
from app.models import (
    Appointment,
    CareTeamLink,
    DoctorProfile,
    Encounter,
    LabReport,
    PatientProfile,
    User,
)
from app.schemas.common import Message
from app.schemas.patient import PatientOut
from app.schemas.providers import DoctorOut, DoctorUpdate, RatingBreakdown
from app.services.ratings import star_breakdown

router = APIRouter(prefix="/doctors", tags=["doctors"])


@router.get("", response_model=list[DoctorOut])
def list_doctors(
    db: DbSession,
    q: str | None = Query(None, description="Search by name or specialisation"),
    specialization: str | None = None,
    city: str | None = None,
    min_rating: float | None = None,
    max_fee: float | None = None,
    teleconsult: bool | None = None,
    limit: int = Query(30, le=100),
    offset: int = 0,
) -> list[DoctorOut]:
    query = select(DoctorProfile).join(User, User.id == DoctorProfile.user_id)
    if q:
        pattern = f"%{q}%"
        query = query.where(
            or_(User.full_name.ilike(pattern), DoctorProfile.specialization.ilike(pattern))
        )
    if specialization:
        query = query.where(DoctorProfile.specialization == specialization)
    if city:
        query = query.where(DoctorProfile.city == city)
    if min_rating is not None:
        query = query.where(DoctorProfile.rating_avg >= min_rating)
    if max_fee is not None:
        query = query.where(DoctorProfile.consultation_fee <= max_fee)
    if teleconsult is not None:
        query = query.where(DoctorProfile.accepts_teleconsult.is_(teleconsult))

    rows = db.scalars(
        query.order_by(desc(DoctorProfile.rating_avg)).limit(limit).offset(offset)
    ).all()
    return [ser.doctor_out(db, d) for d in rows]


@router.get("/specializations", response_model=list[str])
def list_specializations(db: DbSession) -> list[str]:
    return [
        row[0]
        for row in db.execute(
            select(DoctorProfile.specialization).distinct().order_by(DoctorProfile.specialization)
        ).all()
    ]


@router.get("/me", response_model=DoctorOut)
def read_my_doctor_profile(db: DbSession, doctor: CurrentDoctor) -> DoctorOut:
    return ser.doctor_out(db, doctor)


@router.patch("/me", response_model=DoctorOut)
def update_my_doctor_profile(
    payload: DoctorUpdate, db: DbSession, doctor: CurrentDoctor
) -> DoctorOut:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(doctor, field, value)
    db.commit()
    db.refresh(doctor)
    return ser.doctor_out(db, doctor)


@router.get("/me/patients", response_model=list[PatientOut])
def list_my_patients(db: DbSession, doctor: CurrentDoctor) -> list[PatientOut]:
    """Every patient this doctor has a care relationship with."""
    from_care_team = select(CareTeamLink.patient_id).where(
        CareTeamLink.doctor_id == doctor.id, CareTeamLink.active.is_(True)
    )
    from_encounters = select(Encounter.patient_id).where(Encounter.doctor_id == doctor.id)
    from_appointments = select(Appointment.patient_id).where(Appointment.doctor_id == doctor.id)

    patient_ids = {
        row[0]
        for row in db.execute(from_care_team.union(from_encounters, from_appointments)).all()
    }
    if not patient_ids:
        return []
    patients = db.scalars(select(PatientProfile).where(PatientProfile.id.in_(patient_ids))).all()
    return [ser.patient_out(db, p) for p in patients]


@router.get("/me/schedule", response_model=list)
def read_my_schedule(
    db: DbSession, doctor: CurrentDoctor, status_filter: str | None = Query(None, alias="status")
) -> list:
    query = select(Appointment).where(Appointment.doctor_id == doctor.id)
    if status_filter:
        query = query.where(Appointment.status == status_filter)
    else:
        query = query.where(
            Appointment.status.in_([AppointmentStatus.REQUESTED, AppointmentStatus.CONFIRMED])
        )
    rows = db.scalars(query.order_by(Appointment.scheduled_at)).all()
    return [ser.appointment_out(db, a) for a in rows]


@router.get("/me/inbox/reports", response_model=list)
def read_report_inbox(db: DbSession, doctor: CurrentDoctor, unreviewed_only: bool = True) -> list:
    """Reports patients have forwarded to this doctor for review."""
    query = select(LabReport).where(LabReport.shared_with_doctor_id == doctor.id)
    if unreviewed_only:
        query = query.where(LabReport.doctor_reviewed_at.is_(None))
    rows = db.scalars(query.order_by(desc(LabReport.issued_at))).all()
    return [ser.lab_report_out(db, r) for r in rows]


@router.get("/{doctor_id}", response_model=DoctorOut)
def read_doctor(doctor_id: int, db: DbSession) -> DoctorOut:
    doctor = db.get(DoctorProfile, doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return ser.doctor_out(db, doctor)


@router.get("/{doctor_id}/ratings", response_model=RatingBreakdown)
def read_doctor_ratings(doctor_id: int, db: DbSession) -> RatingBreakdown:
    doctor = db.get(DoctorProfile, doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return RatingBreakdown(
        average=doctor.rating_avg,
        count=doctor.rating_count,
        stars=star_breakdown(db, ReviewTarget.DOCTOR, doctor_id),
    )


@router.get("/patients/{patient_id}/prior-doctors", response_model=list[DoctorOut])
def list_prior_doctors(patient_id: int, db: DbSession, doctor: CurrentDoctor) -> list[DoctorOut]:
    """Other doctors who treated this patient, so the current one can consult them."""
    if not doctor_can_access_patient(db, doctor.id, patient_id):
        raise HTTPException(status_code=403, detail="No care relationship with this patient")

    rows = db.execute(
        select(Encounter.doctor_id, func.max(Encounter.started_at).label("last_seen"))
        .where(
            Encounter.patient_id == patient_id,
            Encounter.doctor_id.is_not(None),
            Encounter.doctor_id != doctor.id,
        )
        .group_by(Encounter.doctor_id)
        .order_by(desc("last_seen"))
    ).all()

    prior = [db.get(DoctorProfile, row[0]) for row in rows]
    return [ser.doctor_out(db, d) for d in prior if d]


@router.post("/me/patients/{patient_id}/care-team", response_model=Message)
def join_care_team(patient_id: int, db: DbSession, doctor: CurrentDoctor) -> Message:
    """Attach this doctor to a patient after a booked appointment establishes contact."""
    if not doctor_can_access_patient(db, doctor.id, patient_id):
        raise HTTPException(
            status_code=403,
            detail="An appointment or encounter with this patient is required first",
        )
    existing = db.scalar(
        select(CareTeamLink).where(
            CareTeamLink.patient_id == patient_id, CareTeamLink.doctor_id == doctor.id
        )
    )
    if existing:
        existing.active = True
    else:
        db.add(CareTeamLink(patient_id=patient_id, doctor_id=doctor.id))
    db.commit()
    return Message(detail="Added to care team")

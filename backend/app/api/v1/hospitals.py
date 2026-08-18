from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc, func, select

from app.api.deps import CurrentUser, DbSession
from app.api.v1 import serializers as ser
from app.core.enums import ReviewTarget
from app.models import (
    DoctorProfile,
    Encounter,
    Hospital,
    PatientProfile,
    Surgery,
)
from app.schemas.patient import PatientOut
from app.schemas.providers import DoctorOut, HospitalOut, RatingBreakdown
from app.services.ratings import star_breakdown

router = APIRouter(prefix="/hospitals", tags=["hospitals"])


def _owned_hospital(db, user) -> Hospital:
    hospital = db.scalar(select(Hospital).where(Hospital.owner_user_id == user.id))
    if not hospital:
        raise HTTPException(status_code=403, detail="This account does not operate a hospital")
    return hospital


@router.get("", response_model=list[HospitalOut])
def list_hospitals(
    db: DbSession,
    city: str | None = None,
    q: str | None = None,
    speciality: str | None = None,
    emergency_only: bool = False,
    limit: int = Query(30, le=100),
) -> list[Hospital]:
    query = select(Hospital)
    if city:
        query = query.where(Hospital.city == city)
    if q:
        query = query.where(Hospital.name.ilike(f"%{q}%"))
    if speciality:
        query = query.where(Hospital.specializations.ilike(f"%{speciality}%"))
    if emergency_only:
        query = query.where(Hospital.has_emergency.is_(True))
    return db.scalars(query.order_by(desc(Hospital.rating_avg)).limit(limit)).all()


@router.get("/me", response_model=HospitalOut)
def read_my_hospital(db: DbSession, user: CurrentUser) -> Hospital:
    return _owned_hospital(db, user)


@router.get("/me/doctors", response_model=list[DoctorOut])
def list_my_doctors(db: DbSession, user: CurrentUser) -> list[DoctorOut]:
    hospital = _owned_hospital(db, user)
    rows = db.scalars(select(DoctorProfile).where(DoctorProfile.hospital_id == hospital.id)).all()
    return [ser.doctor_out(db, d) for d in rows]


@router.get("/me/patients", response_model=list[PatientOut])
def list_my_patients(db: DbSession, user: CurrentUser, limit: int = Query(100, le=500)) -> list[PatientOut]:
    """Patients with a recorded encounter or surgery at this hospital."""
    hospital = _owned_hospital(db, user)

    from_encounters = select(Encounter.patient_id).where(Encounter.hospital_id == hospital.id)
    from_surgeries = select(Surgery.patient_id).where(Surgery.hospital_id == hospital.id)
    patient_ids = {row[0] for row in db.execute(from_encounters.union(from_surgeries)).all()}

    if not patient_ids:
        return []
    patients = db.scalars(
        select(PatientProfile).where(PatientProfile.id.in_(patient_ids)).limit(limit)
    ).all()
    return [ser.patient_out(db, p) for p in patients]


@router.get("/me/stats", response_model=dict)
def read_my_stats(db: DbSession, user: CurrentUser) -> dict:
    hospital = _owned_hospital(db, user)
    doctor_count = (
        db.query(DoctorProfile).filter(DoctorProfile.hospital_id == hospital.id).count()
    )
    encounter_count = db.query(Encounter).filter(Encounter.hospital_id == hospital.id).count()
    surgery_count = db.query(Surgery).filter(Surgery.hospital_id == hospital.id).count()
    unique_patients = db.scalar(
        select(func.count(func.distinct(Encounter.patient_id))).where(
            Encounter.hospital_id == hospital.id
        )
    )
    return {
        "doctors": doctor_count,
        "employees": hospital.employee_count,
        "beds": hospital.bed_count,
        "icu_beds": hospital.icu_bed_count,
        "encounters": encounter_count,
        "surgeries": surgery_count,
        "patients": int(unique_patients or 0),
        "rating_avg": hospital.rating_avg,
        "rating_count": hospital.rating_count,
    }


@router.get("/{hospital_id}", response_model=HospitalOut)
def read_hospital(hospital_id: int, db: DbSession) -> Hospital:
    hospital = db.get(Hospital, hospital_id)
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return hospital


@router.get("/{hospital_id}/doctors", response_model=list[DoctorOut])
def list_hospital_doctors(hospital_id: int, db: DbSession) -> list[DoctorOut]:
    rows = db.scalars(select(DoctorProfile).where(DoctorProfile.hospital_id == hospital_id)).all()
    return [ser.doctor_out(db, d) for d in rows]


@router.get("/{hospital_id}/ratings", response_model=RatingBreakdown)
def read_hospital_ratings(hospital_id: int, db: DbSession) -> RatingBreakdown:
    hospital = db.get(Hospital, hospital_id)
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return RatingBreakdown(
        average=hospital.rating_avg,
        count=hospital.rating_count,
        stars=star_breakdown(db, ReviewTarget.HOSPITAL, hospital_id),
    )

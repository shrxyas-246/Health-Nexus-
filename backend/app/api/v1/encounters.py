from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import desc, select

from app.api.deps import (
    CurrentDoctor,
    CurrentUser,
    DbSession,
    doctor_can_access_patient,
    resolve_patient_access,
)
from app.api.v1 import serializers as ser
from app.core.enums import TimelineKind
from app.models import CareTeamLink, Encounter
from app.schemas.clinical import EncounterCreate, EncounterOut, EncounterUpdate
from app.services.timeline import record_event

router = APIRouter(prefix="/encounters", tags=["encounters"])


@router.get("/patients/{patient_id}", response_model=list[EncounterOut])
def list_for_patient(patient_id: int, db: DbSession, user: CurrentUser) -> list[EncounterOut]:
    patient = resolve_patient_access(db, user, patient_id)
    rows = db.scalars(
        select(Encounter)
        .where(Encounter.patient_id == patient.id)
        .order_by(desc(Encounter.started_at))
    ).all()
    return [ser.encounter_out(db, e) for e in rows]


@router.post(
    "/patients/{patient_id}",
    response_model=EncounterOut,
    status_code=status.HTTP_201_CREATED,
)
def open_encounter(
    patient_id: int,
    payload: EncounterCreate,
    db: DbSession,
    user: CurrentUser,
    doctor: CurrentDoctor,
) -> EncounterOut:
    """Doctor records a visit directly (walk-ins, admissions)."""
    patient = resolve_patient_access(db, user, patient_id)

    encounter = Encounter(
        patient_id=patient.id,
        doctor_id=doctor.id,
        started_at=payload.started_at or datetime.now(UTC),
        **payload.model_dump(exclude={"started_at"}),
    )
    db.add(encounter)
    db.flush()

    if not db.scalar(
        select(CareTeamLink.id).where(
            CareTeamLink.patient_id == patient.id, CareTeamLink.doctor_id == doctor.id
        )
    ):
        db.add(CareTeamLink(patient_id=patient.id, doctor_id=doctor.id))

    kind = (
        TimelineKind.ADMISSION
        if encounter.kind == "admission"
        else TimelineKind.SURGERY
        if encounter.kind == "surgery"
        else TimelineKind.CONSULTATION
    )
    record_event(
        db,
        patient_id=patient.id,
        kind=kind,
        occurred_at=encounter.started_at,
        title=f"{encounter.kind.replace('_', ' ').title()} — {ser._doctor_name(db, doctor.id)}",
        summary=encounter.diagnosis or encounter.chief_complaint,
        doctor_id=doctor.id,
        hospital_id=encounter.hospital_id,
        condition_id=encounter.condition_id,
        ref_table="encounters",
        ref_id=encounter.id,
    )
    db.commit()
    db.refresh(encounter)
    return ser.encounter_out(db, encounter)


@router.patch("/{encounter_id}", response_model=EncounterOut)
def update_encounter(
    encounter_id: int, payload: EncounterUpdate, db: DbSession, doctor: CurrentDoctor
) -> EncounterOut:
    encounter = db.get(Encounter, encounter_id)
    if not encounter:
        raise HTTPException(status_code=404, detail="Encounter not found")
    if encounter.doctor_id != doctor.id and not doctor_can_access_patient(
        db, doctor.id, encounter.patient_id
    ):
        raise HTTPException(status_code=403, detail="No care relationship with this patient")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(encounter, field, value)
    db.commit()
    db.refresh(encounter)
    return ser.encounter_out(db, encounter)

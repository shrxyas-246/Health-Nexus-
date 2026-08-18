from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import desc, select

from app.api.deps import (
    AccessiblePatient,
    CurrentPatient,
    CurrentUser,
    DbSession,
    resolve_patient_access,
)
from app.api.v1 import serializers as ser
from app.core.enums import (
    AppointmentStatus,
    ConditionStatus,
    PrescriptionStatus,
    Role,
    TimelineKind,
)
from app.models import (
    Allergy,
    Appointment,
    Condition,
    Document,
    LabReport,
    PatientPolicy,
    PatientProfile,
    Prescription,
    PrescriptionItem,
    Surgery,
    TimelineEvent,
    User,
    VitalReading,
)
from app.schemas.common import Message
from app.schemas.patient import (
    ActivityItem,
    AllergyCreate,
    AllergyOut,
    ConditionCreate,
    ConditionOut,
    ConditionUpdate,
    DocumentCreate,
    DocumentOut,
    MetricTile,
    PatientOut,
    PatientSummary,
    PatientUpdate,
    SurgeryCreate,
    SurgeryOut,
    TimelineEventCreate,
    TimelineEventOut,
    TimelineEventUpdate,
    VitalCreate,
    VitalOut,
)
from app.services.timeline import record_event

router = APIRouter(prefix="/patients", tags=["patients"])


# --- current patient shortcuts -------------------------------------------------
# Registered before /{patient_id} so "me" is not parsed as an id.


@router.get("/me", response_model=PatientOut)
def read_my_profile(db: DbSession, patient: CurrentPatient) -> PatientOut:
    return ser.patient_out(db, patient)


@router.patch("/me", response_model=PatientOut)
def update_my_profile(payload: PatientUpdate, db: DbSession, patient: CurrentPatient) -> PatientOut:
    data = payload.model_dump(exclude_unset=True)
    full_name = data.pop("full_name", None)
    phone = data.pop("phone", None)

    if full_name or phone:
        user = db.get(User, patient.user_id)
        if full_name:
            user.full_name = full_name
        if phone:
            user.phone = phone

    for field, value in data.items():
        setattr(patient, field, value)
    db.commit()
    db.refresh(patient)
    return ser.patient_out(db, patient)


@router.get("/me/summary", response_model=PatientSummary)
def read_my_summary(db: DbSession, patient: CurrentPatient) -> PatientSummary:
    return _build_summary(db, patient)


# --- record access -------------------------------------------------------------


@router.get("/{patient_id}", response_model=PatientOut)
def read_patient(db: DbSession, patient: AccessiblePatient) -> PatientOut:
    return ser.patient_out(db, patient)


@router.get("/{patient_id}/summary", response_model=PatientSummary)
def read_summary(db: DbSession, patient: AccessiblePatient) -> PatientSummary:
    return _build_summary(db, patient)


def _build_summary(db, patient: PatientProfile) -> PatientSummary:
    """Assemble the patient home screen in a single response."""
    now = datetime.now(UTC)

    active_conditions = (
        db.query(Condition)
        .filter(Condition.patient_id == patient.id, Condition.status != ConditionStatus.RESOLVED)
        .count()
    )

    active_prescription = db.scalar(
        select(Prescription)
        .where(
            Prescription.patient_id == patient.id,
            Prescription.status == PrescriptionStatus.ACTIVE,
        )
        .order_by(desc(Prescription.issued_at))
    )
    active_medicines = (
        db.query(PrescriptionItem)
        .filter(PrescriptionItem.prescription_id == active_prescription.id)
        .count()
        if active_prescription
        else 0
    )

    upcoming = db.scalar(
        select(Appointment)
        .where(
            Appointment.patient_id == patient.id,
            Appointment.status.in_([AppointmentStatus.REQUESTED, AppointmentStatus.CONFIRMED]),
            Appointment.scheduled_at >= now,
        )
        .order_by(Appointment.scheduled_at)
    )

    policy = db.scalar(
        select(PatientPolicy).where(
            PatientPolicy.patient_id == patient.id, PatientPolicy.is_active.is_(True)
        )
    )
    insurance_status = "Active" if policy else "Not linked"

    last_visit = db.scalar(
        select(TimelineEvent)
        .where(
            TimelineEvent.patient_id == patient.id,
            TimelineEvent.kind == TimelineKind.CONSULTATION,
        )
        .order_by(desc(TimelineEvent.occurred_at))
    )

    allergy_count = db.query(Allergy).filter(Allergy.patient_id == patient.id).count()

    metrics = [
        MetricTile(
            key="bmi",
            label="BMI",
            value=str(patient.bmi) if patient.bmi else "—",
            tag=_bmi_tag(patient.bmi),
            tone=_bmi_tone(patient.bmi),
        ),
        MetricTile(
            key="conditions",
            label="Conditions",
            value=str(active_conditions),
            tag="Active" if active_conditions else "None",
            tone="warn" if active_conditions else "ok",
        ),
        MetricTile(
            key="medicines",
            label="Medicines",
            value=str(active_medicines),
            tag="Current",
            tone="ok",
        ),
        MetricTile(
            key="allergies",
            label="Allergies",
            value=str(allergy_count),
            tag="Known",
            tone="warn" if allergy_count else "ok",
        ),
        MetricTile(
            key="last_visit",
            label="Last visit",
            value=last_visit.occurred_at.strftime("%d %b") if last_visit else "—",
            tag="Recorded" if last_visit else "No visits",
            tone="ok",
        ),
        MetricTile(
            key="insurance",
            label="Insurance",
            value=insurance_status,
            tag="Verified" if policy else "Add cover",
            tone="ok" if policy else "neutral",
        ),
    ]

    recent_events = db.scalars(
        select(TimelineEvent)
        .where(TimelineEvent.patient_id == patient.id)
        .order_by(desc(TimelineEvent.occurred_at))
        .limit(6)
    ).all()
    activity = [
        ActivityItem(kind=e.kind, title=e.title, detail=e.summary, at=e.occurred_at)
        for e in recent_events
    ]

    return PatientSummary(
        patient=ser.patient_out(db, patient),
        metrics=metrics,
        activity=activity,
        active_conditions=active_conditions,
        active_medicines=active_medicines,
        upcoming_appointment_at=upcoming.scheduled_at if upcoming else None,
        insurance_status=insurance_status,
    )


def _bmi_tag(bmi: float | None) -> str:
    if bmi is None:
        return "Add height & weight"
    if bmi < 18.5:
        return "Underweight"
    if bmi < 25:
        return "Normal"
    if bmi < 30:
        return "Overweight"
    return "Obese"


def _bmi_tone(bmi: float | None) -> str:
    if bmi is None:
        return "neutral"
    if 18.5 <= bmi < 25:
        return "ok"
    if bmi < 30:
        return "warn"
    return "bad"


# --- timeline ------------------------------------------------------------------


@router.get("/{patient_id}/timeline", response_model=list[TimelineEventOut])
def read_timeline(
    db: DbSession,
    patient: AccessiblePatient,
    kind: str | None = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
) -> list[TimelineEventOut]:
    query = select(TimelineEvent).where(TimelineEvent.patient_id == patient.id)
    if kind:
        query = query.where(TimelineEvent.kind == kind)
    events = db.scalars(
        query.order_by(desc(TimelineEvent.occurred_at)).limit(limit).offset(offset)
    ).all()
    return [ser.timeline_out(db, e) for e in events]


@router.post(
    "/{patient_id}/timeline", response_model=TimelineEventOut, status_code=status.HTTP_201_CREATED
)
def add_timeline_event(
    payload: TimelineEventCreate, db: DbSession, patient: AccessiblePatient, user: CurrentUser
) -> TimelineEventOut:
    """Backfill a record from before the patient joined the app."""
    event = record_event(
        db,
        patient_id=patient.id,
        kind=payload.kind,
        occurred_at=payload.occurred_at,
        title=payload.title,
        summary=payload.summary,
        doctor_id=payload.doctor_id,
        hospital_id=payload.hospital_id,
        lab_id=payload.lab_id,
        condition_id=payload.condition_id,
        is_legacy=True,
        editable_by_patient=user.role == Role.PATIENT,
    )
    db.commit()
    db.refresh(event)
    return ser.timeline_out(db, event)


@router.patch("/{patient_id}/timeline/{event_id}", response_model=TimelineEventOut)
def edit_timeline_event(
    event_id: int,
    payload: TimelineEventUpdate,
    db: DbSession,
    patient: AccessiblePatient,
    user: CurrentUser,
) -> TimelineEventOut:
    event = db.get(TimelineEvent, event_id)
    if not event or event.patient_id != patient.id:
        raise HTTPException(status_code=404, detail="Timeline event not found")
    # App-generated entries stay immutable so the clinical record is trustworthy.
    if user.role == Role.PATIENT and not event.editable_by_patient:
        raise HTTPException(
            status_code=403,
            detail="Records created by a provider cannot be edited. Only entries you added yourself are editable.",
        )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(event, field, value)
    db.commit()
    db.refresh(event)
    return ser.timeline_out(db, event)


@router.delete("/{patient_id}/timeline/{event_id}", response_model=Message)
def delete_timeline_event(
    event_id: int, db: DbSession, patient: AccessiblePatient, user: CurrentUser
) -> Message:
    event = db.get(TimelineEvent, event_id)
    if not event or event.patient_id != patient.id:
        raise HTTPException(status_code=404, detail="Timeline event not found")
    if user.role == Role.PATIENT and not event.editable_by_patient:
        raise HTTPException(status_code=403, detail="Provider-created records cannot be deleted")
    db.delete(event)
    db.commit()
    return Message(detail="Timeline event removed")


# --- conditions ----------------------------------------------------------------


@router.get("/{patient_id}/conditions", response_model=list[ConditionOut])
def list_conditions(
    db: DbSession, patient: AccessiblePatient, status_filter: str | None = Query(None, alias="status")
) -> list[ConditionOut]:
    query = select(Condition).where(Condition.patient_id == patient.id)
    if status_filter:
        query = query.where(Condition.status == status_filter)
    rows = db.scalars(query.order_by(desc(Condition.onset_date))).all()
    return [ser.condition_out(db, c) for c in rows]


@router.post(
    "/{patient_id}/conditions", response_model=ConditionOut, status_code=status.HTTP_201_CREATED
)
def add_condition(
    payload: ConditionCreate, db: DbSession, patient: AccessiblePatient, user: CurrentUser
) -> ConditionOut:
    doctor_id = None
    if user.role == Role.DOCTOR and user.doctor:
        doctor_id = user.doctor.id

    condition = Condition(
        patient_id=patient.id,
        diagnosed_by_doctor_id=doctor_id,
        is_legacy=user.role == Role.PATIENT,
        **payload.model_dump(),
    )
    db.add(condition)
    db.flush()

    record_event(
        db,
        patient_id=patient.id,
        kind=TimelineKind.DIAGNOSIS,
        occurred_at=datetime.combine(
            payload.onset_date, datetime.min.time(), tzinfo=UTC
        )
        if payload.onset_date
        else datetime.now(UTC),
        title=f"Diagnosed: {condition.name}",
        summary=condition.notes,
        doctor_id=doctor_id,
        condition_id=condition.id,
        ref_table="conditions",
        ref_id=condition.id,
        is_legacy=condition.is_legacy,
        editable_by_patient=condition.is_legacy,
    )
    db.commit()
    db.refresh(condition)
    return ser.condition_out(db, condition)


@router.patch("/{patient_id}/conditions/{condition_id}", response_model=ConditionOut)
def update_condition(
    condition_id: int, payload: ConditionUpdate, db: DbSession, patient: AccessiblePatient
) -> ConditionOut:
    condition = db.get(Condition, condition_id)
    if not condition or condition.patient_id != patient.id:
        raise HTTPException(status_code=404, detail="Condition not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(condition, field, value)
    db.commit()
    db.refresh(condition)
    return ser.condition_out(db, condition)


# --- surgeries -----------------------------------------------------------------


@router.get("/{patient_id}/surgeries", response_model=list[SurgeryOut])
def list_surgeries(db: DbSession, patient: AccessiblePatient) -> list[SurgeryOut]:
    rows = db.scalars(
        select(Surgery).where(Surgery.patient_id == patient.id).order_by(desc(Surgery.performed_on))
    ).all()
    return [ser.surgery_out(db, s) for s in rows]


@router.post(
    "/{patient_id}/surgeries", response_model=SurgeryOut, status_code=status.HTTP_201_CREATED
)
def add_surgery(
    payload: SurgeryCreate, db: DbSession, patient: AccessiblePatient, user: CurrentUser
) -> SurgeryOut:
    surgery = Surgery(
        patient_id=patient.id, is_legacy=user.role == Role.PATIENT, **payload.model_dump()
    )
    db.add(surgery)
    db.flush()

    record_event(
        db,
        patient_id=patient.id,
        kind=TimelineKind.SURGERY,
        occurred_at=datetime.combine(payload.performed_on, datetime.min.time(), tzinfo=UTC),
        title=surgery.name,
        summary=surgery.outcome or surgery.notes,
        doctor_id=surgery.surgeon_doctor_id,
        hospital_id=surgery.hospital_id,
        ref_table="surgeries",
        ref_id=surgery.id,
        is_legacy=surgery.is_legacy,
        editable_by_patient=surgery.is_legacy,
    )
    db.commit()
    db.refresh(surgery)
    return ser.surgery_out(db, surgery)


# --- allergies -----------------------------------------------------------------


@router.get("/{patient_id}/allergies", response_model=list[AllergyOut])
def list_allergies(db: DbSession, patient: AccessiblePatient) -> list[Allergy]:
    return db.scalars(select(Allergy).where(Allergy.patient_id == patient.id)).all()


@router.post(
    "/{patient_id}/allergies", response_model=AllergyOut, status_code=status.HTTP_201_CREATED
)
def add_allergy(payload: AllergyCreate, db: DbSession, patient: AccessiblePatient) -> Allergy:
    allergy = Allergy(patient_id=patient.id, **payload.model_dump())
    db.add(allergy)
    db.commit()
    db.refresh(allergy)
    return allergy


@router.delete("/{patient_id}/allergies/{allergy_id}", response_model=Message)
def delete_allergy(allergy_id: int, db: DbSession, patient: AccessiblePatient) -> Message:
    allergy = db.get(Allergy, allergy_id)
    if not allergy or allergy.patient_id != patient.id:
        raise HTTPException(status_code=404, detail="Allergy not found")
    db.delete(allergy)
    db.commit()
    return Message(detail="Allergy removed")


# --- vitals --------------------------------------------------------------------


@router.get("/{patient_id}/vitals", response_model=list[VitalOut])
def list_vitals(
    db: DbSession,
    patient: AccessiblePatient,
    kind: str | None = None,
    days: int = Query(180, le=3650),
) -> list[VitalReading]:
    since = datetime.now(UTC) - timedelta(days=days)
    query = select(VitalReading).where(
        VitalReading.patient_id == patient.id, VitalReading.recorded_at >= since
    )
    if kind:
        query = query.where(VitalReading.kind == kind)
    return db.scalars(query.order_by(VitalReading.recorded_at)).all()


@router.post("/{patient_id}/vitals", response_model=VitalOut, status_code=status.HTTP_201_CREATED)
def add_vital(payload: VitalCreate, db: DbSession, patient: AccessiblePatient) -> VitalReading:
    reading = VitalReading(
        patient_id=patient.id,
        kind=payload.kind,
        value=payload.value,
        unit=payload.unit,
        recorded_at=payload.recorded_at or datetime.now(UTC),
        source=payload.source,
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return reading


# --- documents -----------------------------------------------------------------


@router.get("/{patient_id}/documents", response_model=list[DocumentOut])
def list_documents(
    db: DbSession, patient: AccessiblePatient, kind: str | None = None
) -> list[Document]:
    query = select(Document).where(Document.patient_id == patient.id)
    if kind:
        query = query.where(Document.kind == kind)
    return db.scalars(query.order_by(desc(Document.created_at))).all()


@router.post(
    "/{patient_id}/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED
)
def add_document(
    payload: DocumentCreate, db: DbSession, patient: AccessiblePatient, user: CurrentUser
) -> Document:
    document = Document(
        patient_id=patient.id, uploaded_by_user_id=user.id, **payload.model_dump()
    )
    db.add(document)
    db.flush()

    record_event(
        db,
        patient_id=patient.id,
        kind=TimelineKind.DOCUMENT,
        occurred_at=datetime.combine(payload.document_date, datetime.min.time(), tzinfo=UTC)
        if payload.document_date
        else datetime.now(UTC),
        title=document.title,
        summary=document.notes,
        ref_table="documents",
        ref_id=document.id,
        is_legacy=document.is_legacy,
        editable_by_patient=user.role == Role.PATIENT,
    )
    db.commit()
    db.refresh(document)
    return document


@router.delete("/{patient_id}/documents/{document_id}", response_model=Message)
def delete_document(document_id: int, db: DbSession, patient: AccessiblePatient) -> Message:
    document = db.get(Document, document_id)
    if not document or document.patient_id != patient.id:
        raise HTTPException(status_code=404, detail="Document not found")
    db.query(TimelineEvent).filter(
        TimelineEvent.ref_table == "documents", TimelineEvent.ref_id == document.id
    ).delete(synchronize_session=False)
    db.delete(document)
    db.commit()
    return Message(detail="Document removed")


# --- reports (read side lives here; labs router owns creation) -----------------


@router.get("/{patient_id}/reports", response_model=list)
def list_patient_reports(db: DbSession, patient: AccessiblePatient) -> list:
    reports = db.scalars(
        select(LabReport)
        .where(LabReport.patient_id == patient.id)
        .order_by(desc(LabReport.issued_at))
    ).all()
    return [ser.lab_report_out(db, r) for r in reports]


@router.get("/lookup/{medical_id}", response_model=PatientOut)
def lookup_by_medical_id(medical_id: str, db: DbSession, user: CurrentUser) -> PatientOut:
    """Find a patient by the ID printed on their card, then apply normal access rules."""
    patient = db.scalar(select(PatientProfile).where(PatientProfile.medical_id == medical_id))
    if not patient:
        raise HTTPException(status_code=404, detail="No patient with that medical ID")
    resolve_patient_access(db, user, patient.id)
    return ser.patient_out(db, patient)

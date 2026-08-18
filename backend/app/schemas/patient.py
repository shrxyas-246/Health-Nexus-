from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class AllergyOut(ORMModel):
    id: int
    substance: str
    reaction: str | None = None
    severity: str | None = None
    noted_on: date | None = None


class AllergyCreate(BaseModel):
    substance: str
    reaction: str | None = None
    severity: str | None = None
    noted_on: date | None = None


class PatientOut(ORMModel):
    id: int
    user_id: int
    medical_id: str
    full_name: str
    email: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None
    age: int | None = None
    gender: str | None = None
    blood_group: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    bmi: float | None = None
    address: str | None = None
    city: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    is_premium: bool
    is_verified: bool
    allergies: list[AllergyOut] = []


class PatientUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    blood_group: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    address: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None


class VitalOut(ORMModel):
    id: int
    kind: str
    value: float
    unit: str | None = None
    recorded_at: datetime
    source: str | None = None


class VitalCreate(BaseModel):
    kind: str
    value: float
    unit: str | None = None
    recorded_at: datetime | None = None
    source: str | None = "self"


class MetricTile(BaseModel):
    """One card in the patient's header metric strip."""

    key: str
    label: str
    value: str
    tag: str | None = None
    tone: str = "ok"  # ok | warn | bad | neutral


class ActivityItem(BaseModel):
    kind: str
    title: str
    detail: str | None = None
    at: datetime


class PatientSummary(BaseModel):
    """Everything the patient home screen needs, in one request."""

    patient: PatientOut
    metrics: list[MetricTile]
    activity: list[ActivityItem]
    active_conditions: int
    active_medicines: int
    upcoming_appointment_at: datetime | None = None
    insurance_status: str


class TimelineEventOut(ORMModel):
    id: int
    kind: str
    occurred_at: datetime
    title: str
    summary: str | None = None
    doctor_id: int | None = None
    doctor_name: str | None = None
    hospital_id: int | None = None
    hospital_name: str | None = None
    lab_id: int | None = None
    lab_name: str | None = None
    condition_id: int | None = None
    ref_table: str | None = None
    ref_id: int | None = None
    is_legacy: bool
    editable_by_patient: bool


class TimelineEventCreate(BaseModel):
    """Patients backfilling history from before they joined the app."""

    kind: str
    occurred_at: datetime
    title: str
    summary: str | None = None
    doctor_id: int | None = None
    hospital_id: int | None = None
    lab_id: int | None = None
    condition_id: int | None = None


class TimelineEventUpdate(BaseModel):
    kind: str | None = None
    occurred_at: datetime | None = None
    title: str | None = None
    summary: str | None = None


class ConditionOut(ORMModel):
    id: int
    name: str
    icd10_code: str | None = None
    category: str
    status: str
    severity: str | None = None
    onset_date: date | None = None
    resolved_date: date | None = None
    diagnosed_by_doctor_id: int | None = None
    doctor_name: str | None = None
    notes: str | None = None
    is_legacy: bool


class ConditionCreate(BaseModel):
    name: str
    icd10_code: str | None = None
    category: str = "acute"
    status: str = "active"
    severity: str | None = None
    onset_date: date | None = None
    notes: str | None = None


class ConditionUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    status: str | None = None
    severity: str | None = None
    resolved_date: date | None = None
    notes: str | None = None


class SurgeryOut(ORMModel):
    id: int
    name: str
    performed_on: date
    hospital_id: int | None = None
    hospital_name: str | None = None
    surgeon_doctor_id: int | None = None
    surgeon_name: str | None = None
    anaesthesia: str | None = None
    outcome: str | None = None
    notes: str | None = None


class SurgeryCreate(BaseModel):
    name: str
    performed_on: date
    hospital_id: int | None = None
    surgeon_doctor_id: int | None = None
    anaesthesia: str | None = None
    outcome: str | None = None
    notes: str | None = None


class DocumentOut(ORMModel):
    id: int
    kind: str
    title: str
    file_url: str
    mime_type: str | None = None
    size_bytes: int | None = None
    document_date: date | None = None
    notes: str | None = None
    is_legacy: bool
    created_at: datetime


class DocumentCreate(BaseModel):
    kind: str
    title: str
    file_url: str
    mime_type: str | None = None
    size_bytes: int | None = None
    document_date: date | None = None
    notes: str | None = None

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class PrescriptionItemOut(ORMModel):
    id: int
    medicine_name: str
    strength: str | None = None
    form: str | None = None
    purpose: str | None = None
    dosage: str | None = None
    frequency: str | None = None
    timing: str | None = None
    duration_days: int | None = None
    quantity: int | None = None
    instructions: str | None = None


class PrescriptionItemCreate(BaseModel):
    medicine_name: str
    strength: str | None = None
    form: str | None = None
    purpose: str | None = None
    dosage: str | None = None
    frequency: str | None = None
    timing: str | None = None
    duration_days: int | None = None
    quantity: int | None = None
    instructions: str | None = None


class TestRequestOut(ORMModel):
    id: int
    test_name: str
    reason: str | None = None
    urgency: str | None = None
    fulfilled: bool


class TestRequestCreate(BaseModel):
    test_name: str
    reason: str | None = None
    urgency: str | None = "routine"


class PrescriptionOut(ORMModel):
    id: int
    version: int
    status: str
    issued_at: datetime
    valid_until: date | None = None
    patient_id: int
    doctor_id: int | None = None
    doctor_name: str | None = None
    doctor_specialization: str | None = None
    encounter_id: int | None = None
    condition_id: int | None = None
    supersedes_id: int | None = None
    diagnosis_summary: str | None = None
    diet_advice: str | None = None
    lifestyle_advice: str | None = None
    change_note: str | None = None
    notes: str | None = None
    is_legacy: bool
    items: list[PrescriptionItemOut] = []
    test_requests: list[TestRequestOut] = []


class PrescriptionCreate(BaseModel):
    """Written by a doctor; the patient id comes from the URL."""

    encounter_id: int | None = None
    condition_id: int | None = None
    valid_until: date | None = None
    diagnosis_summary: str | None = None
    diet_advice: str | None = None
    lifestyle_advice: str | None = None
    notes: str | None = None
    items: list[PrescriptionItemCreate] = Field(default_factory=list)
    test_requests: list[TestRequestCreate] = Field(default_factory=list)


class PrescriptionRevise(PrescriptionCreate):
    """Supersede an existing prescription; the old version is retained."""

    change_note: str


class PrescriptionVersion(BaseModel):
    id: int
    version: int
    issued_at: datetime
    status: str
    change_note: str | None = None
    doctor_name: str | None = None


class EncounterOut(ORMModel):
    id: int
    kind: str
    started_at: datetime
    ended_at: datetime | None = None
    patient_id: int
    doctor_id: int | None = None
    doctor_name: str | None = None
    hospital_id: int | None = None
    hospital_name: str | None = None
    condition_id: int | None = None
    condition_name: str | None = None
    chief_complaint: str | None = None
    diagnosis: str | None = None
    clinical_notes: str | None = None
    follow_up_on: date | None = None
    is_legacy: bool


class EncounterCreate(BaseModel):
    kind: str = "consultation"
    started_at: datetime | None = None
    ended_at: datetime | None = None
    hospital_id: int | None = None
    condition_id: int | None = None
    chief_complaint: str | None = None
    diagnosis: str | None = None
    clinical_notes: str | None = None
    follow_up_on: date | None = None


class EncounterUpdate(BaseModel):
    ended_at: datetime | None = None
    diagnosis: str | None = None
    clinical_notes: str | None = None
    follow_up_on: date | None = None
    condition_id: int | None = None

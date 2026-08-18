from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    ConditionCategory,
    ConditionStatus,
    EncounterType,
    PrescriptionStatus,
)
from app.db.base import Base


class Condition(Base):
    """An illness episode — the spine that ties visits, drugs and reports together."""

    __tablename__ = "conditions"

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(180))
    icd10_code: Mapped[str | None] = mapped_column(String(16))
    category: Mapped[str] = mapped_column(String(20), default=ConditionCategory.ACUTE)
    status: Mapped[str] = mapped_column(String(20), default=ConditionStatus.ACTIVE, index=True)
    severity: Mapped[str | None] = mapped_column(String(20))
    onset_date: Mapped[date | None] = mapped_column(Date)
    resolved_date: Mapped[date | None] = mapped_column(Date)
    diagnosed_by_doctor_id: Mapped[int | None] = mapped_column(
        ForeignKey("doctor_profiles.id", ondelete="SET NULL")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    # Legacy rows are patient-entered history rather than app-generated records.
    is_legacy: Mapped[bool] = mapped_column(Boolean, default=False)

    encounters: Mapped[list[Encounter]] = relationship(back_populates="condition")


class Encounter(Base):
    """Any point of contact with a provider: consult, follow-up, admission, surgery."""

    __tablename__ = "encounters"

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True
    )
    doctor_id: Mapped[int | None] = mapped_column(
        ForeignKey("doctor_profiles.id", ondelete="SET NULL"), index=True
    )
    hospital_id: Mapped[int | None] = mapped_column(ForeignKey("hospitals.id", ondelete="SET NULL"))
    condition_id: Mapped[int | None] = mapped_column(
        ForeignKey("conditions.id", ondelete="SET NULL"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20), default=EncounterType.CONSULTATION)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    chief_complaint: Mapped[str | None] = mapped_column(String(400))
    diagnosis: Mapped[str | None] = mapped_column(String(400))
    clinical_notes: Mapped[str | None] = mapped_column(Text)
    follow_up_on: Mapped[date | None] = mapped_column(Date)
    is_legacy: Mapped[bool] = mapped_column(Boolean, default=False)

    condition: Mapped[Condition | None] = relationship(back_populates="encounters")
    prescriptions: Mapped[list[Prescription]] = relationship(back_populates="encounter")


class Surgery(Base):
    __tablename__ = "surgeries"

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True
    )
    encounter_id: Mapped[int | None] = mapped_column(ForeignKey("encounters.id", ondelete="SET NULL"))
    hospital_id: Mapped[int | None] = mapped_column(ForeignKey("hospitals.id", ondelete="SET NULL"))
    surgeon_doctor_id: Mapped[int | None] = mapped_column(
        ForeignKey("doctor_profiles.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(200))
    performed_on: Mapped[date] = mapped_column(Date, index=True)
    anaesthesia: Mapped[str | None] = mapped_column(String(60))
    outcome: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    is_legacy: Mapped[bool] = mapped_column(Boolean, default=False)


class Prescription(Base):
    """Immutable versions: editing creates a new row pointing at `supersedes_id`."""

    __tablename__ = "prescriptions"

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True
    )
    doctor_id: Mapped[int | None] = mapped_column(
        ForeignKey("doctor_profiles.id", ondelete="SET NULL"), index=True
    )
    encounter_id: Mapped[int | None] = mapped_column(
        ForeignKey("encounters.id", ondelete="SET NULL"), index=True
    )
    condition_id: Mapped[int | None] = mapped_column(ForeignKey("conditions.id", ondelete="SET NULL"))
    supersedes_id: Mapped[int | None] = mapped_column(
        ForeignKey("prescriptions.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default=PrescriptionStatus.ACTIVE, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    valid_until: Mapped[date | None] = mapped_column(Date)
    diagnosis_summary: Mapped[str | None] = mapped_column(String(400))
    diet_advice: Mapped[str | None] = mapped_column(Text)
    lifestyle_advice: Mapped[str | None] = mapped_column(Text)
    change_note: Mapped[str | None] = mapped_column(String(400))
    notes: Mapped[str | None] = mapped_column(Text)
    is_legacy: Mapped[bool] = mapped_column(Boolean, default=False)

    encounter: Mapped[Encounter | None] = relationship(back_populates="prescriptions")
    items: Mapped[list[PrescriptionItem]] = relationship(
        back_populates="prescription", cascade="all, delete-orphan"
    )
    test_requests: Mapped[list[TestRequest]] = relationship(
        back_populates="prescription", cascade="all, delete-orphan"
    )


class PrescriptionItem(Base):
    __tablename__ = "prescription_items"

    prescription_id: Mapped[int] = mapped_column(
        ForeignKey("prescriptions.id", ondelete="CASCADE"), index=True
    )
    medicine_name: Mapped[str] = mapped_column(String(180))
    strength: Mapped[str | None] = mapped_column(String(60))
    form: Mapped[str | None] = mapped_column(String(40))
    purpose: Mapped[str | None] = mapped_column(String(180))
    dosage: Mapped[str | None] = mapped_column(String(80))  # "1 tablet"
    frequency: Mapped[str | None] = mapped_column(String(80))  # "twice daily"
    timing: Mapped[str | None] = mapped_column(String(80))  # "after food"
    duration_days: Mapped[int | None] = mapped_column(Integer)
    quantity: Mapped[int | None] = mapped_column(Integer)
    instructions: Mapped[str | None] = mapped_column(String(300))


class TestRequest(Base):
    """A test the doctor asked for; becomes a LabOrder once the patient books a lab."""

    __tablename__ = "test_requests"

    prescription_id: Mapped[int | None] = mapped_column(
        ForeignKey("prescriptions.id", ondelete="CASCADE"), index=True
    )
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True
    )
    doctor_id: Mapped[int | None] = mapped_column(
        ForeignKey("doctor_profiles.id", ondelete="SET NULL")
    )
    test_name: Mapped[str] = mapped_column(String(180))
    reason: Mapped[str | None] = mapped_column(String(300))
    urgency: Mapped[str | None] = mapped_column(String(20))  # routine | urgent | stat
    fulfilled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    prescription: Mapped[Prescription | None] = relationship(back_populates="test_requests")


class VitalReading(Base):
    """Time series behind the snapshot charts and the ML feature store."""

    __tablename__ = "vital_readings"

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(30), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(20))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source: Mapped[str | None] = mapped_column(String(30))  # self | device | lab | clinic


class Document(Base):
    """Any uploaded file: old prescriptions, scans, bills, discharge summaries."""

    __tablename__ = "documents"

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True
    )
    uploaded_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(String(30), index=True)
    title: Mapped[str] = mapped_column(String(200))
    file_url: Mapped[str] = mapped_column(String(600))
    mime_type: Mapped[str | None] = mapped_column(String(80))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    document_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    is_legacy: Mapped[bool] = mapped_column(Boolean, default=True)


class TimelineEvent(Base):
    """Denormalised feed of the patient's medical life.

    Written by services whenever a clinical record is created so the timeline
    reads with one query, and so patient-uploaded historical entries sit
    alongside app-generated ones.
    """

    __tablename__ = "timeline_events"

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(30), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    title: Mapped[str] = mapped_column(String(220))
    summary: Mapped[str | None] = mapped_column(Text)
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("doctor_profiles.id", ondelete="SET NULL"))
    hospital_id: Mapped[int | None] = mapped_column(ForeignKey("hospitals.id", ondelete="SET NULL"))
    lab_id: Mapped[int | None] = mapped_column(ForeignKey("labs.id", ondelete="SET NULL"))
    condition_id: Mapped[int | None] = mapped_column(ForeignKey("conditions.id", ondelete="SET NULL"))
    # Pointer back to the row this event was generated from.
    ref_table: Mapped[str | None] = mapped_column(String(40))
    ref_id: Mapped[int | None] = mapped_column(Integer)
    is_legacy: Mapped[bool] = mapped_column(Boolean, default=False)
    editable_by_patient: Mapped[bool] = mapped_column(Boolean, default=False)

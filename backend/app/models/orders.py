from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    AppointmentMode,
    AppointmentStatus,
    LabOrderStatus,
    MedicineOrderStatus,
)
from app.db.base import Base


class Appointment(Base):
    __tablename__ = "appointments"

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True
    )
    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctor_profiles.id", ondelete="CASCADE"), index=True
    )
    hospital_id: Mapped[int | None] = mapped_column(ForeignKey("hospitals.id", ondelete="SET NULL"))
    encounter_id: Mapped[int | None] = mapped_column(ForeignKey("encounters.id", ondelete="SET NULL"))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=20)
    mode: Mapped[str] = mapped_column(String(20), default=AppointmentMode.IN_PERSON)
    status: Mapped[str] = mapped_column(String(20), default=AppointmentStatus.REQUESTED, index=True)
    reason: Mapped[str | None] = mapped_column(String(400))
    fee: Mapped[float] = mapped_column(Float, default=0)
    is_follow_up: Mapped[bool] = mapped_column(Boolean, default=False)
    cancelled_reason: Mapped[str | None] = mapped_column(String(300))


class LabOrder(Base):
    __tablename__ = "lab_orders"

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True
    )
    lab_id: Mapped[int] = mapped_column(ForeignKey("labs.id", ondelete="CASCADE"), index=True)
    doctor_id: Mapped[int | None] = mapped_column(
        ForeignKey("doctor_profiles.id", ondelete="SET NULL")
    )
    prescription_id: Mapped[int | None] = mapped_column(
        ForeignKey("prescriptions.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(30), default=LabOrderStatus.ORDERED, index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    home_collection: Mapped[bool] = mapped_column(Boolean, default=False)
    collection_address: Mapped[str | None] = mapped_column(String(400))
    subtotal: Mapped[float] = mapped_column(Float, default=0)
    discount: Mapped[float] = mapped_column(Float, default=0)
    total_amount: Mapped[float] = mapped_column(Float, default=0)
    notes: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list[LabOrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    reports: Mapped[list[LabReport]] = relationship(back_populates="order")


class LabOrderItem(Base):
    __tablename__ = "lab_order_items"

    lab_order_id: Mapped[int] = mapped_column(
        ForeignKey("lab_orders.id", ondelete="CASCADE"), index=True
    )
    lab_test_id: Mapped[int | None] = mapped_column(ForeignKey("lab_tests.id", ondelete="SET NULL"))
    test_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("test_requests.id", ondelete="SET NULL")
    )
    test_name: Mapped[str] = mapped_column(String(180))
    price: Mapped[float] = mapped_column(Float, default=0)

    order: Mapped[LabOrder] = relationship(back_populates="items")


class LabReport(Base):
    __tablename__ = "lab_reports"

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True
    )
    lab_id: Mapped[int | None] = mapped_column(ForeignKey("labs.id", ondelete="SET NULL"))
    lab_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("lab_orders.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    file_url: Mapped[str | None] = mapped_column(String(600))
    # Set when the report is pushed to the ordering doctor for review.
    shared_with_doctor_id: Mapped[int | None] = mapped_column(
        ForeignKey("doctor_profiles.id", ondelete="SET NULL"), index=True
    )
    doctor_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    doctor_remarks: Mapped[str | None] = mapped_column(Text)
    is_legacy: Mapped[bool] = mapped_column(Boolean, default=False)

    order: Mapped[LabOrder | None] = relationship(back_populates="reports")
    values: Mapped[list[LabReportValue]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )


class LabReportValue(Base):
    __tablename__ = "lab_report_values"

    report_id: Mapped[int] = mapped_column(
        ForeignKey("lab_reports.id", ondelete="CASCADE"), index=True
    )
    analyte: Mapped[str] = mapped_column(String(140))
    value: Mapped[float | None] = mapped_column(Float)
    text_value: Mapped[str | None] = mapped_column(String(140))
    unit: Mapped[str | None] = mapped_column(String(30))
    ref_low: Mapped[float | None] = mapped_column(Float)
    ref_high: Mapped[float | None] = mapped_column(Float)
    flag: Mapped[str | None] = mapped_column(String(20))  # low | normal | high | critical

    report: Mapped[LabReport] = relationship(back_populates="values")


class MedicineOrder(Base):
    __tablename__ = "medicine_orders"

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True
    )
    pharmacy_id: Mapped[int] = mapped_column(
        ForeignKey("pharmacies.id", ondelete="CASCADE"), index=True
    )
    prescription_id: Mapped[int | None] = mapped_column(
        ForeignKey("prescriptions.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(30), default=MedicineOrderStatus.PLACED, index=True)
    delivery: Mapped[bool] = mapped_column(Boolean, default=False)
    delivery_address: Mapped[str | None] = mapped_column(String(400))
    subtotal: Mapped[float] = mapped_column(Float, default=0)
    discount: Mapped[float] = mapped_column(Float, default=0)
    delivery_fee: Mapped[float] = mapped_column(Float, default=0)
    total_amount: Mapped[float] = mapped_column(Float, default=0)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(String(300))

    items: Mapped[list[MedicineOrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class MedicineOrderItem(Base):
    __tablename__ = "medicine_order_items"

    medicine_order_id: Mapped[int] = mapped_column(
        ForeignKey("medicine_orders.id", ondelete="CASCADE"), index=True
    )
    pharmacy_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("pharmacy_items.id", ondelete="SET NULL")
    )
    prescription_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("prescription_items.id", ondelete="SET NULL")
    )
    medicine_name: Mapped[str] = mapped_column(String(180))
    strength: Mapped[str | None] = mapped_column(String(60))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Float, default=0)
    line_total: Mapped[float] = mapped_column(Float, default=0)
    substituted_with: Mapped[str | None] = mapped_column(String(180))

    order: Mapped[MedicineOrder] = relationship(back_populates="items")


class EmergencyRequest(Base):
    """One-tap ambulance dispatch; the patient record is pushed ahead of arrival."""

    __tablename__ = "emergency_requests"

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True
    )
    hospital_id: Mapped[int | None] = mapped_column(ForeignKey("hospitals.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(30), index=True)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    address_hint: Mapped[str | None] = mapped_column(String(400))
    complaint: Mapped[str | None] = mapped_column(String(400))
    ambulance_eta_minutes: Mapped[int | None] = mapped_column(Integer)
    ambulance_ref: Mapped[str | None] = mapped_column(String(60))
    record_pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paperwork_deferred: Mapped[bool] = mapped_column(Boolean, default=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

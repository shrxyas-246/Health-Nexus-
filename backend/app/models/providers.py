from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ProviderMixin:
    """Fields shared by every physical provider (hospital, lab, pharmacy)."""

    name: Mapped[str] = mapped_column(String(180), index=True)
    address: Mapped[str | None] = mapped_column(String(400))
    city: Mapped[str | None] = mapped_column(String(80), index=True)
    phone: Mapped[str | None] = mapped_column(String(20))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    rating_avg: Mapped[float] = mapped_column(Float, default=0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)


class Hospital(ProviderMixin, Base):
    __tablename__ = "hospitals"

    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    kind: Mapped[str | None] = mapped_column(String(40))  # multi_speciality | clinic | nursing_home
    specializations: Mapped[str | None] = mapped_column(Text)  # comma separated
    services: Mapped[str | None] = mapped_column(Text)  # comma separated
    bed_count: Mapped[int] = mapped_column(Integer, default=0)
    icu_bed_count: Mapped[int] = mapped_column(Integer, default=0)
    doctor_count: Mapped[int] = mapped_column(Integer, default=0)
    employee_count: Mapped[int] = mapped_column(Integer, default=0)
    has_emergency: Mapped[bool] = mapped_column(Boolean, default=True)
    has_ambulance: Mapped[bool] = mapped_column(Boolean, default=True)
    avg_consultation_fee: Mapped[float] = mapped_column(Float, default=0)
    about: Mapped[str | None] = mapped_column(Text)
    # Outcome signals the recommender weighs for severe or surgical cases.
    surgery_success_rate: Mapped[float | None] = mapped_column(Float)
    complex_cases_handled: Mapped[int] = mapped_column(Integer, default=0)
    accreditation: Mapped[str | None] = mapped_column(String(120))  # NABH, JCI


class Lab(ProviderMixin, Base):
    __tablename__ = "labs"

    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    accreditation: Mapped[str | None] = mapped_column(String(120))  # NABL, CAP, ...
    home_collection: Mapped[bool] = mapped_column(Boolean, default=False)
    home_collection_fee: Mapped[float] = mapped_column(Float, default=0)
    opens_at: Mapped[str | None] = mapped_column(String(8))
    closes_at: Mapped[str | None] = mapped_column(String(8))
    about: Mapped[str | None] = mapped_column(Text)

    tests: Mapped[list[LabTest]] = relationship(
        back_populates="lab", cascade="all, delete-orphan"
    )


class LabTest(Base):
    """A test a specific lab offers, at that lab's price."""

    __tablename__ = "lab_tests"

    lab_id: Mapped[int] = mapped_column(ForeignKey("labs.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    code: Mapped[str | None] = mapped_column(String(40), index=True)
    category: Mapped[str | None] = mapped_column(String(80))
    price: Mapped[float] = mapped_column(Float, default=0)
    discount_percent: Mapped[float] = mapped_column(Float, default=0)
    turnaround_hours: Mapped[int] = mapped_column(Integer, default=24)
    fasting_required: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    lab: Mapped[Lab] = relationship(back_populates="tests")

    @property
    def effective_price(self) -> float:
        return round(self.price * (1 - self.discount_percent / 100), 2)


class Pharmacy(ProviderMixin, Base):
    __tablename__ = "pharmacies"

    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    licence_no: Mapped[str | None] = mapped_column(String(64))
    delivers: Mapped[bool] = mapped_column(Boolean, default=True)
    delivery_fee: Mapped[float] = mapped_column(Float, default=0)
    avg_delivery_minutes: Mapped[int] = mapped_column(Integer, default=60)
    is_24x7: Mapped[bool] = mapped_column(Boolean, default=False)

    inventory: Mapped[list[PharmacyItem]] = relationship(
        back_populates="pharmacy", cascade="all, delete-orphan"
    )


class PharmacyItem(Base):
    __tablename__ = "pharmacy_items"

    pharmacy_id: Mapped[int] = mapped_column(
        ForeignKey("pharmacies.id", ondelete="CASCADE"), index=True
    )
    medicine_name: Mapped[str] = mapped_column(String(180), index=True)
    strength: Mapped[str | None] = mapped_column(String(60))
    form: Mapped[str | None] = mapped_column(String(40))  # tablet | capsule | syrup | injection
    manufacturer: Mapped[str | None] = mapped_column(String(120))
    mrp: Mapped[float] = mapped_column(Float, default=0)
    selling_price: Mapped[float] = mapped_column(Float, default=0)
    stock_qty: Mapped[int] = mapped_column(Integer, default=0)
    requires_prescription: Mapped[bool] = mapped_column(Boolean, default=True)

    pharmacy: Mapped[Pharmacy] = relationship(back_populates="inventory")

    @property
    def in_stock(self) -> bool:
        return self.stock_qty > 0


class Insurer(Base):
    __tablename__ = "insurers"

    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(180), index=True)
    irdai_reg_no: Mapped[str | None] = mapped_column(String(64))
    support_phone: Mapped[str | None] = mapped_column(String(20))
    claim_settlement_ratio: Mapped[float] = mapped_column(Float, default=0)
    avg_settlement_days: Mapped[int] = mapped_column(Integer, default=14)
    rating_avg: Mapped[float] = mapped_column(Float, default=0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    about: Mapped[str | None] = mapped_column(Text)

    plans: Mapped[list[InsurancePlan]] = relationship(
        back_populates="insurer", cascade="all, delete-orphan"
    )


class InsurancePlan(Base):
    """A product in an insurer's catalogue, before any patient buys it."""

    __tablename__ = "insurance_plans"

    insurer_id: Mapped[int] = mapped_column(ForeignKey("insurers.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    cover_amount: Mapped[float] = mapped_column(Float, default=0)
    annual_premium: Mapped[float] = mapped_column(Float, default=0)
    room_rent_limit: Mapped[float | None] = mapped_column(Float)
    waiting_period_months: Mapped[int] = mapped_column(Integer, default=0)
    covers_pre_existing: Mapped[bool] = mapped_column(Boolean, default=False)
    covers_daycare: Mapped[bool] = mapped_column(Boolean, default=True)
    covers_opd: Mapped[bool] = mapped_column(Boolean, default=False)
    network_hospital_count: Mapped[int] = mapped_column(Integer, default=0)
    highlights: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    insurer: Mapped[Insurer] = relationship(back_populates="plans")

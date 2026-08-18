from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import Role
from app.db.base import Base


class User(Base):
    """Single login table for every actor in the ecosystem; `role` fans out to a profile."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), index=True, default=Role.PATIENT)
    full_name: Mapped[str] = mapped_column(String(160))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    patient: Mapped[PatientProfile | None] = relationship(back_populates="user", uselist=False)
    doctor: Mapped[DoctorProfile | None] = relationship(back_populates="user", uselist=False)


class PatientProfile(Base):
    __tablename__ = "patient_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    medical_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(20))
    blood_group: Mapped[str | None] = mapped_column(String(8))
    height_cm: Mapped[float | None] = mapped_column(Float)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    address: Mapped[str | None] = mapped_column(String(400))
    city: Mapped[str | None] = mapped_column(String(80), index=True)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(120))
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(20))
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="patient")
    allergies: Mapped[list[Allergy]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )

    @property
    def bmi(self) -> float | None:
        if not self.height_cm or not self.weight_kg:
            return None
        metres = self.height_cm / 100
        return round(self.weight_kg / (metres * metres), 1)


class Allergy(Base):
    __tablename__ = "allergies"

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True
    )
    substance: Mapped[str] = mapped_column(String(120))
    reaction: Mapped[str | None] = mapped_column(String(200))
    severity: Mapped[str | None] = mapped_column(String(20))  # mild | moderate | severe
    noted_on: Mapped[date | None] = mapped_column(Date)

    patient: Mapped[PatientProfile] = relationship(back_populates="allergies")


class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    registration_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    specialization: Mapped[str] = mapped_column(String(120), index=True)
    qualifications: Mapped[str | None] = mapped_column(String(240))
    years_experience: Mapped[int] = mapped_column(Integer, default=0)
    hospital_id: Mapped[int | None] = mapped_column(
        ForeignKey("hospitals.id", ondelete="SET NULL"), index=True
    )
    consultation_fee: Mapped[float] = mapped_column(Float, default=0)
    languages: Mapped[str | None] = mapped_column(String(200))
    bio: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(80), index=True)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    accepts_teleconsult: Mapped[bool] = mapped_column(Boolean, default=True)
    rating_avg: Mapped[float] = mapped_column(Float, default=0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    # Outcome signals the recommender weighs for severe or surgical cases.
    procedures_performed: Mapped[int] = mapped_column(Integer, default=0)
    complex_case_success_rate: Mapped[float | None] = mapped_column(Float)
    treats_severity: Mapped[str | None] = mapped_column(String(40))  # mild,moderate,severe

    user: Mapped[User] = relationship(back_populates="doctor")
    hospital: Mapped["Hospital | None"] = relationship()  # noqa: F821


class CareTeamLink(Base):
    """Which doctors currently have standing access to a patient's record."""

    __tablename__ = "care_team_links"
    __table_args__ = (UniqueConstraint("patient_id", "doctor_id", name="uq_care_team_pair"),)

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True
    )
    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctor_profiles.id", ondelete="CASCADE"), index=True
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

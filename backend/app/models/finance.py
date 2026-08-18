from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ClaimStatus, PaymentStatus
from app.db.base import Base


class Payment(Base):
    """Every rupee routed through the app, with the platform's cut recorded on the row."""

    __tablename__ = "payments"

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(30), index=True)
    ref_table: Mapped[str | None] = mapped_column(String(40))
    ref_id: Mapped[int | None] = mapped_column(Integer)
    payee_kind: Mapped[str | None] = mapped_column(String(20))  # doctor | hospital | lab | pharmacy
    payee_id: Mapped[int | None] = mapped_column(Integer)
    amount: Mapped[float] = mapped_column(Float, default=0)
    commission_rate: Mapped[float] = mapped_column(Float, default=0)
    commission_amount: Mapped[float] = mapped_column(Float, default=0)
    payout_amount: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(20), default=PaymentStatus.PENDING, index=True)
    method: Mapped[str | None] = mapped_column(String(30))  # upi | card | netbanking | wallet
    gateway_ref: Mapped[str | None] = mapped_column(String(80))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    description: Mapped[str | None] = mapped_column(String(300))
    # Set once this bill has been attached to an insurance claim.
    claim_id: Mapped[int | None] = mapped_column(
        ForeignKey("insurance_claims.id", ondelete="SET NULL")
    )


class PatientPolicy(Base):
    """A plan a specific patient holds, with live cover utilisation."""

    __tablename__ = "patient_policies"

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True
    )
    insurer_id: Mapped[int] = mapped_column(ForeignKey("insurers.id", ondelete="CASCADE"))
    plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("insurance_plans.id", ondelete="SET NULL")
    )
    policy_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    holder_name: Mapped[str | None] = mapped_column(String(160))
    cover_amount: Mapped[float] = mapped_column(Float, default=0)
    used_amount: Mapped[float] = mapped_column(Float, default=0)
    annual_premium: Mapped[float] = mapped_column(Float, default=0)
    starts_on: Mapped[date | None] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    claims: Mapped[list[InsuranceClaim]] = relationship(back_populates="policy")

    @property
    def remaining_amount(self) -> float:
        return max(self.cover_amount - self.used_amount, 0)

    @property
    def used_percent(self) -> float:
        return round(self.used_amount / self.cover_amount * 100, 1) if self.cover_amount else 0.0


class InsuranceClaim(Base):
    __tablename__ = "insurance_claims"

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True
    )
    patient_policy_id: Mapped[int] = mapped_column(
        ForeignKey("patient_policies.id", ondelete="CASCADE"), index=True
    )
    claim_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default=ClaimStatus.DRAFT, index=True)
    treatment_type: Mapped[str | None] = mapped_column(String(60))  # cashless | reimbursement
    hospital_id: Mapped[int | None] = mapped_column(ForeignKey("hospitals.id", ondelete="SET NULL"))
    encounter_id: Mapped[int | None] = mapped_column(ForeignKey("encounters.id", ondelete="SET NULL"))
    amount_claimed: Mapped[float] = mapped_column(Float, default=0)
    amount_approved: Mapped[float] = mapped_column(Float, default=0)
    incident_date: Mapped[date | None] = mapped_column(Date)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(String(400))
    description: Mapped[str | None] = mapped_column(Text)

    policy: Mapped[PatientPolicy] = relationship(back_populates="claims")
    documents: Mapped[list[ClaimDocument]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )


class ClaimDocument(Base):
    __tablename__ = "claim_documents"

    claim_id: Mapped[int] = mapped_column(
        ForeignKey("insurance_claims.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    label: Mapped[str] = mapped_column(String(160))
    file_url: Mapped[str | None] = mapped_column(String(600))

    claim: Mapped[InsuranceClaim] = relationship(back_populates="documents")


class Subscription(Base):
    """Premium tier that unlocks the ML recommendation surfaces."""

    __tablename__ = "subscriptions"

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True
    )
    tier: Mapped[str] = mapped_column(String(20), default="plus")
    price: Mapped[float] = mapped_column(Float, default=0)
    billing_cycle: Mapped[str] = mapped_column(String(20), default="monthly")
    started_on: Mapped[date | None] = mapped_column(Date)
    renews_on: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    seats: Mapped[int] = mapped_column(Integer, default=1)

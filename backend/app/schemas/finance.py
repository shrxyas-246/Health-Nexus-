from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class PaymentOut(ORMModel):
    id: int
    patient_id: int
    purpose: str
    ref_table: str | None = None
    ref_id: int | None = None
    payee_kind: str | None = None
    payee_id: int | None = None
    payee_name: str | None = None
    amount: float
    commission_rate: float
    commission_amount: float
    payout_amount: float
    status: str
    method: str | None = None
    gateway_ref: str | None = None
    paid_at: datetime | None = None
    description: str | None = None
    claim_id: int | None = None
    created_at: datetime


class PaymentCreate(BaseModel):
    purpose: str
    ref_table: str | None = None
    ref_id: int | None = None
    amount: float
    method: str = "upi"
    description: str | None = None


class BillingSummary(BaseModel):
    total_spent: float
    spent_this_year: float
    pending_amount: float
    reimbursed_amount: float
    by_purpose: dict[str, float]
    recent: list[PaymentOut]


class PatientPolicyOut(ORMModel):
    id: int
    patient_id: int
    insurer_id: int
    insurer_name: str | None = None
    plan_id: int | None = None
    plan_name: str | None = None
    policy_number: str
    holder_name: str | None = None
    cover_amount: float
    used_amount: float
    remaining_amount: float
    used_percent: float
    annual_premium: float
    starts_on: date | None = None
    ends_on: date | None = None
    is_active: bool


class ClaimDocumentOut(ORMModel):
    id: int
    label: str
    file_url: str | None = None
    document_id: int | None = None


class ClaimDocumentCreate(BaseModel):
    label: str
    file_url: str | None = None
    document_id: int | None = None


class InsuranceClaimOut(ORMModel):
    id: int
    patient_id: int
    patient_name: str | None = None
    patient_policy_id: int
    policy_number: str | None = None
    insurer_name: str | None = None
    claim_number: str
    status: str
    treatment_type: str | None = None
    hospital_id: int | None = None
    hospital_name: str | None = None
    encounter_id: int | None = None
    amount_claimed: float
    amount_approved: float
    incident_date: date | None = None
    submitted_at: datetime | None = None
    decided_at: datetime | None = None
    settled_at: datetime | None = None
    reviewer_note: str | None = None
    rejection_reason: str | None = None
    description: str | None = None
    created_at: datetime
    documents: list[ClaimDocumentOut] = []


class InsuranceClaimCreate(BaseModel):
    patient_policy_id: int
    amount_claimed: float
    treatment_type: str = "reimbursement"
    hospital_id: int | None = None
    encounter_id: int | None = None
    incident_date: date | None = None
    description: str | None = None
    documents: list[ClaimDocumentCreate] = Field(default_factory=list)
    # Bills already paid through the app that this claim covers.
    payment_ids: list[int] = Field(default_factory=list)


class ClaimDecision(BaseModel):
    """Insurer-side action on a submitted claim."""

    status: str  # under_review | approved | partially_approved | rejected | settled
    amount_approved: float | None = None
    reviewer_note: str | None = None
    rejection_reason: str | None = None


class SubscriptionOut(ORMModel):
    id: int
    patient_id: int
    tier: str
    price: float
    billing_cycle: str
    started_on: date | None = None
    renews_on: date | None = None
    is_active: bool
    auto_renew: bool


class SubscribeRequest(BaseModel):
    tier: str = "plus"
    billing_cycle: str = "monthly"

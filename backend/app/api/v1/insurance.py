import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import desc, select

from app.api.deps import CurrentPatient, CurrentUser, DbSession
from app.api.v1 import serializers as ser
from app.core.enums import ClaimStatus, Role
from app.models import (
    ClaimDocument,
    InsuranceClaim,
    InsurancePlan,
    Insurer,
    Notification,
    PatientPolicy,
    PatientProfile,
    Payment,
)
from app.schemas.common import Message
from app.schemas.finance import (
    ClaimDecision,
    InsuranceClaimCreate,
    InsuranceClaimOut,
    PatientPolicyOut,
)
from app.schemas.providers import InsurancePlanOut, InsurerOut

router = APIRouter(prefix="/insurance", tags=["insurance"])

# Statuses an insurer may still act on.
OPEN_STATUSES = [ClaimStatus.SUBMITTED, ClaimStatus.UNDER_REVIEW]
DECIDED_STATUSES = {
    ClaimStatus.APPROVED,
    ClaimStatus.PARTIALLY_APPROVED,
    ClaimStatus.REJECTED,
    ClaimStatus.SETTLED,
}


def _owned_insurer(db, user) -> Insurer:
    insurer = db.scalar(select(Insurer).where(Insurer.owner_user_id == user.id))
    if not insurer:
        raise HTTPException(status_code=403, detail="This account does not operate an insurer")
    return insurer


# --- catalogue -----------------------------------------------------------------


@router.get("/insurers", response_model=list[InsurerOut])
def list_insurers(db: DbSession) -> list[Insurer]:
    return db.scalars(select(Insurer).order_by(desc(Insurer.claim_settlement_ratio))).all()


@router.get("/plans", response_model=list[InsurancePlanOut])
def list_plans(
    db: DbSession,
    insurer_id: int | None = None,
    max_premium: float | None = None,
    min_cover: float | None = None,
    covers_pre_existing: bool | None = None,
) -> list[InsurancePlanOut]:
    query = select(InsurancePlan).where(InsurancePlan.is_active.is_(True))
    if insurer_id:
        query = query.where(InsurancePlan.insurer_id == insurer_id)
    if max_premium is not None:
        query = query.where(InsurancePlan.annual_premium <= max_premium)
    if min_cover is not None:
        query = query.where(InsurancePlan.cover_amount >= min_cover)
    if covers_pre_existing is not None:
        query = query.where(InsurancePlan.covers_pre_existing.is_(covers_pre_existing))
    rows = db.scalars(query.order_by(InsurancePlan.annual_premium)).all()
    return [ser.plan_out(db, p) for p in rows]


# --- the patient's cover -------------------------------------------------------


@router.get("/policies/me", response_model=list[PatientPolicyOut])
def list_my_policies(db: DbSession, patient: CurrentPatient) -> list[PatientPolicyOut]:
    rows = db.scalars(
        select(PatientPolicy)
        .where(PatientPolicy.patient_id == patient.id)
        .order_by(desc(PatientPolicy.is_active), desc(PatientPolicy.ends_on))
    ).all()
    return [ser.policy_out(db, p) for p in rows]


@router.post("/policies/link", response_model=PatientPolicyOut, status_code=status.HTTP_201_CREATED)
def link_policy(
    db: DbSession,
    patient: CurrentPatient,
    policy_number: str,
    insurer_id: int,
    plan_id: int | None = None,
    cover_amount: float = 0,
) -> PatientPolicyOut:
    """Attach an existing policy the patient already holds."""
    if db.scalar(select(PatientPolicy.id).where(PatientPolicy.policy_number == policy_number)):
        raise HTTPException(status_code=409, detail="That policy number is already linked")

    plan = db.get(InsurancePlan, plan_id) if plan_id else None
    policy = PatientPolicy(
        patient_id=patient.id,
        insurer_id=insurer_id,
        plan_id=plan_id,
        policy_number=policy_number,
        cover_amount=cover_amount or (plan.cover_amount if plan else 0),
        annual_premium=plan.annual_premium if plan else 0,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return ser.policy_out(db, policy)


# --- claims --------------------------------------------------------------------


@router.post("/claims", response_model=InsuranceClaimOut, status_code=status.HTTP_201_CREATED)
def file_claim(
    payload: InsuranceClaimCreate, db: DbSession, patient: CurrentPatient
) -> InsuranceClaimOut:
    """File a reimbursement claim against a linked policy."""
    policy = db.get(PatientPolicy, payload.patient_policy_id)
    if not policy or policy.patient_id != patient.id:
        raise HTTPException(status_code=404, detail="Policy not found")
    if not policy.is_active:
        raise HTTPException(status_code=409, detail="This policy is no longer active")
    if payload.amount_claimed > policy.remaining_amount:
        raise HTTPException(
            status_code=409,
            detail=f"Claim exceeds remaining cover of ₹{policy.remaining_amount:,.0f}",
        )

    claim = InsuranceClaim(
        patient_id=patient.id,
        patient_policy_id=policy.id,
        claim_number=f"CLM-{secrets.randbelow(900000) + 100000}",
        status=ClaimStatus.SUBMITTED,
        treatment_type=payload.treatment_type,
        hospital_id=payload.hospital_id,
        encounter_id=payload.encounter_id,
        amount_claimed=payload.amount_claimed,
        amount_approved=0,
        incident_date=payload.incident_date,
        description=payload.description,
        submitted_at=datetime.now(UTC),
    )
    db.add(claim)
    db.flush()

    for document in payload.documents:
        db.add(ClaimDocument(claim_id=claim.id, **document.model_dump()))

    # Tie already-paid bills to the claim so the insurer sees the evidence.
    for payment_id in payload.payment_ids:
        payment = db.get(Payment, payment_id)
        if not payment or payment.patient_id != patient.id:
            raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")
        payment.claim_id = claim.id

    insurer = db.get(Insurer, policy.insurer_id)
    if insurer and insurer.owner_user_id:
        db.add(
            Notification(
                user_id=insurer.owner_user_id,
                kind="claim_submitted",
                title=f"New claim {claim.claim_number}",
                body=f"₹{claim.amount_claimed:,.0f} claimed on policy {policy.policy_number}",
                link=f"/claims/{claim.id}",
            )
        )

    db.commit()
    db.refresh(claim)
    return ser.claim_out(db, claim)


@router.get("/claims/me", response_model=list[InsuranceClaimOut])
def list_my_claims(
    db: DbSession, patient: CurrentPatient, status_filter: str | None = Query(None, alias="status")
) -> list[InsuranceClaimOut]:
    query = select(InsuranceClaim).where(InsuranceClaim.patient_id == patient.id)
    if status_filter:
        query = query.where(InsuranceClaim.status == status_filter)
    rows = db.scalars(query.order_by(desc(InsuranceClaim.created_at))).all()
    return [ser.claim_out(db, c) for c in rows]


@router.get("/claims/incoming", response_model=list[InsuranceClaimOut])
def list_incoming_claims(
    db: DbSession, user: CurrentUser, status_filter: str | None = Query(None, alias="status")
) -> list[InsuranceClaimOut]:
    """Insurer-side queue of claims to review."""
    insurer = _owned_insurer(db, user)
    policy_ids = select(PatientPolicy.id).where(PatientPolicy.insurer_id == insurer.id)

    query = select(InsuranceClaim).where(InsuranceClaim.patient_policy_id.in_(policy_ids))
    if status_filter:
        query = query.where(InsuranceClaim.status == status_filter)
    else:
        query = query.where(InsuranceClaim.status.in_(OPEN_STATUSES))
    rows = db.scalars(query.order_by(InsuranceClaim.submitted_at)).all()
    return [ser.claim_out(db, c) for c in rows]


@router.get("/claims/{claim_id}", response_model=InsuranceClaimOut)
def read_claim(claim_id: int, db: DbSession, user: CurrentUser) -> InsuranceClaimOut:
    claim = db.get(InsuranceClaim, claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if user.role == Role.PATIENT:
        if not user.patient or claim.patient_id != user.patient.id:
            raise HTTPException(status_code=403, detail="Not your claim")
    elif user.role == Role.INSURER:
        insurer = _owned_insurer(db, user)
        policy = db.get(PatientPolicy, claim.patient_policy_id)
        if not policy or policy.insurer_id != insurer.id:
            raise HTTPException(status_code=403, detail="Not a claim on your policies")
    elif user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Not permitted")

    return ser.claim_out(db, claim)


@router.post("/claims/{claim_id}/decision", response_model=InsuranceClaimOut)
def decide_claim(
    claim_id: int, payload: ClaimDecision, db: DbSession, user: CurrentUser
) -> InsuranceClaimOut:
    """Insurer approves, part-approves, rejects or settles a claim."""
    insurer = _owned_insurer(db, user)
    claim = db.get(InsuranceClaim, claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    policy = db.get(PatientPolicy, claim.patient_policy_id)
    if not policy or policy.insurer_id != insurer.id:
        raise HTTPException(status_code=403, detail="Not a claim on your policies")
    if claim.status == ClaimStatus.SETTLED:
        raise HTTPException(status_code=409, detail="This claim is already settled")

    now = datetime.now(UTC)
    previous_status = claim.status
    claim.status = payload.status
    claim.reviewer_note = payload.reviewer_note or claim.reviewer_note

    if payload.status == ClaimStatus.REJECTED:
        claim.amount_approved = 0
        claim.rejection_reason = payload.rejection_reason
        claim.decided_at = now
    elif payload.status in {ClaimStatus.APPROVED, ClaimStatus.PARTIALLY_APPROVED}:
        approved = payload.amount_approved
        if approved is None:
            approved = claim.amount_claimed if payload.status == ClaimStatus.APPROVED else 0
        if approved > policy.remaining_amount:
            raise HTTPException(
                status_code=409, detail="Approved amount exceeds the policy's remaining cover"
            )
        claim.amount_approved = approved
        claim.decided_at = now
    elif payload.status == ClaimStatus.SETTLED:
        if previous_status not in DECIDED_STATUSES:
            raise HTTPException(status_code=409, detail="Approve the claim before settling it")
        claim.settled_at = now
        # Cover is consumed only when money actually moves.
        policy.used_amount = round(policy.used_amount + claim.amount_approved, 2)

    patient = db.get(PatientProfile, claim.patient_id)
    if patient:
        db.add(
            Notification(
                user_id=patient.user_id,
                kind="claim_update",
                title=f"Claim {claim.claim_number} — {payload.status.replace('_', ' ')}",
                body=payload.reviewer_note or payload.rejection_reason,
                link=f"/claims/{claim.id}",
            )
        )

    db.commit()
    db.refresh(claim)
    return ser.claim_out(db, claim)


@router.post("/claims/{claim_id}/documents", response_model=InsuranceClaimOut)
def attach_document(
    claim_id: int, label: str, file_url: str, db: DbSession, patient: CurrentPatient
) -> InsuranceClaimOut:
    claim = db.get(InsuranceClaim, claim_id)
    if not claim or claim.patient_id != patient.id:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim.status in DECIDED_STATUSES:
        raise HTTPException(status_code=409, detail="This claim has already been decided")
    db.add(ClaimDocument(claim_id=claim.id, label=label, file_url=file_url))
    db.commit()
    db.refresh(claim)
    return ser.claim_out(db, claim)


@router.delete("/claims/{claim_id}", response_model=Message)
def withdraw_claim(claim_id: int, db: DbSession, patient: CurrentPatient) -> Message:
    claim = db.get(InsuranceClaim, claim_id)
    if not claim or claim.patient_id != patient.id:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim.status in DECIDED_STATUSES:
        raise HTTPException(status_code=409, detail="A decided claim cannot be withdrawn")
    db.delete(claim)
    db.commit()
    return Message(detail="Claim withdrawn")

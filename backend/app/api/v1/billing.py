from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import desc, func, select

from app.api.deps import CurrentPatient, DbSession
from app.api.v1 import serializers as ser
from app.core.enums import ClaimStatus, PaymentStatus
from app.models import InsuranceClaim, Payment, Subscription
from app.schemas.finance import (
    BillingSummary,
    PaymentCreate,
    PaymentOut,
    SubscribeRequest,
    SubscriptionOut,
)
from app.services.payments import record_payment

router = APIRouter(prefix="/billing", tags=["billing"])

PREMIUM_PRICES = {("plus", "monthly"): 299.0, ("plus", "yearly"): 2999.0}


@router.get("/payments/me", response_model=list[PaymentOut])
def list_my_payments(
    db: DbSession,
    patient: CurrentPatient,
    purpose: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
) -> list[PaymentOut]:
    query = select(Payment).where(Payment.patient_id == patient.id)
    if purpose:
        query = query.where(Payment.purpose == purpose)
    rows = db.scalars(query.order_by(desc(Payment.created_at)).limit(limit).offset(offset)).all()
    return [ser.payment_out(db, p) for p in rows]


@router.get("/summary", response_model=BillingSummary)
def read_billing_summary(db: DbSession, patient: CurrentPatient) -> BillingSummary:
    paid = select(Payment).where(
        Payment.patient_id == patient.id, Payment.status == PaymentStatus.PAID
    )

    total_spent = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0.0)).where(
            Payment.patient_id == patient.id, Payment.status == PaymentStatus.PAID
        )
    )
    year_start = datetime(datetime.now(UTC).year, 1, 1, tzinfo=UTC)
    spent_this_year = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0.0)).where(
            Payment.patient_id == patient.id,
            Payment.status == PaymentStatus.PAID,
            Payment.paid_at >= year_start,
        )
    )
    pending = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0.0)).where(
            Payment.patient_id == patient.id, Payment.status == PaymentStatus.PENDING
        )
    )
    reimbursed = db.scalar(
        select(func.coalesce(func.sum(InsuranceClaim.amount_approved), 0.0)).where(
            InsuranceClaim.patient_id == patient.id,
            InsuranceClaim.status == ClaimStatus.SETTLED,
        )
    )

    by_purpose_rows = db.execute(
        select(Payment.purpose, func.sum(Payment.amount))
        .where(Payment.patient_id == patient.id, Payment.status == PaymentStatus.PAID)
        .group_by(Payment.purpose)
    ).all()

    recent = db.scalars(paid.order_by(desc(Payment.created_at)).limit(8)).all()

    return BillingSummary(
        total_spent=round(float(total_spent or 0), 2),
        spent_this_year=round(float(spent_this_year or 0), 2),
        pending_amount=round(float(pending or 0), 2),
        reimbursed_amount=round(float(reimbursed or 0), 2),
        by_purpose={purpose: round(float(amount), 2) for purpose, amount in by_purpose_rows},
        recent=[ser.payment_out(db, p) for p in recent],
    )


@router.post("/payments", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def make_payment(payload: PaymentCreate, db: DbSession, patient: CurrentPatient) -> PaymentOut:
    """Generic payment entry point (hospital bills, ad-hoc charges)."""
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    payment = record_payment(
        db,
        patient_id=patient.id,
        purpose=payload.purpose,
        amount=payload.amount,
        ref_table=payload.ref_table,
        ref_id=payload.ref_id,
        method=payload.method,
        description=payload.description,
    )
    db.commit()
    db.refresh(payment)
    return ser.payment_out(db, payment)


# --- premium subscription ------------------------------------------------------


@router.get("/subscription/me", response_model=SubscriptionOut | None)
def read_my_subscription(db: DbSession, patient: CurrentPatient) -> Subscription | None:
    return db.scalar(
        select(Subscription)
        .where(Subscription.patient_id == patient.id, Subscription.is_active.is_(True))
        .order_by(desc(Subscription.created_at))
    )


@router.post("/subscription", response_model=SubscriptionOut, status_code=status.HTTP_201_CREATED)
def subscribe(payload: SubscribeRequest, db: DbSession, patient: CurrentPatient) -> Subscription:
    """Opt in to premium; unlocks the ML recommendation surfaces."""
    price = PREMIUM_PRICES.get((payload.tier, payload.billing_cycle))
    if price is None:
        raise HTTPException(status_code=400, detail="Unknown tier or billing cycle")

    existing = db.scalar(
        select(Subscription).where(
            Subscription.patient_id == patient.id, Subscription.is_active.is_(True)
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="You already have an active subscription")

    today = datetime.now(UTC).date()
    renews = today.replace(year=today.year + 1) if payload.billing_cycle == "yearly" else (
        today.replace(year=today.year + 1, month=1)
        if today.month == 12
        else today.replace(month=today.month + 1)
    )

    subscription = Subscription(
        patient_id=patient.id,
        tier=payload.tier,
        price=price,
        billing_cycle=payload.billing_cycle,
        started_on=today,
        renews_on=renews,
    )
    db.add(subscription)
    patient.is_premium = True

    record_payment(
        db,
        patient_id=patient.id,
        purpose="premium",
        amount=price,
        ref_table="subscriptions",
        ref_id=None,
        description=f"HealthNexus {payload.tier} — {payload.billing_cycle}",
    )
    db.commit()
    db.refresh(subscription)
    return subscription


@router.delete("/subscription", response_model=SubscriptionOut)
def cancel_subscription(db: DbSession, patient: CurrentPatient) -> Subscription:
    subscription = db.scalar(
        select(Subscription).where(
            Subscription.patient_id == patient.id, Subscription.is_active.is_(True)
        )
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="No active subscription")
    subscription.is_active = False
    subscription.auto_renew = False
    subscription.cancelled_at = datetime.now(UTC)
    patient.is_premium = False
    db.commit()
    db.refresh(subscription)
    return subscription

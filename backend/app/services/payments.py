import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import PaymentPurpose, PaymentStatus
from app.models import Payment


def record_payment(
    db: Session,
    *,
    patient_id: int,
    purpose: PaymentPurpose | str,
    amount: float,
    payee_kind: str | None = None,
    payee_id: int | None = None,
    ref_table: str | None = None,
    ref_id: int | None = None,
    method: str = "upi",
    description: str | None = None,
    settle_immediately: bool = True,
) -> Payment:
    """Create the ledger row for a transaction and split out the platform's cut.

    `settle_immediately` stands in for a payment-gateway callback: swap it for a
    webhook that flips the row to PAID once a real gateway is wired in.
    """
    rate = settings.COMMISSION_RATE
    commission = round(amount * rate, 2)

    payment = Payment(
        patient_id=patient_id,
        purpose=str(purpose),
        ref_table=ref_table,
        ref_id=ref_id,
        payee_kind=payee_kind,
        payee_id=payee_id,
        amount=round(amount, 2),
        commission_rate=rate,
        commission_amount=commission,
        payout_amount=round(amount - commission, 2),
        method=method,
        description=description,
        status=PaymentStatus.PAID if settle_immediately else PaymentStatus.PENDING,
        gateway_ref=f"HNXPAY-{uuid.uuid4().hex[:12].upper()}",
        paid_at=datetime.now(UTC) if settle_immediately else None,
    )
    db.add(payment)
    db.flush()
    return payment

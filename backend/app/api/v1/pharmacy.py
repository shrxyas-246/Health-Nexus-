from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import desc, select

from app.api.deps import CurrentPatient, CurrentUser, DbSession
from app.api.v1 import serializers as ser
from app.core.enums import MedicineOrderStatus, PaymentPurpose, ReviewTarget, Role
from app.models import (
    MedicineOrder,
    MedicineOrderItem,
    Pharmacy,
    PharmacyItem,
    Prescription,
    PrescriptionItem,
)
from app.schemas.common import Message
from app.schemas.orders import (
    MedicineOrderCreate,
    MedicineOrderOut,
    MedicineOrderStatusUpdate,
)
from app.schemas.providers import PharmacyItemOut, PharmacyOut, RatingBreakdown
from app.services.payments import record_payment
from app.services.ratings import star_breakdown

router = APIRouter(prefix="/pharmacies", tags=["pharmacy"])

CANCELLABLE = {MedicineOrderStatus.PLACED, MedicineOrderStatus.ACCEPTED}


def _owned_pharmacy(db, user) -> Pharmacy:
    pharmacy = db.scalar(select(Pharmacy).where(Pharmacy.owner_user_id == user.id))
    if not pharmacy:
        raise HTTPException(status_code=403, detail="This account does not operate a pharmacy")
    return pharmacy


@router.get("", response_model=list[PharmacyOut])
def list_pharmacies(
    db: DbSession,
    city: str | None = None,
    q: str | None = None,
    delivers: bool | None = None,
    open_24x7: bool | None = None,
    limit: int = Query(30, le=100),
) -> list[PharmacyOut]:
    query = select(Pharmacy)
    if city:
        query = query.where(Pharmacy.city == city)
    if q:
        query = query.where(Pharmacy.name.ilike(f"%{q}%"))
    if delivers is not None:
        query = query.where(Pharmacy.delivers.is_(delivers))
    if open_24x7 is not None:
        query = query.where(Pharmacy.is_24x7.is_(open_24x7))
    rows = db.scalars(query.order_by(desc(Pharmacy.rating_avg)).limit(limit)).all()
    return [ser.pharmacy_out(p) for p in rows]


@router.get("/medicines/search", response_model=list[PharmacyItemOut])
def search_medicines(
    db: DbSession, q: str, city: str | None = None, in_stock_only: bool = True
) -> list[PharmacyItem]:
    query = select(PharmacyItem).where(PharmacyItem.medicine_name.ilike(f"%{q}%"))
    if in_stock_only:
        query = query.where(PharmacyItem.stock_qty > 0)
    if city:
        query = query.join(Pharmacy, Pharmacy.id == PharmacyItem.pharmacy_id).where(
            Pharmacy.city == city
        )
    return db.scalars(query.order_by(PharmacyItem.selling_price).limit(50)).all()


@router.get("/{pharmacy_id}", response_model=PharmacyOut)
def read_pharmacy(pharmacy_id: int, db: DbSession) -> PharmacyOut:
    pharmacy = db.get(Pharmacy, pharmacy_id)
    if not pharmacy:
        raise HTTPException(status_code=404, detail="Pharmacy not found")
    return ser.pharmacy_out(pharmacy)


@router.get("/{pharmacy_id}/inventory", response_model=list[PharmacyItemOut])
def list_inventory(pharmacy_id: int, db: DbSession, q: str | None = None) -> list[PharmacyItem]:
    query = select(PharmacyItem).where(PharmacyItem.pharmacy_id == pharmacy_id)
    if q:
        query = query.where(PharmacyItem.medicine_name.ilike(f"%{q}%"))
    return db.scalars(query.order_by(PharmacyItem.medicine_name)).all()


@router.get("/{pharmacy_id}/ratings", response_model=RatingBreakdown)
def read_pharmacy_ratings(pharmacy_id: int, db: DbSession) -> RatingBreakdown:
    pharmacy = db.get(Pharmacy, pharmacy_id)
    if not pharmacy:
        raise HTTPException(status_code=404, detail="Pharmacy not found")
    return RatingBreakdown(
        average=pharmacy.rating_avg,
        count=pharmacy.rating_count,
        stars=star_breakdown(db, ReviewTarget.PHARMACY, pharmacy_id),
    )


@router.post("/{pharmacy_id}/quote", response_model=MedicineOrderOut)
def quote_prescription(
    pharmacy_id: int, prescription_id: int, db: DbSession, patient: CurrentPatient
) -> MedicineOrderOut:
    """Price a prescription at one pharmacy without placing the order."""
    order, _ = _build_order(
        db,
        patient=patient,
        pharmacy_id=pharmacy_id,
        prescription_id=prescription_id,
        prescription_item_ids=[],
        delivery=False,
        delivery_address=None,
        persist=False,
    )
    return order


def _build_order(
    db,
    *,
    patient,
    pharmacy_id: int,
    prescription_id: int | None,
    prescription_item_ids: list[int],
    delivery: bool,
    delivery_address: str | None,
    persist: bool,
):
    """Shared pricing path for both a quote and a real order."""
    pharmacy = db.get(Pharmacy, pharmacy_id)
    if not pharmacy:
        raise HTTPException(status_code=404, detail="Pharmacy not found")
    if delivery and not pharmacy.delivers:
        raise HTTPException(status_code=400, detail="This pharmacy does not deliver")

    items: list[PrescriptionItem] = []
    if prescription_id:
        prescription = db.get(Prescription, prescription_id)
        if not prescription or prescription.patient_id != patient.id:
            raise HTTPException(status_code=404, detail="Prescription not found")
        query = select(PrescriptionItem).where(
            PrescriptionItem.prescription_id == prescription.id
        )
        if prescription_item_ids:
            query = query.where(PrescriptionItem.id.in_(prescription_item_ids))
        items = db.scalars(query).all()

    if not items:
        raise HTTPException(status_code=400, detail="Nothing to order from that prescription")

    stock = {
        s.medicine_name.lower(): s
        for s in db.scalars(select(PharmacyItem).where(PharmacyItem.pharmacy_id == pharmacy.id)).all()
    }

    order = MedicineOrder(
        patient_id=patient.id,
        pharmacy_id=pharmacy.id,
        prescription_id=prescription_id,
        status=MedicineOrderStatus.PLACED,
        delivery=delivery,
        delivery_address=delivery_address or patient.address,
        delivery_fee=pharmacy.delivery_fee if delivery else 0,
        # Column defaults only land on flush, and the quote path never flushes.
        discount=0,
        subtotal=0,
        total_amount=0,
    )

    subtotal = 0.0
    unavailable: list[str] = []
    line_items: list[MedicineOrderItem] = []

    for item in items:
        match = stock.get(item.medicine_name.lower())
        quantity = item.quantity or (item.duration_days or 1)
        if not match or match.stock_qty <= 0:
            unavailable.append(item.medicine_name)
            continue
        line_total = round(match.selling_price * quantity, 2)
        subtotal += line_total
        line_items.append(
            MedicineOrderItem(
                pharmacy_item_id=match.id,
                prescription_item_id=item.id,
                medicine_name=item.medicine_name,
                strength=item.strength,
                quantity=quantity,
                unit_price=match.selling_price,
                line_total=line_total,
            )
        )

    if not line_items:
        raise HTTPException(
            status_code=409,
            detail=f"This pharmacy has none of the prescribed medicines in stock: {', '.join(unavailable)}",
        )

    order.subtotal = round(subtotal, 2)
    order.total_amount = round(order.subtotal - order.discount + order.delivery_fee, 2)

    if not persist:
        # Quote only: nothing is saved, so stand in for the ids the client expects.
        order.id = 0
        order.created_at = datetime.now(UTC)
        for index, line in enumerate(line_items, start=1):
            line.id = index
        order.items = line_items
        return (
            ser.medicine_order_out(db, order),
            unavailable,
        )

    db.add(order)
    db.flush()
    for line in line_items:
        line.medicine_order_id = order.id
        db.add(line)
    db.flush()
    db.refresh(order)
    return order, unavailable


@router.post("/orders", response_model=MedicineOrderOut, status_code=status.HTTP_201_CREATED)
def place_order(
    payload: MedicineOrderCreate, db: DbSession, patient: CurrentPatient
) -> MedicineOrderOut:
    """Forward a prescription to a medical store so the order is ready on arrival."""
    order, _ = _build_order(
        db,
        patient=patient,
        pharmacy_id=payload.pharmacy_id,
        prescription_id=payload.prescription_id,
        prescription_item_ids=payload.prescription_item_ids,
        delivery=payload.delivery,
        delivery_address=payload.delivery_address,
        persist=True,
    )

    record_payment(
        db,
        patient_id=patient.id,
        purpose=PaymentPurpose.MEDICINE_ORDER,
        amount=order.total_amount,
        payee_kind="pharmacy",
        payee_id=order.pharmacy_id,
        ref_table="medicine_orders",
        ref_id=order.id,
        description=f"Medicines — {ser._name_of(db, Pharmacy, order.pharmacy_id)}",
    )
    db.commit()
    db.refresh(order)
    return ser.medicine_order_out(db, order)


@router.get("/orders/me", response_model=list[MedicineOrderOut])
def list_my_orders(
    db: DbSession, patient: CurrentPatient, status_filter: str | None = Query(None, alias="status")
) -> list[MedicineOrderOut]:
    query = select(MedicineOrder).where(MedicineOrder.patient_id == patient.id)
    if status_filter:
        query = query.where(MedicineOrder.status == status_filter)
    rows = db.scalars(query.order_by(desc(MedicineOrder.created_at))).all()
    return [ser.medicine_order_out(db, o) for o in rows]


@router.get("/orders/incoming", response_model=list[MedicineOrderOut])
def list_incoming_orders(
    db: DbSession, user: CurrentUser, status_filter: str | None = Query(None, alias="status")
) -> list[MedicineOrderOut]:
    """Pharmacy-side queue of orders awaiting approval and fulfilment."""
    pharmacy = _owned_pharmacy(db, user)
    query = select(MedicineOrder).where(MedicineOrder.pharmacy_id == pharmacy.id)
    if status_filter:
        query = query.where(MedicineOrder.status == status_filter)
    else:
        query = query.where(
            MedicineOrder.status.not_in(
                [
                    MedicineOrderStatus.FULFILLED,
                    MedicineOrderStatus.REJECTED,
                    MedicineOrderStatus.CANCELLED,
                ]
            )
        )
    rows = db.scalars(query.order_by(desc(MedicineOrder.created_at))).all()
    return [ser.medicine_order_out(db, o) for o in rows]


@router.patch("/orders/{order_id}/status", response_model=MedicineOrderOut)
def update_order_status(
    order_id: int, payload: MedicineOrderStatusUpdate, db: DbSession, user: CurrentUser
) -> MedicineOrderOut:
    order = db.get(MedicineOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if user.role == Role.PHARMACY:
        pharmacy = _owned_pharmacy(db, user)
        if order.pharmacy_id != pharmacy.id:
            raise HTTPException(status_code=403, detail="Not your order")
    elif user.role == Role.PATIENT:
        if not user.patient or order.patient_id != user.patient.id:
            raise HTTPException(status_code=403, detail="Not your order")
        if payload.status != MedicineOrderStatus.CANCELLED:
            raise HTTPException(status_code=403, detail="Patients may only cancel an order")
        if order.status not in CANCELLABLE:
            raise HTTPException(status_code=409, detail="This order can no longer be cancelled")
    elif user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Not permitted")

    order.status = payload.status
    if payload.rejection_reason:
        order.rejection_reason = payload.rejection_reason
    if payload.status == MedicineOrderStatus.READY:
        order.ready_at = payload.ready_at or datetime.now(UTC)

    db.commit()
    db.refresh(order)
    return ser.medicine_order_out(db, order)


@router.put("/inventory/{item_id}", response_model=PharmacyItemOut)
def update_stock(
    item_id: int,
    db: DbSession,
    user: CurrentUser,
    stock_qty: int | None = None,
    selling_price: float | None = None,
) -> PharmacyItem:
    pharmacy = _owned_pharmacy(db, user)
    item = db.get(PharmacyItem, item_id)
    if not item or item.pharmacy_id != pharmacy.id:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    if stock_qty is not None:
        item.stock_qty = stock_qty
    if selling_price is not None:
        item.selling_price = selling_price
    db.commit()
    db.refresh(item)
    return item


@router.delete("/orders/{order_id}", response_model=Message)
def cancel_order(order_id: int, db: DbSession, patient: CurrentPatient) -> Message:
    order = db.get(MedicineOrder, order_id)
    if not order or order.patient_id != patient.id:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status not in CANCELLABLE:
        raise HTTPException(status_code=409, detail="This order can no longer be cancelled")
    order.status = MedicineOrderStatus.CANCELLED
    db.commit()
    return Message(detail="Order cancelled")

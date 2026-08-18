from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import desc, select

from app.api.deps import CurrentPatient, CurrentUser, DbSession, resolve_patient_access
from app.api.v1 import serializers as ser
from app.core.enums import (
    LabOrderStatus,
    PaymentPurpose,
    ReviewTarget,
    Role,
    TimelineKind,
)
from app.models import (
    Lab,
    LabOrder,
    LabOrderItem,
    LabReport,
    LabReportValue,
    LabTest,
    Notification,
    PatientProfile,
    TestRequest,
)
from app.schemas.common import Message
from app.schemas.orders import (
    DoctorRemarkCreate,
    LabOrderCreate,
    LabOrderOut,
    LabOrderStatusUpdate,
    LabReportCreate,
    LabReportOut,
)
from app.schemas.providers import LabOut, LabTestOut, RatingBreakdown
from app.services.payments import record_payment
from app.services.ratings import star_breakdown
from app.services.timeline import record_event

router = APIRouter(prefix="/labs", tags=["labs"])

TERMINAL_STATUSES = {LabOrderStatus.READY, LabOrderStatus.CANCELLED}


def _flag_for(value: float | None, low: float | None, high: float | None) -> str | None:
    if value is None or (low is None and high is None):
        return None
    if low is not None and value < low:
        return "low"
    if high is not None and value > high:
        return "high"
    return "normal"


def _owned_lab(db, user) -> Lab:
    lab = db.scalar(select(Lab).where(Lab.owner_user_id == user.id))
    if not lab:
        raise HTTPException(status_code=403, detail="This account does not operate a lab")
    return lab


# --- directory -----------------------------------------------------------------


@router.get("", response_model=list[LabOut])
def list_labs(
    db: DbSession,
    city: str | None = None,
    q: str | None = None,
    home_collection: bool | None = None,
    limit: int = Query(30, le=100),
) -> list[LabOut]:
    query = select(Lab)
    if city:
        query = query.where(Lab.city == city)
    if q:
        query = query.where(Lab.name.ilike(f"%{q}%"))
    if home_collection is not None:
        query = query.where(Lab.home_collection.is_(home_collection))
    rows = db.scalars(query.order_by(desc(Lab.rating_avg)).limit(limit)).all()
    return [ser.lab_out(db, lab) for lab in rows]


@router.get("/tests/search", response_model=list[LabTestOut])
def search_tests(
    db: DbSession, q: str, city: str | None = None, limit: int = Query(40, le=100)
) -> list[LabTest]:
    """Find a named test across labs, cheapest first."""
    query = select(LabTest).where(LabTest.name.ilike(f"%{q}%"), LabTest.is_active.is_(True))
    if city:
        query = query.join(Lab, Lab.id == LabTest.lab_id).where(Lab.city == city)
    return db.scalars(query.order_by(LabTest.price).limit(limit)).all()


@router.get("/{lab_id}", response_model=LabOut)
def read_lab(lab_id: int, db: DbSession) -> LabOut:
    lab = db.get(Lab, lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="Lab not found")
    return ser.lab_out(db, lab, include_tests=True)


@router.get("/{lab_id}/tests", response_model=list[LabTestOut])
def list_lab_tests(lab_id: int, db: DbSession) -> list[LabTest]:
    return db.scalars(
        select(LabTest).where(LabTest.lab_id == lab_id, LabTest.is_active.is_(True)).order_by(LabTest.name)
    ).all()


@router.get("/{lab_id}/ratings", response_model=RatingBreakdown)
def read_lab_ratings(lab_id: int, db: DbSession) -> RatingBreakdown:
    lab = db.get(Lab, lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="Lab not found")
    return RatingBreakdown(
        average=lab.rating_avg,
        count=lab.rating_count,
        stars=star_breakdown(db, ReviewTarget.LAB, lab_id),
    )


# --- booking -------------------------------------------------------------------


@router.post("/orders", response_model=LabOrderOut, status_code=status.HTTP_201_CREATED)
def book_tests(payload: LabOrderCreate, db: DbSession, patient: CurrentPatient) -> LabOrderOut:
    """Book tests at a lab, either from a doctor's request or the lab's catalogue."""
    lab = db.get(Lab, payload.lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="Lab not found")
    if payload.home_collection and not lab.home_collection:
        raise HTTPException(status_code=400, detail="This lab does not offer home collection")

    order = LabOrder(
        patient_id=patient.id,
        lab_id=lab.id,
        status=LabOrderStatus.BOOKED,
        scheduled_at=payload.scheduled_at,
        home_collection=payload.home_collection,
        collection_address=payload.collection_address or patient.address,
        notes=payload.notes,
    )
    db.add(order)
    db.flush()

    subtotal = 0.0
    catalogue = {
        t.name.lower(): t
        for t in db.scalars(select(LabTest).where(LabTest.lab_id == lab.id)).all()
    }

    # Tests the doctor asked for: price them against this lab's catalogue.
    for request_id in payload.test_request_ids:
        request = db.get(TestRequest, request_id)
        if not request or request.patient_id != patient.id:
            raise HTTPException(status_code=404, detail=f"Test request {request_id} not found")
        match = catalogue.get(request.test_name.lower())
        price = match.effective_price if match else 0.0
        subtotal += price
        db.add(
            LabOrderItem(
                lab_order_id=order.id,
                lab_test_id=match.id if match else None,
                test_request_id=request.id,
                test_name=request.test_name,
                price=price,
            )
        )
        request.fulfilled = True
        if request.doctor_id and not order.doctor_id:
            order.doctor_id = request.doctor_id
            order.prescription_id = request.prescription_id

    # Tests the patient picked directly.
    for test_id in payload.lab_test_ids:
        test = db.get(LabTest, test_id)
        if not test or test.lab_id != lab.id:
            raise HTTPException(status_code=404, detail=f"Test {test_id} is not offered by this lab")
        subtotal += test.effective_price
        db.add(
            LabOrderItem(
                lab_order_id=order.id,
                lab_test_id=test.id,
                test_name=test.name,
                price=test.effective_price,
            )
        )

    if not payload.test_request_ids and not payload.lab_test_ids:
        raise HTTPException(status_code=400, detail="Select at least one test to book")

    order.subtotal = round(subtotal, 2)
    if payload.home_collection:
        order.subtotal += lab.home_collection_fee
    order.total_amount = round(order.subtotal - order.discount, 2)

    record_payment(
        db,
        patient_id=patient.id,
        purpose=PaymentPurpose.LAB_ORDER,
        amount=order.total_amount,
        payee_kind="lab",
        payee_id=lab.id,
        ref_table="lab_orders",
        ref_id=order.id,
        description=f"Lab tests — {lab.name}",
    )

    db.commit()
    db.refresh(order)
    return ser.lab_order_out(db, order)


@router.get("/orders/me", response_model=list[LabOrderOut])
def list_my_orders(
    db: DbSession, patient: CurrentPatient, status_filter: str | None = Query(None, alias="status")
) -> list[LabOrderOut]:
    query = select(LabOrder).where(LabOrder.patient_id == patient.id)
    if status_filter:
        query = query.where(LabOrder.status == status_filter)
    rows = db.scalars(query.order_by(desc(LabOrder.created_at))).all()
    return [ser.lab_order_out(db, o) for o in rows]


@router.get("/orders/incoming", response_model=list[LabOrderOut])
def list_incoming_orders(
    db: DbSession, user: CurrentUser, status_filter: str | None = Query(None, alias="status")
) -> list[LabOrderOut]:
    """Lab-side queue of bookings to confirm and process."""
    lab = _owned_lab(db, user)
    query = select(LabOrder).where(LabOrder.lab_id == lab.id)
    if status_filter:
        query = query.where(LabOrder.status == status_filter)
    else:
        query = query.where(LabOrder.status.not_in(list(TERMINAL_STATUSES)))
    rows = db.scalars(query.order_by(LabOrder.scheduled_at)).all()
    return [ser.lab_order_out(db, o) for o in rows]


@router.patch("/orders/{order_id}/status", response_model=LabOrderOut)
def update_order_status(
    order_id: int, payload: LabOrderStatusUpdate, db: DbSession, user: CurrentUser
) -> LabOrderOut:
    order = db.get(LabOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Lab order not found")

    # Labs drive the workflow; the patient may only cancel.
    if user.role == Role.LAB:
        lab = _owned_lab(db, user)
        if order.lab_id != lab.id:
            raise HTTPException(status_code=403, detail="Not your order")
    elif user.role == Role.PATIENT:
        if not user.patient or order.patient_id != user.patient.id:
            raise HTTPException(status_code=403, detail="Not your order")
        if payload.status != LabOrderStatus.CANCELLED:
            raise HTTPException(status_code=403, detail="Patients may only cancel a booking")
    elif user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Not permitted")

    order.status = payload.status
    if payload.scheduled_at:
        order.scheduled_at = payload.scheduled_at
    db.commit()
    db.refresh(order)
    return ser.lab_order_out(db, order)


# --- reports -------------------------------------------------------------------


@router.post(
    "/patients/{patient_id}/reports", response_model=LabReportOut, status_code=status.HTTP_201_CREATED
)
def upload_report(
    patient_id: int, payload: LabReportCreate, db: DbSession, user: CurrentUser
) -> LabReportOut:
    """Publish a report. Labs file results; patients backfill historical ones."""
    patient = resolve_patient_access(db, user, patient_id)

    lab_id = payload.lab_id
    if user.role == Role.LAB:
        lab_id = _owned_lab(db, user).id

    order = db.get(LabOrder, payload.lab_order_id) if payload.lab_order_id else None
    if order and order.patient_id != patient.id:
        raise HTTPException(status_code=400, detail="That order belongs to a different patient")

    report = LabReport(
        patient_id=patient.id,
        lab_id=lab_id or (order.lab_id if order else None),
        lab_order_id=payload.lab_order_id,
        title=payload.title,
        issued_at=payload.issued_at or datetime.now(UTC),
        summary=payload.summary,
        file_url=payload.file_url,
        # Results route straight back to the doctor who ordered them.
        shared_with_doctor_id=payload.share_with_doctor_id or (order.doctor_id if order else None),
        is_legacy=payload.is_legacy or user.role == Role.PATIENT,
    )
    db.add(report)
    db.flush()

    for value in payload.values:
        db.add(
            LabReportValue(
                report_id=report.id,
                flag=_flag_for(value.value, value.ref_low, value.ref_high),
                **value.model_dump(),
            )
        )

    if order:
        order.status = LabOrderStatus.READY

    record_event(
        db,
        patient_id=patient.id,
        kind=TimelineKind.LAB_REPORT,
        occurred_at=report.issued_at,
        title=report.title,
        summary=report.summary,
        lab_id=report.lab_id,
        doctor_id=report.shared_with_doctor_id,
        ref_table="lab_reports",
        ref_id=report.id,
        is_legacy=report.is_legacy,
        editable_by_patient=report.is_legacy and user.role == Role.PATIENT,
    )
    db.commit()
    db.refresh(report)
    return ser.lab_report_out(db, report)


@router.get("/reports/{report_id}", response_model=LabReportOut)
def read_report(report_id: int, db: DbSession, user: CurrentUser) -> LabReportOut:
    report = db.get(LabReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    # A doctor the report was explicitly shared with can always open it.
    if not (user.role == Role.DOCTOR and user.doctor and report.shared_with_doctor_id == user.doctor.id):
        resolve_patient_access(db, user, report.patient_id)
    return ser.lab_report_out(db, report)


@router.post("/reports/{report_id}/share", response_model=LabReportOut)
def share_report_with_doctor(
    report_id: int, doctor_id: int, db: DbSession, patient: CurrentPatient
) -> LabReportOut:
    report = db.get(LabReport, report_id)
    if not report or report.patient_id != patient.id:
        raise HTTPException(status_code=404, detail="Report not found")
    report.shared_with_doctor_id = doctor_id
    report.doctor_reviewed_at = None
    db.commit()
    db.refresh(report)
    return ser.lab_report_out(db, report)


@router.post("/reports/{report_id}/remarks", response_model=LabReportOut)
def add_doctor_remarks(
    report_id: int, payload: DoctorRemarkCreate, db: DbSession, user: CurrentUser
) -> LabReportOut:
    """Doctor reviews a forwarded report and optionally asks for a follow-up."""
    if user.role != Role.DOCTOR or not user.doctor:
        raise HTTPException(status_code=403, detail="Only doctors can add remarks")
    report = db.get(LabReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.shared_with_doctor_id != user.doctor.id:
        raise HTTPException(status_code=403, detail="This report was not shared with you")

    report.doctor_remarks = payload.remarks
    report.doctor_reviewed_at = datetime.now(UTC)

    if payload.request_follow_up:
        patient = db.get(PatientProfile, report.patient_id)
        if patient:
            db.add(
                Notification(
                    user_id=patient.user_id,
                    kind="follow_up_requested",
                    title="Your doctor has asked for a follow-up",
                    body=payload.remarks,
                    link=f"/reports/{report.id}",
                )
            )
    db.commit()
    db.refresh(report)
    return ser.lab_report_out(db, report)


@router.delete("/orders/{order_id}", response_model=Message)
def cancel_order(order_id: int, db: DbSession, patient: CurrentPatient) -> Message:
    order = db.get(LabOrder, order_id)
    if not order or order.patient_id != patient.id:
        raise HTTPException(status_code=404, detail="Lab order not found")
    if order.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="This order can no longer be cancelled")
    order.status = LabOrderStatus.CANCELLED
    db.commit()
    return Message(detail="Booking cancelled")

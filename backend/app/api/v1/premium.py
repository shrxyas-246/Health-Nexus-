"""Premium ML recommendation surfaces + the one-tap emergency flow."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import desc, select

from app.api.deps import CurrentPatient, CurrentUser, DbSession
from app.api.v1 import serializers as ser
from app.core.enums import EmergencyStatus, Role, TimelineKind
from app.models import EmergencyRequest, Hospital, MLRecommendation, Notification
from app.schemas.common import Message
from app.schemas.orders import EmergencyRequestCreate, EmergencyRequestOut
from app.schemas.providers import (
    DoctorOut,
    HospitalOut,
    InsurancePlanOut,
    LabOut,
    PharmacyOut,
)
from app.schemas.social import RecommendationOut
from app.services import ml_client
from app.services import recommendations as rec
from app.services import wellness_plan
from app.services.geo import haversine_km
from app.services.timeline import record_event

router = APIRouter(tags=["premium"])


def _require_premium(patient) -> None:
    if not patient.is_premium:
        raise HTTPException(
            status_code=402,
            detail="This is a premium feature. Subscribe from the Plus tab to unlock it.",
        )


@router.get("/recommendations/doctors", response_model=list[DoctorOut])
def recommended_doctors(
    db: DbSession,
    patient: CurrentPatient,
    condition_id: int | None = None,
    limit: int = Query(6, le=20),
) -> list[DoctorOut]:
    _require_premium(patient)
    ranked, _version = rec.recommend_doctors(db, patient, limit=limit, condition_id=condition_id)
    return [
        ser.doctor_out(db, doctor, distance_km=distance, match_score=score, match_reason=reason)
        for doctor, score, reason, distance in ranked
    ]


@router.get("/recommendations/labs", response_model=list[LabOut])
def recommended_labs(
    db: DbSession,
    patient: CurrentPatient,
    tests: str = Query("", description="Comma-separated test names to price"),
    limit: int = Query(5, le=20),
) -> list[LabOut]:
    _require_premium(patient)
    test_names = [t.strip() for t in tests.split(",") if t.strip()]
    ranked, _version = rec.recommend_labs(db, patient, test_names, limit=limit)
    return [
        ser.lab_out(
            db, lab, distance_km=distance, match_score=score, match_reason=reason, quoted_total=quote
        )
        for lab, score, reason, distance, quote in ranked
    ]


@router.get("/recommendations/pharmacies", response_model=list[PharmacyOut])
def recommended_pharmacies(
    db: DbSession,
    patient: CurrentPatient,
    prescription_id: int | None = None,
    limit: int = Query(5, le=20),
) -> list[PharmacyOut]:
    _require_premium(patient)
    ranked, _version = rec.recommend_pharmacies(
        db, patient, prescription_id=prescription_id, limit=limit
    )
    return [
        ser.pharmacy_out(
            pharmacy,
            distance_km=distance,
            match_score=score,
            match_reason=reason,
            quoted_total=quote,
            unavailable_items=missing,
        )
        for pharmacy, score, reason, distance, quote, missing in ranked
    ]


@router.get("/recommendations/hospitals", response_model=list[HospitalOut])
def recommended_hospitals(
    db: DbSession,
    patient: CurrentPatient,
    need: str | None = None,
    limit: int = Query(5, le=20),
) -> list[HospitalOut]:
    _require_premium(patient)
    ranked, _version = rec.recommend_hospitals(db, patient, limit=limit, need=need)
    out = []
    for hospital, score, reason, distance in ranked:
        item = HospitalOut.model_validate(hospital)
        item.distance_km = distance
        item.match_score = score
        item.match_reason = reason
        out.append(item)
    return out


@router.get("/recommendations/insurance", response_model=list[InsurancePlanOut])
def recommended_insurance(
    db: DbSession, patient: CurrentPatient, limit: int = Query(5, le=20)
) -> list[InsurancePlanOut]:
    _require_premium(patient)
    ranked, _version = rec.recommend_insurance(db, patient, limit=limit)
    return [
        ser.plan_out(db, plan, match_score=score, match_reason=reason, insurer_name=insurer_name)
        for plan, score, reason, insurer_name in ranked
    ]


@router.get("/recommendations/daily", response_model=list[RecommendationOut])
def daily_advice(db: DbSession, patient: CurrentPatient) -> list[MLRecommendation]:
    """Today's diet/workout/lifestyle plan from model 2, generated once a day.

    Regenerates when the cached plan is older than 24 hours. If the ML service is
    unreachable the cached plan is served as-is — stale advice beats no advice,
    and the patient is never shown an error for something a background job would
    normally refresh.
    """
    _require_premium(patient)
    rows = wellness_plan.cached_plan(db, patient)
    if wellness_plan.plan_is_stale(rows):
        generated = wellness_plan.generate_plan(db, patient)
        if generated:
            return generated
    return rows


@router.post("/recommendations/daily/refresh", response_model=list[RecommendationOut])
def refresh_daily_advice(db: DbSession, patient: CurrentPatient) -> list[MLRecommendation]:
    """Force model 2 to rebuild the plan — used after the record changes."""
    _require_premium(patient)
    generated = wellness_plan.generate_plan(db, patient)
    if not generated:
        raise HTTPException(
            status_code=503,
            detail="The recommendation service is unavailable right now. Please try again shortly.",
        )
    return generated


@router.get("/ml/status", tags=["meta"])
def ml_status(user: CurrentUser) -> dict:
    """Which models are actually serving, so a fallback is visible rather than silent."""
    health = ml_client.service_health()
    return {
        "configured": ml_client.is_ml_service_configured(),
        "reachable": health is not None,
        "service": health,
        "fallback": "heuristic ranking + FAQ rules" if health is None else None,
    }


@router.post("/recommendations/{recommendation_id}/dismiss", response_model=Message)
def dismiss_recommendation(
    recommendation_id: int, db: DbSession, patient: CurrentPatient
) -> Message:
    row = db.get(MLRecommendation, recommendation_id)
    if not row or row.patient_id != patient.id:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    row.dismissed = True
    db.commit()
    return Message(detail="Dismissed")


# --- emergency -----------------------------------------------------------------


@router.post("/emergency", response_model=EmergencyRequestOut, status_code=status.HTTP_201_CREATED)
def one_tap_emergency(
    payload: EmergencyRequestCreate, db: DbSession, patient: CurrentPatient
) -> EmergencyRequestOut:
    """One tap: pick the nearest capable hospital, dispatch, and push the record ahead."""
    latitude = payload.latitude if payload.latitude is not None else patient.latitude
    longitude = payload.longitude if payload.longitude is not None else patient.longitude

    hospitals = db.scalars(
        select(Hospital).where(Hospital.has_emergency.is_(True), Hospital.has_ambulance.is_(True))
    ).all()
    if not hospitals:
        hospitals = db.scalars(select(Hospital)).all()
    if not hospitals:
        raise HTTPException(status_code=503, detail="No partner hospitals available")

    def sort_key(hospital: Hospital) -> tuple:
        distance = haversine_km(latitude, longitude, hospital.latitude, hospital.longitude)
        same_city = hospital.city == patient.city
        # Nearest first; unknown distances fall back to same-city then rating.
        return (
            distance if distance is not None else 9999,
            0 if same_city else 1,
            -hospital.rating_avg,
        )

    chosen = sorted(hospitals, key=sort_key)[0]
    distance = haversine_km(latitude, longitude, chosen.latitude, chosen.longitude)
    now = datetime.now(UTC)

    request = EmergencyRequest(
        patient_id=patient.id,
        hospital_id=chosen.id,
        status=EmergencyStatus.AMBULANCE_DISPATCHED,
        latitude=latitude,
        longitude=longitude,
        address_hint=payload.address_hint or patient.address,
        complaint=payload.complaint,
        # ETA estimate until a live dispatch integration exists.
        ambulance_eta_minutes=max(6, int((distance or 5) * 2.5)),
        ambulance_ref=f"AMB-{now.strftime('%H%M%S')}",
        record_pushed_at=now,  # profile forwarded immediately; paperwork deferred
        paperwork_deferred=True,
    )
    db.add(request)
    db.flush()

    if chosen.owner_user_id:
        db.add(
            Notification(
                user_id=chosen.owner_user_id,
                kind="emergency_inbound",
                title="Incoming emergency patient",
                body=(
                    f"{payload.complaint or 'Emergency'} — full medical record attached. "
                    "Registration formalities deferred until after admission."
                ),
                link=f"/emergency/{request.id}",
            )
        )

    record_event(
        db,
        patient_id=patient.id,
        kind=TimelineKind.EMERGENCY,
        occurred_at=now,
        title=f"Emergency — ambulance dispatched from {chosen.name}",
        summary=payload.complaint,
        hospital_id=chosen.id,
        ref_table="emergency_requests",
        ref_id=request.id,
    )
    db.commit()
    db.refresh(request)
    return _emergency_out(db, request)


def _emergency_out(db, request: EmergencyRequest) -> EmergencyRequestOut:
    hospital = db.get(Hospital, request.hospital_id) if request.hospital_id else None
    return EmergencyRequestOut(
        id=request.id,
        patient_id=request.patient_id,
        hospital_id=request.hospital_id,
        hospital_name=hospital.name if hospital else None,
        hospital_phone=hospital.phone if hospital else None,
        status=request.status,
        latitude=request.latitude,
        longitude=request.longitude,
        address_hint=request.address_hint,
        complaint=request.complaint,
        ambulance_eta_minutes=request.ambulance_eta_minutes,
        ambulance_ref=request.ambulance_ref,
        record_pushed_at=request.record_pushed_at,
        paperwork_deferred=request.paperwork_deferred,
        created_at=request.created_at,
    )


@router.get("/emergency/active", response_model=EmergencyRequestOut | None)
def active_emergency(db: DbSession, patient: CurrentPatient) -> EmergencyRequestOut | None:
    request = db.scalar(
        select(EmergencyRequest)
        .where(
            EmergencyRequest.patient_id == patient.id,
            EmergencyRequest.status.not_in([EmergencyStatus.CLOSED, EmergencyStatus.CANCELLED]),
        )
        .order_by(desc(EmergencyRequest.created_at))
    )
    return _emergency_out(db, request) if request else None


@router.patch("/emergency/{request_id}/status", response_model=EmergencyRequestOut)
def update_emergency_status(
    request_id: int, new_status: EmergencyStatus, db: DbSession, user: CurrentUser
) -> EmergencyRequestOut:
    request = db.get(EmergencyRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Emergency request not found")

    if user.role == Role.PATIENT:
        if not user.patient or request.patient_id != user.patient.id:
            raise HTTPException(status_code=403, detail="Not your request")
        if new_status != EmergencyStatus.CANCELLED:
            raise HTTPException(status_code=403, detail="Patients may only cancel")
    elif user.role == Role.HOSPITAL:
        hospital = db.scalar(select(Hospital).where(Hospital.owner_user_id == user.id))
        if not hospital or request.hospital_id != hospital.id:
            raise HTTPException(status_code=403, detail="Not your incoming patient")
    elif user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Not permitted")

    request.status = new_status
    if new_status in {EmergencyStatus.CLOSED, EmergencyStatus.CANCELLED}:
        request.closed_at = datetime.now(UTC)
    db.commit()
    db.refresh(request)
    return _emergency_out(db, request)

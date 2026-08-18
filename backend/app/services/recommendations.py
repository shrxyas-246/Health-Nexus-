"""Ranking for the premium recommendation surfaces.

Every function here builds the candidate set from the database, offers it to the
ML service via `ml_client.get_ranking`, and falls back to a transparent
heuristic score when no model is reachable. The response shape is identical
either way, so the frontend never branches on which one ran.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import ConditionStatus, PrescriptionStatus
from app.models import (
    Condition,
    DoctorProfile,
    Hospital,
    InsurancePlan,
    Insurer,
    Lab,
    LabTest,
    PatientProfile,
    Pharmacy,
    PharmacyItem,
    Prescription,
    PrescriptionItem,
    User,
)
from app.services import ml_client
from app.services.geo import haversine_km

HEURISTIC_VERSION = "heuristic-v1"

# Maps a condition to the specialities that treat it, for doctor matching.
SPECIALITY_HINTS: dict[str, tuple[str, ...]] = {
    "diabetes": ("Endocrinology", "General Medicine", "Diabetology"),
    "hypertension": ("Cardiology", "General Medicine"),
    "cholesterol": ("Cardiology", "General Medicine"),
    "asthma": ("Pulmonology", "General Medicine"),
    "thyroid": ("Endocrinology",),
    "arthritis": ("Rheumatology", "Orthopaedics"),
    "migraine": ("Neurology", "General Medicine"),
    "anxiety": ("Psychiatry",),
    "depression": ("Psychiatry",),
    "pregnancy": ("Obstetrics & Gynaecology",),
    "fracture": ("Orthopaedics",),
    "kidney": ("Nephrology",),
    "liver": ("Gastroenterology", "Hepatology"),
    "skin": ("Dermatology",),
    "cancer": ("Oncology",),
}


def patient_features(db: Session, patient: PatientProfile) -> dict[str, Any]:
    """Feature bundle handed to the ML service — also useful for offline training."""
    conditions = db.scalars(
        select(Condition).where(
            Condition.patient_id == patient.id,
            Condition.status != ConditionStatus.RESOLVED,
        )
    ).all()
    age = None
    if patient.date_of_birth:
        today = date.today()
        age = today.year - patient.date_of_birth.year - (
            (today.month, today.day) < (patient.date_of_birth.month, patient.date_of_birth.day)
        )
    return {
        "patient_id": patient.id,
        "age": age,
        "gender": patient.gender,
        "blood_group": patient.blood_group,
        "bmi": patient.bmi,
        "city": patient.city,
        "latitude": patient.latitude,
        "longitude": patient.longitude,
        "is_premium": patient.is_premium,
        "allergies": [a.substance for a in patient.allergies],
        "conditions": [
            {"name": c.name, "category": c.category, "status": c.status, "severity": c.severity}
            for c in conditions
        ],
    }


def _specialities_for(condition_names: list[str]) -> set[str]:
    hits: set[str] = set()
    for name in condition_names:
        lowered = name.lower()
        for keyword, specialities in SPECIALITY_HINTS.items():
            if keyword in lowered:
                hits.update(specialities)
    return hits


def _apply_ranking(
    kind: str,
    candidates: list[dict[str, Any]],
    features: dict[str, Any],
    context: dict[str, Any] | None,
    heuristic_scores: dict[int, tuple[float, str]],
) -> tuple[dict[int, tuple[float, str]], str]:
    """Prefer the model's ranking; fall back to the heuristic scores."""
    result = ml_client.get_ranking(kind, features, candidates, context)
    if result and result.ranked:
        merged = {
            item.id: (
                item.score,
                item.reason or heuristic_scores.get(item.id, (0, ""))[1],
            )
            for item in result.ranked
        }
        return merged, result.model_version
    return heuristic_scores, HEURISTIC_VERSION


def recommend_doctors(
    db: Session, patient: PatientProfile, limit: int = 6, condition_id: int | None = None
) -> tuple[list[tuple[DoctorProfile, float, str, float | None]], str]:
    """Rank doctors for the patient's active conditions."""
    query = select(Condition).where(
        Condition.patient_id == patient.id, Condition.status != ConditionStatus.RESOLVED
    )
    if condition_id:
        query = select(Condition).where(Condition.id == condition_id)
    condition_names = [c.name for c in db.scalars(query).all()]
    wanted = _specialities_for(condition_names)

    doctors = db.scalars(select(DoctorProfile)).all()
    heuristic: dict[int, tuple[float, str]] = {}
    distances: dict[int, float | None] = {}
    candidates: list[dict[str, Any]] = []

    for doctor in doctors:
        distance = haversine_km(
            patient.latitude, patient.longitude, doctor.latitude, doctor.longitude
        )
        distances[doctor.id] = distance

        speciality_match = doctor.specialization in wanted
        score = 0.0
        reasons: list[str] = []

        if speciality_match:
            score += 45
            reasons.append(f"Specialises in {doctor.specialization}")
        elif doctor.specialization == "General Medicine":
            score += 20
            reasons.append("General physician")

        score += doctor.rating_avg * 6
        if doctor.rating_count >= 20:
            score += 5
        if doctor.rating_avg >= 4.5:
            reasons.append(f"Rated {doctor.rating_avg} by {doctor.rating_count} patients")

        score += min(doctor.years_experience, 25) * 0.6
        if doctor.years_experience >= 10:
            reasons.append(f"{doctor.years_experience} years experience")

        if distance is not None:
            score += max(0, 20 - distance)
            reasons.append(f"{distance} km away")
        elif doctor.city and doctor.city == patient.city:
            score += 10
            reasons.append(f"Practises in {doctor.city}")

        if doctor.is_verified:
            score += 5

        heuristic[doctor.id] = (round(score, 2), " · ".join(reasons) or "Available for consultation")
        candidates.append(
            {
                "id": doctor.id,
                "specialization": doctor.specialization,
                "rating_avg": doctor.rating_avg,
                "rating_count": doctor.rating_count,
                "years_experience": doctor.years_experience,
                "consultation_fee": doctor.consultation_fee,
                "distance_km": distance,
                "city": doctor.city,
                "is_verified": doctor.is_verified,
            }
        )

    scores, version = _apply_ranking(
        "doctor",
        candidates,
        patient_features(db, patient),
        {"conditions": condition_names},
        heuristic,
    )
    ranked = sorted(doctors, key=lambda d: scores.get(d.id, (0, ""))[0], reverse=True)[:limit]
    return (
        [(d, scores.get(d.id, (0, ""))[0], scores.get(d.id, (0, ""))[1], distances.get(d.id)) for d in ranked],
        version,
    )


def recommend_labs(
    db: Session, patient: PatientProfile, test_names: list[str], limit: int = 5
) -> tuple[list[tuple[Lab, float, str, float | None, float | None]], str]:
    """Rank labs by what the requested basket actually costs at each one."""
    labs = db.scalars(select(Lab)).all()
    heuristic: dict[int, tuple[float, str]] = {}
    distances: dict[int, float | None] = {}
    quotes: dict[int, float | None] = {}
    candidates: list[dict[str, Any]] = []
    wanted = [t.strip().lower() for t in test_names if t.strip()]

    for lab in labs:
        tests = db.scalars(select(LabTest).where(LabTest.lab_id == lab.id, LabTest.is_active.is_(True))).all()
        by_name = {t.name.lower(): t for t in tests}

        matched = [by_name[name] for name in wanted if name in by_name]
        quote = round(sum(t.effective_price for t in matched), 2) if matched else None
        coverage = len(matched) / len(wanted) if wanted else 1.0

        distance = haversine_km(patient.latitude, patient.longitude, lab.latitude, lab.longitude)
        distances[lab.id] = distance
        quotes[lab.id] = quote

        score = coverage * 40
        reasons: list[str] = []
        if wanted:
            reasons.append(
                "All requested tests available"
                if coverage == 1.0
                else f"{len(matched)} of {len(wanted)} tests available"
            )

        score += lab.rating_avg * 5
        if lab.accreditation:
            score += 8
            reasons.append(f"{lab.accreditation} accredited")
        if lab.home_collection:
            score += 6
            reasons.append("Home sample collection")
        if distance is not None:
            score += max(0, 15 - distance)
            reasons.append(f"{distance} km away")

        candidates.append(
            {
                "id": lab.id,
                "quoted_total": quote,
                "coverage": coverage,
                "rating_avg": lab.rating_avg,
                "accreditation": lab.accreditation,
                "home_collection": lab.home_collection,
                "distance_km": distance,
            }
        )
        heuristic[lab.id] = (round(score, 2), " · ".join(reasons) or "Offers diagnostic services")

    # Cheapest complete basket gets an explicit price bonus, since price is the
    # headline promise of the premium lab recommendation.
    priced = [(lab_id, q) for lab_id, q in quotes.items() if q is not None]
    if priced:
        cheapest = min(q for _, q in priced)
        dearest = max(q for _, q in priced)
        spread = dearest - cheapest
        for lab_id, quote in priced:
            bonus = 25.0 if spread == 0 else 25 * (1 - (quote - cheapest) / spread)
            score, reason = heuristic[lab_id]
            if quote == cheapest and spread > 0:
                reason = f"Lowest price at ₹{quote:,.0f} · {reason}"
            heuristic[lab_id] = (round(score + bonus, 2), reason)

    scores, version = _apply_ranking(
        "lab", candidates, patient_features(db, patient), {"tests": test_names}, heuristic
    )
    ranked = sorted(labs, key=lambda lb: scores.get(lb.id, (0, ""))[0], reverse=True)[:limit]
    return (
        [
            (lb, scores.get(lb.id, (0, ""))[0], scores.get(lb.id, (0, ""))[1], distances.get(lb.id), quotes.get(lb.id))
            for lb in ranked
        ],
        version,
    )


def recommend_pharmacies(
    db: Session, patient: PatientProfile, prescription_id: int | None = None, limit: int = 5
) -> tuple[list[tuple[Pharmacy, float, str, float | None, float | None, list[str]]], str]:
    """Rank pharmacies on the real basket price for the patient's live medicines."""
    if prescription_id:
        prescription = db.get(Prescription, prescription_id)
    else:
        prescription = db.scalar(
            select(Prescription)
            .where(
                Prescription.patient_id == patient.id,
                Prescription.status == PrescriptionStatus.ACTIVE,
            )
            .order_by(Prescription.issued_at.desc())
        )

    wanted_items: list[PrescriptionItem] = []
    if prescription:
        wanted_items = db.scalars(
            select(PrescriptionItem).where(PrescriptionItem.prescription_id == prescription.id)
        ).all()
    wanted_names = [i.medicine_name.lower() for i in wanted_items]

    pharmacies = db.scalars(select(Pharmacy)).all()
    heuristic: dict[int, tuple[float, str]] = {}
    distances: dict[int, float | None] = {}
    quotes: dict[int, float | None] = {}
    missing_map: dict[int, list[str]] = {}
    candidates: list[dict[str, Any]] = []

    for pharmacy in pharmacies:
        stock = db.scalars(
            select(PharmacyItem).where(PharmacyItem.pharmacy_id == pharmacy.id)
        ).all()
        by_name = {s.medicine_name.lower(): s for s in stock}

        total = 0.0
        missing: list[str] = []
        for item in wanted_items:
            match = by_name.get(item.medicine_name.lower())
            if match and match.stock_qty > 0:
                total += match.selling_price * (item.quantity or 1)
            else:
                missing.append(item.medicine_name)

        quote = round(total, 2) if wanted_items and len(missing) < len(wanted_items) else None
        coverage = 1 - (len(missing) / len(wanted_names)) if wanted_names else 1.0

        distance = haversine_km(
            patient.latitude, patient.longitude, pharmacy.latitude, pharmacy.longitude
        )
        distances[pharmacy.id] = distance
        quotes[pharmacy.id] = quote
        missing_map[pharmacy.id] = missing

        score = coverage * 40
        reasons: list[str] = []
        if wanted_names:
            reasons.append(
                "Every medicine in stock" if not missing else f"{len(missing)} item(s) unavailable"
            )
        score += pharmacy.rating_avg * 5
        if pharmacy.delivers:
            score += 6
            reasons.append(f"Delivers in ~{pharmacy.avg_delivery_minutes} min")
        if pharmacy.is_24x7:
            score += 4
            reasons.append("Open 24×7")
        if distance is not None:
            score += max(0, 15 - distance * 1.5)
            reasons.append(f"{distance} km away")

        candidates.append(
            {
                "id": pharmacy.id,
                "quoted_total": quote,
                "coverage": coverage,
                "rating_avg": pharmacy.rating_avg,
                "delivers": pharmacy.delivers,
                "distance_km": distance,
            }
        )
        heuristic[pharmacy.id] = (round(score, 2), " · ".join(reasons) or "Stocks common medicines")

    priced = [(pid, q) for pid, q in quotes.items() if q is not None and not missing_map[pid]]
    if priced:
        cheapest = min(q for _, q in priced)
        dearest = max(q for _, q in priced)
        spread = dearest - cheapest
        for pid, quote in priced:
            bonus = 25.0 if spread == 0 else 25 * (1 - (quote - cheapest) / spread)
            score, reason = heuristic[pid]
            if quote == cheapest and spread > 0:
                reason = f"Cheapest full order at ₹{quote:,.0f} · {reason}"
            heuristic[pid] = (round(score + bonus, 2), reason)

    scores, version = _apply_ranking(
        "pharmacy",
        candidates,
        patient_features(db, patient),
        {"prescription_id": prescription.id if prescription else None},
        heuristic,
    )
    ranked = sorted(pharmacies, key=lambda p: scores.get(p.id, (0, ""))[0], reverse=True)[:limit]
    return (
        [
            (
                p,
                scores.get(p.id, (0, ""))[0],
                scores.get(p.id, (0, ""))[1],
                distances.get(p.id),
                quotes.get(p.id),
                missing_map.get(p.id, []),
            )
            for p in ranked
        ],
        version,
    )


def recommend_hospitals(
    db: Session, patient: PatientProfile, limit: int = 5, need: str | None = None
) -> tuple[list[tuple[Hospital, float, str, float | None]], str]:
    hospitals = db.scalars(select(Hospital)).all()
    heuristic: dict[int, tuple[float, str]] = {}
    distances: dict[int, float | None] = {}
    candidates: list[dict[str, Any]] = []
    need_lower = (need or "").lower()

    for hospital in hospitals:
        distance = haversine_km(
            patient.latitude, patient.longitude, hospital.latitude, hospital.longitude
        )
        distances[hospital.id] = distance

        score = hospital.rating_avg * 8
        reasons: list[str] = []

        if need_lower and hospital.specializations and need_lower in hospital.specializations.lower():
            score += 30
            reasons.append(f"Treats {need}")
        if hospital.has_emergency:
            score += 8
            reasons.append("24×7 emergency")
        if hospital.icu_bed_count:
            score += min(hospital.icu_bed_count, 40) * 0.3
        if distance is not None:
            score += max(0, 25 - distance)
            reasons.append(f"{distance} km away")
        if hospital.avg_consultation_fee:
            score += max(0, 12 - hospital.avg_consultation_fee / 100)

        candidates.append(
            {
                "id": hospital.id,
                "rating_avg": hospital.rating_avg,
                "specializations": hospital.specializations,
                "bed_count": hospital.bed_count,
                "icu_bed_count": hospital.icu_bed_count,
                "avg_consultation_fee": hospital.avg_consultation_fee,
                "distance_km": distance,
            }
        )
        heuristic[hospital.id] = (round(score, 2), " · ".join(reasons) or "Multi-speciality care")

    scores, version = _apply_ranking(
        "hospital", candidates, patient_features(db, patient), {"need": need}, heuristic
    )
    ranked = sorted(hospitals, key=lambda h: scores.get(h.id, (0, ""))[0], reverse=True)[:limit]
    return (
        [(h, scores.get(h.id, (0, ""))[0], scores.get(h.id, (0, ""))[1], distances.get(h.id)) for h in ranked],
        version,
    )


def recommend_insurance(
    db: Session, patient: PatientProfile, limit: int = 5
) -> tuple[list[tuple[InsurancePlan, float, str, str | None]], str]:
    plans = db.scalars(select(InsurancePlan).where(InsurancePlan.is_active.is_(True))).all()
    has_chronic = bool(
        db.scalar(
            select(Condition.id).where(
                Condition.patient_id == patient.id,
                Condition.category == "chronic",
                Condition.status != ConditionStatus.RESOLVED,
            )
        )
    )

    heuristic: dict[int, tuple[float, str]] = {}
    insurer_names: dict[int, str | None] = {}
    candidates: list[dict[str, Any]] = []

    for plan in plans:
        insurer = db.get(Insurer, plan.insurer_id)
        insurer_names[plan.id] = insurer.name if insurer else None

        score = 0.0
        reasons: list[str] = []

        # Cover per rupee of premium is the core value signal.
        if plan.annual_premium:
            value = plan.cover_amount / plan.annual_premium
            score += min(value, 60) * 0.8
            reasons.append(f"₹{plan.cover_amount:,.0f} cover for ₹{plan.annual_premium:,.0f}/yr")

        if has_chronic and plan.covers_pre_existing:
            score += 30
            reasons.append("Covers pre-existing conditions")
        elif has_chronic and plan.waiting_period_months > 24:
            score -= 15

        if insurer:
            score += insurer.claim_settlement_ratio * 0.25
            score += insurer.rating_avg * 4
            if insurer.claim_settlement_ratio >= 95:
                reasons.append(f"{insurer.claim_settlement_ratio}% claims settled")
        if plan.covers_opd:
            score += 6
            reasons.append("OPD covered")
        score += min(plan.network_hospital_count, 12000) / 1000

        candidates.append(
            {
                "id": plan.id,
                "cover_amount": plan.cover_amount,
                "annual_premium": plan.annual_premium,
                "covers_pre_existing": plan.covers_pre_existing,
                "waiting_period_months": plan.waiting_period_months,
                "network_hospital_count": plan.network_hospital_count,
                "claim_settlement_ratio": insurer.claim_settlement_ratio if insurer else 0,
            }
        )
        heuristic[plan.id] = (round(score, 2), " · ".join(reasons) or "Health cover")

    scores, version = _apply_ranking(
        "insurance",
        candidates,
        patient_features(db, patient),
        {"has_chronic_condition": has_chronic},
        heuristic,
    )
    ranked = sorted(plans, key=lambda p: scores.get(p.id, (0, ""))[0], reverse=True)[:limit]
    return (
        [
            (p, scores.get(p.id, (0, ""))[0], scores.get(p.id, (0, ""))[1], insurer_names.get(p.id))
            for p in ranked
        ],
        version,
    )

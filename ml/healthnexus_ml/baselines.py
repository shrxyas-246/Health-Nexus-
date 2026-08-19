"""The rule-based ranking the backend ships today, re-expressed over candidate dicts.

This is the number every model has to beat. ``backend/app/services/recommendations.py``
scores candidates with hand-tuned weights; the same weights are reproduced here so
training can report honest lift ("+X NDCG over the shipped heuristic") instead of
lift over a random ordering, which would mean nothing.

Keep in step with the backend if those weights are re-tuned.
"""

from __future__ import annotations

import numpy as np

from healthnexus_ml.knowledge import SEVERITY_WEIGHT, specialities_for


def _severity(patient: dict) -> int:
    return max(
        (
            SEVERITY_WEIGHT.get(str(c.get("severity") or "").lower(), 0)
            for c in (patient.get("conditions") or [])
        ),
        default=0,
    )


def _condition_names(patient: dict, context: dict) -> list[str]:
    return list(context.get("conditions") or []) or [
        c.get("name", "") for c in (patient.get("conditions") or [])
    ]


def doctor_scores(patient: dict, candidates: list[dict], context: dict) -> np.ndarray:
    wanted = specialities_for(_condition_names(patient, context))
    needs_specialist = _severity(patient) >= 2
    out = []
    for c in candidates:
        score = 0.0
        if c.get("specialization") in wanted:
            score += 45
        elif c.get("specialization") == "General Medicine":
            score += 20
        score += (c.get("rating_avg") or 0) * 6
        if (c.get("rating_count") or 0) >= 20:
            score += 5
        score += min(c.get("years_experience") or 0, 25) * 0.6

        if needs_specialist:
            if c.get("complex_case_success_rate"):
                score += (c["complex_case_success_rate"] - 80) * 1.5
            score += min(c.get("procedures_performed") or 0, 800) / 40
            if c.get("specialization") == "General Medicine" and wanted:
                score -= 25
            distance_weight = 0.4
        else:
            distance_weight = 1.0

        distance = c.get("distance_km")
        if distance is not None:
            score += max(0, 20 - distance) * distance_weight
        elif c.get("city") and c.get("city") == patient.get("city"):
            score += 10 * distance_weight
        if c.get("is_verified"):
            score += 5
        out.append(score)
    return np.array(out, dtype=float)


def hospital_scores(patient: dict, candidates: list[dict], context: dict) -> np.ndarray:
    need = str(context.get("need") or "").lower()
    out = []
    for c in candidates:
        score = (c.get("rating_avg") or 0) * 8
        if need and c.get("specializations") and need in str(c["specializations"]).lower():
            score += 30
        if c.get("has_emergency"):
            score += 8
        score += min(c.get("icu_bed_count") or 0, 40) * 0.3
        if c.get("surgery_success_rate"):
            score += (c["surgery_success_rate"] - 85) * 1.6
        score += min(c.get("complex_cases_handled") or 0, 5000) / 250
        if c.get("accreditation"):
            score += 6
        if c.get("distance_km") is not None:
            score += max(0, 25 - c["distance_km"])
        if c.get("avg_consultation_fee"):
            score += max(0, 12 - c["avg_consultation_fee"] / 100)
        out.append(score)
    return np.array(out, dtype=float)


def lab_scores(patient: dict, candidates: list[dict], context: dict) -> np.ndarray:
    out = []
    for c in candidates:
        score = (c.get("coverage") or 0) * 40
        score += (c.get("rating_avg") or 0) * 5
        if c.get("accreditation"):
            score += 8
        if c.get("home_collection"):
            score += 6
        if c.get("distance_km") is not None:
            score += max(0, 15 - c["distance_km"])
        out.append(score)
    out = np.array(out, dtype=float)
    return out + _cheapest_bonus(candidates)


def pharmacy_scores(patient: dict, candidates: list[dict], context: dict) -> np.ndarray:
    out = []
    for c in candidates:
        score = (c.get("coverage") or 0) * 40
        score += (c.get("rating_avg") or 0) * 5
        if c.get("delivers"):
            score += 6
        if c.get("is_24x7"):
            score += 4
        if c.get("distance_km") is not None:
            score += max(0, 15 - c["distance_km"] * 1.5)
        out.append(score)
    out = np.array(out, dtype=float)
    return out + _cheapest_bonus(candidates, require_full_coverage=True)


def _cheapest_bonus(candidates: list[dict], require_full_coverage: bool = False) -> np.ndarray:
    """The backend's explicit price bonus: 25 points to the cheapest quote, 0 to the dearest."""
    quotes = [
        (i, c.get("quoted_total"))
        for i, c in enumerate(candidates)
        if c.get("quoted_total") is not None
        and (not require_full_coverage or (c.get("coverage") or 0) >= 1.0)
    ]
    bonus = np.zeros(len(candidates))
    if not quotes:
        return bonus
    values = [q for _, q in quotes]
    cheapest, dearest = min(values), max(values)
    spread = dearest - cheapest
    for index, quote in quotes:
        bonus[index] = 25.0 if spread == 0 else 25 * (1 - (quote - cheapest) / spread)
    return bonus


def insurance_scores(patient: dict, candidates: list[dict], context: dict) -> np.ndarray:
    has_chronic = bool(context.get("has_chronic_condition"))
    out = []
    for c in candidates:
        score = 0.0
        if c.get("annual_premium"):
            score += min(c["cover_amount"] / c["annual_premium"], 60) * 0.8
        if has_chronic and c.get("covers_pre_existing"):
            score += 30
        elif has_chronic and (c.get("waiting_period_months") or 0) > 24:
            score -= 15
        score += (c.get("claim_settlement_ratio") or 0) * 0.25
        score += (c.get("insurer_rating") or 0) * 4
        if c.get("covers_opd"):
            score += 6
        score += min(c.get("network_hospital_count") or 0, 12000) / 1000
        out.append(score)
    return np.array(out, dtype=float)


SCORERS = {
    "doctor": doctor_scores,
    "hospital": hospital_scores,
    "lab": lab_scores,
    "pharmacy": pharmacy_scores,
    "insurance": insurance_scores,
}


def heuristic_scores(kind: str, patient: dict, candidates: list[dict], context: dict) -> np.ndarray:
    return SCORERS[kind](patient, candidates, context or {})

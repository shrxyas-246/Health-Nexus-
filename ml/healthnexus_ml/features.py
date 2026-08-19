"""Feature extraction for the model-3 recommenders.

The contract is fixed by the product backend: it POSTs ``/rank`` with a patient
feature bundle, a list of candidate dicts and a context dict (see
``backend/app/services/recommendations.py``). Everything in this module reads
that payload and nothing else, so the exact same code path runs during training
and during serving — the classic way ranking models drift is a feature computed
one way offline and another way online.

Two kinds of feature are produced:

* **Absolute** — the candidate's own numbers (rating, price, distance).
* **Relative** — the same numbers re-expressed against the rest of the candidate
  set for this one query (``__rel`` = min-max position, ``__rank`` = ordinal
  position). Ranking is a within-query decision, so "cheapest of the five
  offered" is far more predictive than "costs 1,240".

Missing values are left as NaN on purpose: the gradient-boosted trees handle
them natively, which means a lab with no price quote is ranked on its other
signals rather than being silently scored as zero.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from healthnexus_ml.knowledge import (
    SEVERITY_WEIGHT,
    SURGICAL_SPECIALITIES,
    specialities_for,
)


def _f(value: Any) -> float:
    """Coerce to float, mapping None/blank/non-numeric to NaN."""
    if value is None or value is False:
        return 0.0 if value is False else math.nan
    if value is True:
        return 1.0
    try:
        out = float(value)
    except (TypeError, ValueError):
        return math.nan
    return out if math.isfinite(out) else math.nan


def _log1p(value: Any) -> float:
    out = _f(value)
    return math.nan if math.isnan(out) else math.log1p(max(out, 0.0))


# Fields re-expressed relative to the rest of the candidate set, per kind.
RELATIVE_FIELDS: dict[str, tuple[str, ...]] = {
    "doctor": ("c_fee", "c_distance_km", "c_rating_avg", "c_success_rate"),
    "hospital": ("c_avg_consultation_fee", "c_distance_km", "c_rating_avg", "c_surgery_success_rate"),
    "lab": ("c_quoted_total", "c_distance_km", "c_rating_avg", "c_turnaround_hours"),
    "pharmacy": ("c_quoted_total", "c_distance_km", "c_rating_avg", "c_delivery_minutes"),
    "insurance": ("c_annual_premium", "c_cover_per_premium", "c_claim_settlement_ratio"),
}


# --- patient side ---------------------------------------------------------------


def patient_features(patient: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, float]:
    """Query-level features: the same for every candidate in one request."""
    context = context or {}
    conditions = patient.get("conditions") or []
    severities = [c.get("severity") for c in conditions if isinstance(c, dict)]
    categories = [str(c.get("category", "")).lower() for c in conditions if isinstance(c, dict)]

    severity = max(
        (SEVERITY_WEIGHT.get(str(s or "").lower(), 0) for s in severities), default=0
    )
    age = _f(patient.get("age"))
    return {
        "p_age": age,
        "p_age_over_60": 1.0 if (not math.isnan(age) and age >= 60) else 0.0,
        "p_bmi": _f(patient.get("bmi")),
        "p_is_premium": 1.0 if patient.get("is_premium") else 0.0,
        "p_n_conditions": float(len(conditions)),
        "p_severity": float(severity),
        "p_needs_specialist": 1.0 if severity >= 2 else 0.0,
        "p_has_chronic": 1.0 if ("chronic" in categories or context.get("has_chronic_condition")) else 0.0,
        "p_n_allergies": float(len(patient.get("allergies") or [])),
    }


def _condition_names(patient: dict[str, Any], context: dict[str, Any]) -> list[str]:
    names = list(context.get("conditions") or [])
    if not names:
        names = [
            c.get("name", "")
            for c in (patient.get("conditions") or [])
            if isinstance(c, dict)
        ]
    return [n for n in names if n]


# --- candidate side, one function per kind ---------------------------------------


def _doctor(cand: dict, patient: dict, context: dict, wanted: set[str]) -> dict[str, float]:
    speciality = cand.get("specialization") or ""
    return {
        "c_rating_avg": _f(cand.get("rating_avg")),
        "c_rating_count_log": _log1p(cand.get("rating_count")),
        "c_years_experience": _f(cand.get("years_experience")),
        "c_fee": _f(cand.get("consultation_fee")),
        "c_procedures_log": _log1p(cand.get("procedures_performed")),
        "c_success_rate": _f(cand.get("complex_case_success_rate")),
        "c_distance_km": _f(cand.get("distance_km")),
        "c_is_verified": 1.0 if cand.get("is_verified") else 0.0,
        "f_speciality_match": 1.0 if speciality in wanted else 0.0,
        "f_is_general": 1.0 if speciality == "General Medicine" else 0.0,
        "f_is_surgical": 1.0 if speciality in SURGICAL_SPECIALITIES else 0.0,
        "f_same_city": 1.0 if (cand.get("city") and cand.get("city") == patient.get("city")) else 0.0,
    }


def _hospital(cand: dict, patient: dict, context: dict, wanted: set[str]) -> dict[str, float]:
    specialisations = str(cand.get("specializations") or "")
    need = str(context.get("need") or "").strip().lower()
    listed = [s.strip().lower() for s in specialisations.split(",") if s.strip()]
    need_match = 1.0 if need and any(need in s or s in need for s in listed) else 0.0
    condition_match = 1.0 if any(
        w.lower() in specialisations.lower() for w in wanted
    ) else 0.0
    return {
        "c_rating_avg": _f(cand.get("rating_avg")),
        "c_bed_count": _f(cand.get("bed_count")),
        "c_icu_bed_count": _f(cand.get("icu_bed_count")),
        "c_surgery_success_rate": _f(cand.get("surgery_success_rate")),
        "c_complex_cases_log": _log1p(cand.get("complex_cases_handled")),
        "c_avg_consultation_fee": _f(cand.get("avg_consultation_fee")),
        "c_distance_km": _f(cand.get("distance_km")),
        "c_has_emergency": 1.0 if cand.get("has_emergency") else 0.0,
        "c_is_accredited": 1.0 if cand.get("accreditation") else 0.0,
        "c_n_specialities": float(len(listed)),
        "f_need_match": need_match,
        "f_condition_speciality_match": condition_match,
    }


def _lab(cand: dict, patient: dict, context: dict, wanted: set[str]) -> dict[str, float]:
    return {
        "c_quoted_total": _f(cand.get("quoted_total")),
        "c_coverage": _f(cand.get("coverage")),
        "c_rating_avg": _f(cand.get("rating_avg")),
        "c_home_collection": 1.0 if cand.get("home_collection") else 0.0,
        "c_distance_km": _f(cand.get("distance_km")),
        "c_is_accredited": 1.0 if cand.get("accreditation") else 0.0,
        "c_turnaround_hours": _f(cand.get("turnaround_hours")),
        "c_discount_percent": _f(cand.get("discount_percent")),
        "c_home_collection_fee": _f(cand.get("home_collection_fee")),
        "f_n_tests_requested": float(len(context.get("tests") or [])),
    }


def _pharmacy(cand: dict, patient: dict, context: dict, wanted: set[str]) -> dict[str, float]:
    return {
        "c_quoted_total": _f(cand.get("quoted_total")),
        "c_coverage": _f(cand.get("coverage")),
        "c_rating_avg": _f(cand.get("rating_avg")),
        "c_delivers": 1.0 if cand.get("delivers") else 0.0,
        "c_distance_km": _f(cand.get("distance_km")),
        "c_is_24x7": 1.0 if cand.get("is_24x7") else 0.0,
        "c_delivery_minutes": _f(cand.get("avg_delivery_minutes")),
        "c_delivery_fee": _f(cand.get("delivery_fee")),
        "f_full_basket": 1.0 if _f(cand.get("coverage")) >= 1.0 else 0.0,
    }


def _insurance(cand: dict, patient: dict, context: dict, wanted: set[str]) -> dict[str, float]:
    cover = _f(cand.get("cover_amount"))
    premium = _f(cand.get("annual_premium"))
    ratio = cover / premium if premium and not math.isnan(cover) and premium > 0 else math.nan
    has_chronic = 1.0 if context.get("has_chronic_condition") else 0.0
    covers_pre_existing = 1.0 if cand.get("covers_pre_existing") else 0.0
    waiting = _f(cand.get("waiting_period_months"))
    return {
        "c_cover_amount": cover,
        "c_annual_premium": premium,
        "c_cover_per_premium": ratio,
        "c_covers_pre_existing": covers_pre_existing,
        "c_covers_opd": 1.0 if cand.get("covers_opd") else 0.0,
        "c_covers_daycare": 1.0 if cand.get("covers_daycare") else 0.0,
        "c_waiting_period_months": waiting,
        "c_network_hospital_count": _f(cand.get("network_hospital_count")),
        "c_claim_settlement_ratio": _f(cand.get("claim_settlement_ratio")),
        "c_insurer_rating": _f(cand.get("insurer_rating")),
        "c_room_rent_limit": _f(cand.get("room_rent_limit")),
        "x_chronic_x_pre_existing": has_chronic * covers_pre_existing,
        "x_chronic_x_waiting": has_chronic * (0.0 if math.isnan(waiting) else waiting),
    }


_EXTRACTORS = {
    "doctor": _doctor,
    "hospital": _hospital,
    "lab": _lab,
    "pharmacy": _pharmacy,
    "insurance": _insurance,
}


# --- assembly -------------------------------------------------------------------


def _add_relative(frame: pd.DataFrame, kind: str) -> pd.DataFrame:
    """Add within-query min-max position and ordinal rank for the key numerics."""
    for field in RELATIVE_FIELDS.get(kind, ()):
        if field not in frame.columns:
            continue
        column = frame[field].astype(float)
        low, high = column.min(), column.max()
        if pd.isna(low) or pd.isna(high) or high == low:
            frame[f"{field}__rel"] = np.where(column.isna(), np.nan, 0.5)
        else:
            frame[f"{field}__rel"] = (column - low) / (high - low)
        # Ordinal position, 0 = smallest. Scaled so it is comparable across
        # candidate sets of different sizes.
        ranks = column.rank(method="average", na_option="keep")
        denominator = max(column.notna().sum() - 1, 1)
        frame[f"{field}__rank"] = (ranks - 1) / denominator
    return frame


def build_frame(
    kind: str,
    patient: dict[str, Any],
    candidates: list[dict[str, Any]],
    context: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Featurise one ranking request. Row order matches ``candidates``."""
    if kind not in _EXTRACTORS:
        raise ValueError(f"unknown ranking kind: {kind!r}")
    context = context or {}
    extractor = _EXTRACTORS[kind]
    wanted = specialities_for(_condition_names(patient, context))
    shared = patient_features(patient, context)

    rows = []
    for cand in candidates:
        row = dict(shared)
        row.update(extractor(cand, patient, context, wanted))
        rows.append(row)

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame = _add_relative(frame, kind)

    # A handful of cross terms the trees would otherwise need many splits to
    # approximate: severity changes what a patient is willing to trade away.
    if kind == "doctor":
        frame["x_severity_x_success"] = frame["p_severity"] * frame["c_success_rate"].fillna(0)
        frame["x_severity_x_distance"] = frame["p_severity"] * frame["c_distance_km"].fillna(0)
        frame["x_premium_x_fee_rank"] = frame["p_is_premium"] * frame["c_fee__rank"].fillna(0.5)
    elif kind == "hospital":
        frame["x_severity_x_success"] = frame["p_severity"] * frame["c_surgery_success_rate"].fillna(0)
        frame["x_severity_x_icu"] = frame["p_severity"] * frame["c_icu_bed_count"].fillna(0)
    elif kind in {"lab", "pharmacy"}:
        frame["x_premium_x_price_rank"] = frame["p_is_premium"] * frame["c_quoted_total__rank"].fillna(0.5)

    return frame.astype(float)


def feature_names(kind: str) -> list[str]:
    """Column order for a kind, derived from a probe request (single source of truth)."""
    probe_patient = {
        "age": 40, "bmi": 24.0, "is_premium": True, "city": "Bengaluru",
        "conditions": [{"name": "Type 2 Diabetes", "category": "chronic", "severity": "moderate"}],
        "allergies": ["dust"],
    }
    probe_candidates = [{"id": 1}, {"id": 2}]
    return list(build_frame(kind, probe_patient, probe_candidates, {}).columns)

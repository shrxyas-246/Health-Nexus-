"""Human-readable explanations attached to every ranked result.

A recommendation a patient cannot interrogate is a recommendation they will not
act on, so each ranked item carries a short reason. These are derived from the
candidate's standing *within the set that was actually ranked* ("cheapest of the
six quoted", "nearest") plus the attributes the trained model leans on most, so
the text tracks the decision rather than being decoration.
"""

from __future__ import annotations

from typing import Any

from healthnexus_ml.knowledge import specialities_for


def _numbers(candidates: list[dict], key: str) -> list[float]:
    return [c[key] for c in candidates if isinstance(c.get(key), (int, float))]


def _is_min(candidate: dict, candidates: list[dict], key: str) -> bool:
    values = _numbers(candidates, key)
    value = candidate.get(key)
    return bool(values and isinstance(value, (int, float)) and value <= min(values) and len(values) > 1)


def _is_max(candidate: dict, candidates: list[dict], key: str) -> bool:
    values = _numbers(candidates, key)
    value = candidate.get(key)
    return bool(values and isinstance(value, (int, float)) and value >= max(values) and len(values) > 1)


def _money(value: float) -> str:
    return f"₹{value:,.0f}"


def explain(
    kind: str,
    candidate: dict[str, Any],
    candidates: list[dict[str, Any]],
    patient: dict[str, Any],
    context: dict[str, Any],
) -> str:
    parts: list[str] = []

    if kind == "doctor":
        wanted = specialities_for(
            context.get("conditions")
            or [c.get("name") for c in (patient.get("conditions") or [])]
        )
        speciality = candidate.get("specialization")
        if speciality in wanted:
            parts.append(f"Specialises in {speciality}")
        elif speciality:
            parts.append(speciality)
        if candidate.get("rating_avg"):
            parts.append(
                f"Rated {candidate['rating_avg']} by {candidate.get('rating_count', 0)} patients"
            )
        if (candidate.get("years_experience") or 0) >= 10:
            parts.append(f"{candidate['years_experience']} years experience")
        if (candidate.get("complex_case_success_rate") or 0) >= 90:
            parts.append(f"{candidate['complex_case_success_rate']}% success in complex cases")
        if _is_min(candidate, candidates, "distance_km"):
            parts.append("Closest to you")
        elif candidate.get("distance_km") is not None:
            parts.append(f"{candidate['distance_km']} km away")
        if _is_min(candidate, candidates, "consultation_fee"):
            parts.append(f"Lowest fee at {_money(candidate['consultation_fee'])}")

    elif kind == "hospital":
        need = context.get("need")
        if need and need.lower() in str(candidate.get("specializations", "")).lower():
            parts.append(f"Treats {need}")
        if candidate.get("accreditation"):
            parts.append(f"{candidate['accreditation']} accredited")
        if candidate.get("surgery_success_rate"):
            parts.append(f"{candidate['surgery_success_rate']}% surgical success rate")
        if candidate.get("has_emergency"):
            parts.append("24×7 emergency")
        if (candidate.get("icu_bed_count") or 0) > 0:
            parts.append(f"{candidate['icu_bed_count']} ICU beds")
        if candidate.get("distance_km") is not None:
            parts.append(f"{candidate['distance_km']} km away")

    elif kind == "lab":
        coverage = candidate.get("coverage")
        if coverage is not None:
            parts.append(
                "All requested tests available" if coverage >= 1 else f"{round(coverage * 100)}% of tests available"
            )
        if _is_min(candidate, candidates, "quoted_total") and candidate.get("quoted_total"):
            parts.append(f"Lowest price at {_money(candidate['quoted_total'])}")
        elif candidate.get("quoted_total"):
            parts.append(f"Quoted {_money(candidate['quoted_total'])}")
        if candidate.get("accreditation"):
            parts.append(f"{candidate['accreditation']} accredited")
        if candidate.get("home_collection"):
            parts.append("Home sample collection")
        if candidate.get("turnaround_hours"):
            parts.append(f"Reports in {candidate['turnaround_hours']}h")
        if candidate.get("distance_km") is not None:
            parts.append(f"{candidate['distance_km']} km away")

    elif kind == "pharmacy":
        coverage = candidate.get("coverage")
        if coverage is not None:
            parts.append(
                "Every medicine in stock" if coverage >= 1 else f"{round(coverage * 100)}% of the order in stock"
            )
        if _is_min(candidate, candidates, "quoted_total") and candidate.get("quoted_total"):
            parts.append(f"Cheapest full order at {_money(candidate['quoted_total'])}")
        elif candidate.get("quoted_total"):
            parts.append(f"Order total {_money(candidate['quoted_total'])}")
        if candidate.get("delivers") and candidate.get("avg_delivery_minutes"):
            parts.append(f"Delivers in ~{candidate['avg_delivery_minutes']} min")
        if candidate.get("is_24x7"):
            parts.append("Open 24×7")
        if candidate.get("distance_km") is not None:
            parts.append(f"{candidate['distance_km']} km away")

    elif kind == "insurance":
        if candidate.get("cover_amount") and candidate.get("annual_premium"):
            parts.append(
                f"{_money(candidate['cover_amount'])} cover for {_money(candidate['annual_premium'])}/yr"
            )
        if context.get("has_chronic_condition") and candidate.get("covers_pre_existing"):
            parts.append("Covers pre-existing conditions")
        if (candidate.get("claim_settlement_ratio") or 0) >= 95:
            parts.append(f"{candidate['claim_settlement_ratio']}% claims settled")
        if candidate.get("covers_opd"):
            parts.append("OPD covered")
        if _is_max(candidate, candidates, "network_hospital_count"):
            parts.append(f"{candidate['network_hospital_count']:,} network hospitals")

    return " · ".join(parts[:4]) or "Recommended for you"

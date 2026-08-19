"""A synthetic Health Nexus marketplace: patients, and the providers they choose between.

Why synthetic? The platform has no click log yet — the seed database holds a
handful of rows. So we simulate the marketplace and, crucially, simulate *how
patients choose*, then ask the model to recover that choice behaviour from the
observable features. Every entity here is emitted in exactly the dict shape the
backend sends to ``/rank``, so a model trained on this data consumes production
payloads unchanged.

The latent preference weights (`price_sensitivity`, `convenience_weight`,
`quality_weight`) are deliberately **not** exposed as features. They are only
partly predictable from what the platform can observe (premium status, age,
severity), which is what makes the task non-trivial and keeps the reported
metrics honest — a model that scored perfectly here would mean the labels were
a giveaway.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from healthnexus_ml.knowledge import SPECIALITIES, SPECIALITY_HINTS

CITIES = ("Bengaluru", "Mumbai", "Delhi", "Chennai", "Hyderabad", "Pune", "Kolkata")

CONDITION_POOL: tuple[tuple[str, str], ...] = (
    ("Type 2 Diabetes", "chronic"),
    ("Hypertension", "chronic"),
    ("High Cholesterol", "chronic"),
    ("Asthma", "chronic"),
    ("Hypothyroidism", "chronic"),
    ("Chronic Kidney Disease", "chronic"),
    ("Rheumatoid Arthritis", "chronic"),
    ("Migraine", "chronic"),
    ("Anxiety", "chronic"),
    ("Coronary Artery Disease", "chronic"),
    ("Dengue Fever", "acute"),
    ("Gastritis", "acute"),
    ("Lower Back Fracture", "acute"),
    ("Eczema", "acute"),
    ("Cataract", "acute"),
    ("Breast Cancer", "chronic"),
    ("Pregnancy", "acute"),
    ("Anaemia", "acute"),
)

SEVERITIES = ("mild", "moderate", "severe", "critical")
SEVERITY_P = (0.42, 0.36, 0.17, 0.05)

ALLERGY_POOL = ("Penicillin", "Dust", "Peanuts", "Sulfa drugs", "Lactose", "Pollen")

TEST_POOL = (
    "Complete Blood Count", "HbA1c", "Lipid Profile", "Thyroid Profile",
    "Liver Function Test", "Kidney Function Test", "Vitamin D", "Urine Routine",
)

ACCREDITATIONS_LAB = (None, "NABL", "NABL", "CAP")
ACCREDITATIONS_HOSP = (None, "NABH", "NABH", "JCI")


@dataclass
class Patient:
    """A simulated patient: the observable bundle plus the latent preferences."""

    payload: dict[str, Any]
    price_sensitivity: float
    convenience_weight: float
    quality_weight: float
    severity: int
    condition_names: list[str] = field(default_factory=list)


def make_patient(rng: np.random.Generator) -> Patient:
    age = int(np.clip(rng.normal(43, 17), 3, 92))
    is_premium = bool(rng.random() < 0.35)
    n_conditions = int(rng.choice([0, 1, 2, 3], p=[0.12, 0.45, 0.31, 0.12]))
    picked = rng.choice(len(CONDITION_POOL), size=n_conditions, replace=False) if n_conditions else []

    conditions = []
    for index in picked:
        name, category = CONDITION_POOL[int(index)]
        severity = str(rng.choice(SEVERITIES, p=SEVERITY_P))
        conditions.append(
            {"name": name, "category": category, "status": "active", "severity": severity}
        )

    from healthnexus_ml.knowledge import severity_score

    severity = severity_score([c["severity"] for c in conditions])

    # Latent taste. Premium subscribers and younger patients care less about
    # price; older and sicker patients weight quality and convenience up.
    price_sensitivity = float(
        np.clip(rng.beta(2.4, 2.0) - 0.22 * is_premium + 0.004 * (age - 43), 0.02, 1.0)
    )
    quality_weight = float(np.clip(rng.beta(2.6, 2.0) + 0.12 * severity, 0.05, 1.6))
    convenience_weight = float(np.clip(rng.beta(2.2, 2.4) + 0.006 * max(age - 55, 0), 0.05, 1.3))

    payload = {
        "patient_id": int(rng.integers(1, 10**6)),
        "age": age,
        "gender": str(rng.choice(["male", "female", "other"], p=[0.48, 0.49, 0.03])),
        "blood_group": str(rng.choice(["A+", "B+", "O+", "AB+", "O-"])),
        "bmi": round(float(np.clip(rng.normal(25.4, 4.6), 14.0, 46.0)), 1),
        "city": str(rng.choice(CITIES)),
        "latitude": None,
        "longitude": None,
        "is_premium": is_premium,
        "allergies": [
            str(a) for a in rng.choice(ALLERGY_POOL, size=int(rng.integers(0, 3)), replace=False)
        ],
        "conditions": conditions,
    }
    return Patient(
        payload=payload,
        price_sensitivity=price_sensitivity,
        convenience_weight=convenience_weight,
        quality_weight=quality_weight,
        severity=severity,
        condition_names=[c["name"] for c in conditions],
    )


def _distance(rng: np.random.Generator) -> float | None:
    # ~6% of providers have no geocode in practice; the model must cope.
    if rng.random() < 0.06:
        return None
    return round(float(np.clip(rng.gamma(2.0, 4.0), 0.3, 60.0)), 1)


def make_doctors(rng: np.random.Generator, n: int, patient: Patient) -> list[dict]:
    """Candidate doctors, seeded so relevant specialities actually appear."""
    wanted = sorted(
        {s for name in patient.condition_names for s in SPECIALITY_HINTS.get(_key(name), ())}
    )
    out = []
    for i in range(n):
        if wanted and i < max(1, n // 4):
            speciality = str(rng.choice(wanted))
        else:
            speciality = str(rng.choice(SPECIALITIES))
        experience = int(np.clip(rng.gamma(3.0, 4.0), 0, 45))
        rating = round(float(np.clip(rng.normal(4.1 + 0.012 * experience, 0.45), 2.2, 5.0)), 1)
        out.append(
            {
                "id": i + 1,
                "specialization": speciality,
                "rating_avg": rating,
                "rating_count": int(np.clip(rng.gamma(2.0, 40.0), 0, 900)),
                "years_experience": experience,
                "consultation_fee": float(
                    np.clip(rng.normal(600 + 26 * experience + 220 * (rating - 4), 250), 150, 3500)
                ).__round__(0),
                "procedures_performed": int(np.clip(rng.gamma(2.0, 90.0) * (1 + experience / 20), 0, 4000)),
                "complex_case_success_rate": round(
                    float(np.clip(rng.normal(88 + 0.18 * experience, 5.0), 55, 99.5)), 1
                ),
                "distance_km": _distance(rng),
                "city": str(rng.choice(CITIES, p=_city_bias(patient))),
                "is_verified": bool(rng.random() < 0.72),
            }
        )
    return out


def _key(condition_name: str) -> str:
    lowered = condition_name.lower()
    for keyword in SPECIALITY_HINTS:
        if keyword in lowered:
            return keyword
    return ""


def _city_bias(patient: Patient) -> list[float]:
    """Most candidates are in the patient's own city, as the backend query implies."""
    probabilities = [0.08] * len(CITIES)
    home = CITIES.index(patient.payload["city"])
    probabilities[home] = 1.0
    total = sum(probabilities)
    return [p / total for p in probabilities]


def make_hospitals(rng: np.random.Generator, n: int, patient: Patient) -> list[dict]:
    out = []
    for i in range(n):
        beds = int(np.clip(rng.gamma(2.5, 90.0), 20, 1200))
        specialities = sorted(
            {str(s) for s in rng.choice(SPECIALITIES, size=int(rng.integers(2, 8)), replace=True)}
        )
        out.append(
            {
                "id": i + 1,
                "rating_avg": round(float(np.clip(rng.normal(4.0, 0.5), 2.0, 5.0)), 1),
                "specializations": ",".join(specialities),
                "bed_count": beds,
                "icu_bed_count": int(beds * float(np.clip(rng.normal(0.11, 0.05), 0.0, 0.35))),
                "surgery_success_rate": round(float(np.clip(rng.normal(92, 4.5), 60, 99.8)), 1),
                "complex_cases_handled": int(np.clip(rng.gamma(2.0, 700.0), 0, 9000)),
                "avg_consultation_fee": float(np.clip(rng.normal(750, 320), 150, 2500)).__round__(0),
                "distance_km": _distance(rng),
                "has_emergency": bool(rng.random() < 0.8),
                "accreditation": rng.choice(ACCREDITATIONS_HOSP),
            }
        )
    return out


def make_labs(rng: np.random.Generator, n: int, patient: Patient, n_tests: int) -> list[dict]:
    """Labs quoting on one basket of tests; coverage and price move together."""
    base_price = float(np.clip(rng.normal(520, 130), 220, 1100)) * max(n_tests, 1)
    out = []
    for i in range(n):
        coverage = float(rng.choice([1.0, 1.0, 1.0, 0.75, 0.5, 0.25], p=[0.45, 0.15, 0.1, 0.15, 0.1, 0.05]))
        matched = max(round(coverage * n_tests), 0) if n_tests else 0
        quote = (
            round(base_price * coverage * float(np.clip(rng.normal(1.0, 0.22), 0.55, 1.7)), 2)
            if matched
            else None
        )
        out.append(
            {
                "id": i + 1,
                "quoted_total": quote,
                "coverage": coverage if n_tests else 1.0,
                "rating_avg": round(float(np.clip(rng.normal(4.1, 0.45), 2.2, 5.0)), 1),
                "accreditation": rng.choice(ACCREDITATIONS_LAB),
                "home_collection": bool(rng.random() < 0.55),
                "home_collection_fee": float(rng.choice([0, 0, 100, 150, 200])),
                "turnaround_hours": int(rng.choice([6, 12, 24, 24, 48, 72])),
                "discount_percent": float(rng.choice([0, 0, 5, 10, 15, 20, 25])),
                "distance_km": _distance(rng),
            }
        )
    return out


def make_pharmacies(rng: np.random.Generator, n: int, patient: Patient, n_items: int) -> list[dict]:
    base_price = float(np.clip(rng.normal(340, 110), 80, 900)) * max(n_items, 1)
    out = []
    for i in range(n):
        coverage = float(rng.choice([1.0, 1.0, 0.8, 0.66, 0.5, 0.0], p=[0.5, 0.14, 0.12, 0.12, 0.09, 0.03]))
        quote = (
            round(base_price * coverage * float(np.clip(rng.normal(1.0, 0.18), 0.6, 1.6)), 2)
            if coverage > 0 and n_items
            else None
        )
        delivers = bool(rng.random() < 0.78)
        out.append(
            {
                "id": i + 1,
                "quoted_total": quote,
                "coverage": coverage if n_items else 1.0,
                "rating_avg": round(float(np.clip(rng.normal(4.0, 0.5), 2.0, 5.0)), 1),
                "delivers": delivers,
                "delivery_fee": float(rng.choice([0, 0, 25, 40, 60])) if delivers else 0.0,
                "avg_delivery_minutes": int(np.clip(rng.normal(55, 25), 15, 180)) if delivers else None,
                "is_24x7": bool(rng.random() < 0.3),
                "distance_km": _distance(rng),
            }
        )
    return out


def make_insurance_plans(rng: np.random.Generator, n: int, patient: Patient) -> list[dict]:
    out = []
    for i in range(n):
        cover = float(rng.choice([300_000, 500_000, 500_000, 1_000_000, 1_500_000, 2_500_000]))
        # Premium scales with cover, sub-linearly, plus underwriting noise.
        premium = round(
            float(cover ** 0.72 * np.clip(rng.normal(0.55, 0.14), 0.28, 1.1)), 0
        )
        covers_pre_existing = bool(rng.random() < 0.4)
        out.append(
            {
                "id": i + 1,
                "cover_amount": cover,
                "annual_premium": premium,
                "covers_pre_existing": covers_pre_existing,
                "covers_opd": bool(rng.random() < 0.35),
                "covers_daycare": bool(rng.random() < 0.85),
                "waiting_period_months": int(
                    rng.choice([0, 12, 24, 36, 48], p=[0.15, 0.25, 0.3, 0.2, 0.1])
                ),
                "network_hospital_count": int(np.clip(rng.gamma(2.5, 2500.0), 300, 15000)),
                "claim_settlement_ratio": round(float(np.clip(rng.normal(92, 5.0), 60, 99.5)), 1),
                "insurer_rating": round(float(np.clip(rng.normal(4.0, 0.5), 2.0, 5.0)), 1),
                "room_rent_limit": float(rng.choice([0, 0, 3000, 5000, 8000])) or None,
            }
        )
    return out

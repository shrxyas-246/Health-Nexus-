"""Clinical vocabulary shared by the data generator, the features and the service.

Kept deliberately small and inspectable: every mapping here is a product rule a
clinician could review, not something learned. The models learn *weights*, not
which speciality treats which disease.
"""

from __future__ import annotations

# Condition keyword -> specialities that treat it. Mirrors (and extends) the
# backend heuristic so model features and fallback ranking agree on vocabulary.
SPECIALITY_HINTS: dict[str, tuple[str, ...]] = {
    "diabetes": ("Endocrinology", "General Medicine", "Diabetology"),
    "hypertension": ("Cardiology", "General Medicine"),
    "cholesterol": ("Cardiology", "General Medicine"),
    "cardiac": ("Cardiology", "Cardiothoracic Surgery"),
    "heart": ("Cardiology", "Cardiothoracic Surgery"),
    "asthma": ("Pulmonology", "General Medicine"),
    "copd": ("Pulmonology",),
    "thyroid": ("Endocrinology",),
    "arthritis": ("Rheumatology", "Orthopaedics"),
    "migraine": ("Neurology", "General Medicine"),
    "epilepsy": ("Neurology",),
    "anxiety": ("Psychiatry",),
    "depression": ("Psychiatry",),
    "pregnancy": ("Obstetrics & Gynaecology",),
    "fracture": ("Orthopaedics",),
    "kidney": ("Nephrology",),
    "renal": ("Nephrology",),
    "liver": ("Gastroenterology", "Hepatology"),
    "gastritis": ("Gastroenterology", "General Medicine"),
    "skin": ("Dermatology",),
    "eczema": ("Dermatology",),
    "cancer": ("Oncology",),
    "tumour": ("Oncology", "General Surgery"),
    "dengue": ("General Medicine", "Infectious Diseases"),
    "anaemia": ("General Medicine", "Haematology"),
    "cataract": ("Ophthalmology",),
}

SPECIALITIES: tuple[str, ...] = (
    "General Medicine", "Cardiology", "Endocrinology", "Pulmonology", "Neurology",
    "Orthopaedics", "Dermatology", "Gastroenterology", "Nephrology", "Oncology",
    "Psychiatry", "Obstetrics & Gynaecology", "Rheumatology", "Ophthalmology",
    "General Surgery", "Cardiothoracic Surgery", "Paediatrics",
)

SURGICAL_SPECIALITIES = frozenset(
    {"General Surgery", "Cardiothoracic Surgery", "Orthopaedics", "Oncology"}
)

# How severe a case is decides whether the ranking optimises for outcomes or for
# convenience and price. Same scale the backend heuristic uses.
SEVERITY_WEIGHT = {"mild": 0, "moderate": 1, "severe": 2, "critical": 3}

# Conditions that impose a dietary restriction, used by the wellness model's
# label generator and by the plan composer.
RESTRICTION_LABELS = (
    "sodium_limit",
    "sugar_limit",
    "saturated_fat_limit",
    "potassium_limit",
    "purine_limit",
    "caffeine_limit",
    "alcohol_avoid",
)

PLAN_ARCHETYPES = (
    "glycaemic_control",
    "blood_pressure_control",
    "lipid_control",
    "weight_loss",
    "weight_gain",
    "renal_protective",
    "post_surgical_recovery",
    "general_maintenance",
)

WORKOUT_INTENSITIES = ("gentle", "moderate", "vigorous")


def specialities_for(condition_names) -> set[str]:
    """Specialities implied by a list of free-text condition names."""
    hits: set[str] = set()
    for name in condition_names or []:
        lowered = str(name).lower()
        for keyword, specialities in SPECIALITY_HINTS.items():
            if keyword in lowered:
                hits.update(specialities)
    return hits


def severity_score(severities) -> int:
    """Worst severity across a patient's active conditions, 0..3."""
    return max(
        (SEVERITY_WEIGHT.get(str(s or "").lower(), 0) for s in (severities or [])),
        default=0,
    )

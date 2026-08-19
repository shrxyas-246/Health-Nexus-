"""Training data for model 2 — the premium daily diet / movement / lifestyle plan.

Honest framing, because it matters for how the metrics should be read: the
labels here are a **documented clinical policy**, not discovered medicine. A
dietitian's rules (Mifflin-St Jeor energy needs, protein targets by goal and
renal function, restriction sets by condition) generate the ground truth, then
three things make recovering it a real learning problem:

* **Missingness.** Real records are patchy — 30–60% of simulated patients have no
  HbA1c, no lipid panel or no creatinine on file. The model has to infer the
  right plan from proxies (medicines, diagnoses, BMI, age) when the decisive lab
  value simply is not there.
* **Clinician variation.** Each record is assigned a latent prescriber whose
  thresholds and calorie preferences differ, so identical patients get different
  plans depending on who saw them.
* **Label noise.** A few percent of archetype labels are flipped to a clinically
  adjacent choice.

So the model is not being asked to invent nutrition science. It is being asked to
apply a reviewed policy consistently across incomplete records — which is exactly
the failure mode of writing the policy as `if` statements in the API, where one
missing lab value drops a patient to a generic plan.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from healthnexus_ml.knowledge import PLAN_ARCHETYPES, RESTRICTION_LABELS

CONDITION_FLAGS = (
    "has_diabetes", "has_hypertension", "has_high_cholesterol", "has_ckd",
    "has_cad", "has_thyroid", "has_asthma", "has_arthritis", "has_gout",
    "has_anxiety", "has_liver_disease", "is_pregnant",
)

NUMERIC_FEATURES = (
    "age", "height_cm", "weight_kg", "bmi", "activity_level", "sleep_hours",
    "resting_hr", "systolic", "diastolic", "hba1c", "ldl", "creatinine",
    "haemoglobin", "n_medicines", "days_since_surgery", "smoker", "alcohol_units_week",
)

FEATURE_COLUMNS = tuple(NUMERIC_FEATURES) + CONDITION_FLAGS + ("is_male",)


def _maybe_missing(value: float, probability: float, rng) -> float:
    """Drop a value the way real records drop it — no test was ever ordered."""
    return np.nan if rng.random() < probability else value


def simulate_patients(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []

    for _ in range(n):
        age = int(np.clip(rng.normal(45, 18), 12, 92))
        is_male = bool(rng.random() < 0.5)
        height = float(np.clip(rng.normal(172 if is_male else 159, 7.5), 140, 198))
        bmi = float(np.clip(rng.normal(25.6, 5.0), 14.5, 47))
        weight = round(bmi * (height / 100) ** 2, 1)

        # Condition prevalence rises with age and BMI, as it does in reality.
        age_factor = (age - 30) / 60
        bmi_factor = (bmi - 24) / 12
        p = lambda base, a=0.0, b=0.0: float(  # noqa: E731
            np.clip(base + a * age_factor + b * bmi_factor, 0.005, 0.85)
        )

        has_diabetes = rng.random() < p(0.09, 0.22, 0.14)
        has_hypertension = rng.random() < p(0.12, 0.30, 0.16)
        has_high_cholesterol = rng.random() < p(0.10, 0.18, 0.14)
        has_ckd = rng.random() < p(0.02, 0.09, 0.02) or (has_diabetes and rng.random() < 0.10)
        has_cad = rng.random() < p(0.03, 0.14, 0.05)
        has_thyroid = rng.random() < p(0.07, 0.04, 0.03)
        has_asthma = rng.random() < 0.07
        has_arthritis = rng.random() < p(0.05, 0.20, 0.06)
        has_gout = rng.random() < p(0.02, 0.05, 0.04)
        has_anxiety = rng.random() < 0.11
        has_liver_disease = rng.random() < p(0.02, 0.03, 0.05)
        is_pregnant = (not is_male) and 18 <= age <= 44 and rng.random() < 0.06

        activity_level = int(rng.choice([0, 1, 2, 3], p=[0.24, 0.40, 0.26, 0.10]))
        smoker = float(rng.random() < (0.16 if is_male else 0.05))
        alcohol = float(np.clip(rng.gamma(1.2, 3.0) * (0 if is_pregnant else 1), 0, 40))
        sleep_hours = float(np.clip(rng.normal(6.9, 1.2), 3.0, 10.5))

        # Vitals and labs, correlated with the conditions that cause them.
        systolic = float(np.clip(rng.normal(118 + 22 * has_hypertension + 0.25 * age, 12), 88, 205))
        diastolic = float(np.clip(systolic * 0.63 + rng.normal(0, 6), 55, 125))
        resting_hr = float(np.clip(rng.normal(74 - 4 * activity_level, 9), 44, 118))
        hba1c = float(np.clip(rng.normal(5.4 + 2.3 * has_diabetes + 0.03 * bmi_factor, 0.7), 4.2, 14.0))
        ldl = float(np.clip(rng.normal(104 + 46 * has_high_cholesterol + 12 * has_cad, 26), 45, 260))
        creatinine = float(
            np.clip(rng.normal((1.02 if is_male else 0.85) + 1.5 * has_ckd, 0.22), 0.4, 7.5)
        )
        haemoglobin = float(
            np.clip(rng.normal((14.6 if is_male else 12.9) - 1.6 * has_ckd, 1.4), 6.0, 18.5)
        )

        n_medicines = int(
            np.clip(
                rng.poisson(
                    0.6
                    + 1.6 * has_diabetes
                    + 1.3 * has_hypertension
                    + 1.0 * has_high_cholesterol
                    + 1.2 * has_cad
                    + 1.1 * has_ckd
                ),
                0,
                14,
            )
        )
        days_since_surgery = (
            float(rng.integers(1, 120)) if rng.random() < 0.08 else np.nan
        )

        rows.append(
            {
                "age": age,
                "is_male": float(is_male),
                "height_cm": round(height, 1),
                "weight_kg": weight,
                "bmi": round(bmi, 1),
                "activity_level": activity_level,
                "sleep_hours": round(sleep_hours, 1),
                "smoker": smoker,
                "alcohol_units_week": round(alcohol, 1),
                # Labs are the values most often missing from a real record.
                "resting_hr": _maybe_missing(round(resting_hr), 0.25, rng),
                "systolic": _maybe_missing(round(systolic), 0.18, rng),
                "diastolic": _maybe_missing(round(diastolic), 0.18, rng),
                "hba1c": _maybe_missing(round(hba1c, 1), 0.45 if not has_diabetes else 0.18, rng),
                "ldl": _maybe_missing(round(ldl), 0.50, rng),
                "creatinine": _maybe_missing(round(creatinine, 2), 0.55 if not has_ckd else 0.20, rng),
                "haemoglobin": _maybe_missing(round(haemoglobin, 1), 0.40, rng),
                "n_medicines": n_medicines,
                "days_since_surgery": days_since_surgery,
                "has_diabetes": float(has_diabetes),
                "has_hypertension": float(has_hypertension),
                "has_high_cholesterol": float(has_high_cholesterol),
                "has_ckd": float(has_ckd),
                "has_cad": float(has_cad),
                "has_thyroid": float(has_thyroid),
                "has_asthma": float(has_asthma),
                "has_arthritis": float(has_arthritis),
                "has_gout": float(has_gout),
                "has_anxiety": float(has_anxiety),
                "has_liver_disease": float(has_liver_disease),
                "is_pregnant": float(is_pregnant),
            }
        )

    return pd.DataFrame(rows)


def _bmr(row, weight, height) -> float:
    """Mifflin-St Jeor resting energy expenditure."""
    return 10 * weight + 6.25 * height - 5 * row["age"] + (5 if row["is_male"] else -161)


ACTIVITY_FACTOR = {0: 1.2, 1: 1.375, 2: 1.55, 3: 1.725}


def label(frame: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Apply the clinical policy, with clinician variation and label noise."""
    rng = np.random.default_rng(seed + 1)
    n = len(frame)
    # Each record is attributed to one of eight prescribers with their own bias.
    clinician_calorie_bias = rng.normal(0, 90, size=8)
    clinician_strictness = rng.normal(0, 0.35, size=8)
    clinician = rng.integers(0, 8, size=n)

    archetypes, intensities, calories, proteins = [], [], [], []
    restrictions = {label_name: [] for label_name in RESTRICTION_LABELS}

    for i, row in frame.iterrows():
        strict = clinician_strictness[clinician[i]]
        post_op = not np.isnan(row["days_since_surgery"]) and row["days_since_surgery"] <= 60
        bmi = row["bmi"]

        # --- archetype: highest-priority clinical driver wins ---------------------
        if post_op:
            archetype = "post_surgical_recovery"
        elif row["has_ckd"] or (not np.isnan(row["creatinine"]) and row["creatinine"] > 1.6):
            archetype = "renal_protective"
        elif row["has_diabetes"] or (not np.isnan(row["hba1c"]) and row["hba1c"] >= 6.5):
            archetype = "glycaemic_control"
        elif row["has_cad"] or (not np.isnan(row["ldl"]) and row["ldl"] >= 160 + 20 * strict):
            archetype = "lipid_control"
        elif row["has_hypertension"] or (not np.isnan(row["systolic"]) and row["systolic"] >= 140):
            archetype = "blood_pressure_control"
        elif bmi >= 27.5 - strict:
            archetype = "weight_loss"
        elif bmi < 18.5 + 0.5 * strict:
            archetype = "weight_gain"
        elif row["has_high_cholesterol"]:
            archetype = "lipid_control"
        else:
            archetype = "general_maintenance"

        # 4% of plans go to a clinically adjacent archetype — genuine disagreement.
        if rng.random() < 0.04:
            archetype = str(rng.choice(PLAN_ARCHETYPES))

        # --- energy and protein ---------------------------------------------------
        bmr = _bmr(row, row["weight_kg"], row["height_cm"])
        maintenance = bmr * ACTIVITY_FACTOR[int(row["activity_level"])]
        if archetype == "weight_loss":
            target = maintenance - 480
        elif archetype == "weight_gain":
            target = maintenance + 420
        elif archetype == "post_surgical_recovery":
            target = maintenance + 260
        elif archetype == "glycaemic_control":
            target = maintenance - 180
        else:
            target = maintenance
        if row["is_pregnant"]:
            target += 340
        target += clinician_calorie_bias[clinician[i]] + rng.normal(0, 70)
        calories.append(float(np.clip(round(target / 10) * 10, 1200, 4200)))

        if archetype == "renal_protective":
            protein_per_kg = 0.7
        elif archetype in {"post_surgical_recovery", "weight_loss"}:
            protein_per_kg = 1.55
        elif archetype == "weight_gain":
            protein_per_kg = 1.7
        elif row["age"] >= 65:
            protein_per_kg = 1.2
        else:
            protein_per_kg = 1.0
        if row["is_pregnant"]:
            protein_per_kg += 0.25
        reference_weight = (
            row["weight_kg"] if bmi < 30 else 24 * (row["height_cm"] / 100) ** 2
        )
        proteins.append(
            float(np.clip(round(reference_weight * protein_per_kg + rng.normal(0, 4)), 35, 190))
        )

        # --- restrictions (multi-label) -------------------------------------------
        flags = {
            "sodium_limit": bool(
                row["has_hypertension"] or row["has_ckd"] or row["has_cad"]
                or (not np.isnan(row["systolic"]) and row["systolic"] >= 135)
            ),
            "sugar_limit": bool(
                row["has_diabetes"] or bmi >= 27.5
                or (not np.isnan(row["hba1c"]) and row["hba1c"] >= 6.0)
            ),
            "saturated_fat_limit": bool(
                row["has_high_cholesterol"] or row["has_cad"]
                or (not np.isnan(row["ldl"]) and row["ldl"] >= 130)
            ),
            "potassium_limit": bool(
                row["has_ckd"] or (not np.isnan(row["creatinine"]) and row["creatinine"] > 1.8)
            ),
            "purine_limit": bool(row["has_gout"]),
            "caffeine_limit": bool(
                row["has_anxiety"] or row["sleep_hours"] < 6.0 or row["is_pregnant"]
            ),
            "alcohol_avoid": bool(
                row["has_liver_disease"] or row["is_pregnant"] or row["has_ckd"]
                or row["n_medicines"] >= 5
            ),
        }
        for name, value in flags.items():
            # 3% observation noise per label: advice given but not recorded.
            restrictions[name].append(float(value != (rng.random() < 0.03)))

        # --- workout intensity ----------------------------------------------------
        if post_op or row["age"] >= 75 or row["has_ckd"] or row["has_cad"] or row["is_pregnant"]:
            intensity = "gentle"
        elif row["age"] <= 45 and bmi < 30 and row["activity_level"] >= 2 and not row["has_arthritis"]:
            intensity = "vigorous"
        else:
            intensity = "moderate"
        if rng.random() < 0.05:
            intensity = str(rng.choice(["gentle", "moderate", "vigorous"]))
        intensities.append(intensity)
        archetypes.append(archetype)

    labels = pd.DataFrame(
        {
            "archetype": archetypes,
            "workout_intensity": intensities,
            "calorie_target": calories,
            "protein_g": proteins,
        }
    )
    for name, values in restrictions.items():
        labels[name] = values
    return labels


def build_dataset(n: int, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    features = simulate_patients(n, seed)
    labels = label(features, seed)
    return features[list(FEATURE_COLUMNS)], labels

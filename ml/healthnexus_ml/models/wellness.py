"""Model 2 — the premium daily diet, movement and lifestyle plan.

Five heads over one shared feature row, each doing the job it is best suited to:

* ``archetype``   — multiclass: which plan this patient is on today.
* ``intensity``   — multiclass: how hard they should train.
* ``calories``    — regression: daily energy target, in kcal.
* ``protein``     — regression: daily protein target, in grams.
* ``restrictions``— seven independent binary heads (sodium, sugar, saturated fat,
  potassium, purine, caffeine, alcohol). Independent rather than multiclass
  because a renal patient can easily need four of them at once.

Gradient-boosted trees throughout, for the same reason as the ranker: patient
records arrive with holes in them, and these handle NaN natively instead of
forcing an imputation that would quietly invent a lab result.

The heads produce *numbers and flags*. ``compose_plan`` turns those into the
three cards the Plus tab renders. Keeping generation separate from prediction is
deliberate — the text a patient reads is reviewable copy, not model output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

from healthnexus_ml.config import WELLNESS_VERSION
from healthnexus_ml.datagen.wellness import FEATURE_COLUMNS
from healthnexus_ml.knowledge import RESTRICTION_LABELS
from healthnexus_ml.models import registry

# --- mapping a live patient record onto the training feature row ------------------

CONDITION_KEYWORDS = {
    "has_diabetes": ("diabet", "sugar"),
    "has_hypertension": ("hypertens", "blood pressure", "bp"),
    "has_high_cholesterol": ("cholesterol", "dyslipid", "lipid"),
    "has_ckd": ("kidney", "renal", "ckd", "nephro"),
    "has_cad": ("coronary", "cardiac", "heart", "angina", "myocardial"),
    "has_thyroid": ("thyroid",),
    "has_asthma": ("asthma", "copd"),
    "has_arthritis": ("arthrit", "joint"),
    "has_gout": ("gout",),
    "has_anxiety": ("anxiety", "depress", "panic", "insomnia"),
    "has_liver_disease": ("liver", "hepat", "cirrho"),
    "is_pregnant": ("pregnan",),
}

# Vital name in the product record -> feature column.
VITAL_ALIASES = {
    "systolic": "systolic",
    "bp_systolic": "systolic",
    "diastolic": "diastolic",
    "bp_diastolic": "diastolic",
    "heart_rate": "resting_hr",
    "pulse": "resting_hr",
    "resting_hr": "resting_hr",
    "hba1c": "hba1c",
    "ldl": "ldl",
    "cholesterol_ldl": "ldl",
    "creatinine": "creatinine",
    "haemoglobin": "haemoglobin",
    "hemoglobin": "haemoglobin",
}


def features_from_record(record: dict[str, Any]) -> pd.DataFrame:
    """Build the model's feature row from the backend's patient bundle.

    Everything is optional. A record with nothing but an age still produces a
    plan — that is the whole point of using models that accept NaN.
    """
    row = {name: np.nan for name in FEATURE_COLUMNS}

    row["age"] = _num(record.get("age"))
    gender = str(record.get("gender") or "").lower()
    row["is_male"] = 1.0 if gender.startswith("m") else 0.0
    row["height_cm"] = _num(record.get("height_cm"))
    row["weight_kg"] = _num(record.get("weight_kg"))
    bmi = _num(record.get("bmi"))
    if np.isnan(bmi) and not np.isnan(row["height_cm"]) and not np.isnan(row["weight_kg"]):
        bmi = row["weight_kg"] / (row["height_cm"] / 100) ** 2
    row["bmi"] = bmi
    row["activity_level"] = _num(record.get("activity_level"), default=1.0)
    row["sleep_hours"] = _num(record.get("sleep_hours"), default=7.0)
    row["smoker"] = 1.0 if record.get("smoker") else 0.0
    row["alcohol_units_week"] = _num(record.get("alcohol_units_week"), default=0.0)
    row["n_medicines"] = float(len(record.get("medicines") or []))
    row["days_since_surgery"] = _num(record.get("days_since_surgery"))

    for key, value in (record.get("vitals") or {}).items():
        column = VITAL_ALIASES.get(str(key).lower())
        if column:
            row[column] = _num(value)

    condition_text = " ".join(
        str(c.get("name", "") if isinstance(c, dict) else c).lower()
        for c in (record.get("conditions") or [])
    )
    for column, keywords in CONDITION_KEYWORDS.items():
        row[column] = 1.0 if any(k in condition_text for k in keywords) else 0.0

    return pd.DataFrame([row])[list(FEATURE_COLUMNS)]


def _num(value: Any, default: float = np.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if np.isfinite(out) else default


# --- the model --------------------------------------------------------------------


@dataclass
class WellnessModel:
    archetype_clf: HistGradientBoostingClassifier
    intensity_clf: HistGradientBoostingClassifier
    calorie_reg: HistGradientBoostingRegressor
    protein_reg: HistGradientBoostingRegressor
    restriction_clfs: dict[str, HistGradientBoostingClassifier]
    features: list[str] = field(default_factory=lambda: list(FEATURE_COLUMNS))
    metrics: dict[str, Any] = field(default_factory=dict)
    version: str = WELLNESS_VERSION
    trained_at: str = ""

    def predict(self, frame: pd.DataFrame) -> dict[str, Any]:
        """Raw model outputs for one patient row."""
        X = frame.reindex(columns=self.features)
        archetype_proba = self.archetype_clf.predict_proba(X)[0]
        archetype_index = int(np.argmax(archetype_proba))
        intensity_proba = self.intensity_clf.predict_proba(X)[0]

        restrictions = {}
        for name, clf in self.restriction_clfs.items():
            probability = float(clf.predict_proba(X)[0][list(clf.classes_).index(1.0)]) \
                if 1.0 in list(clf.classes_) else 0.0
            restrictions[name] = {"flag": probability >= 0.5, "probability": round(probability, 3)}

        return {
            "archetype": str(self.archetype_clf.classes_[archetype_index]),
            "archetype_confidence": round(float(archetype_proba[archetype_index]), 3),
            "workout_intensity": str(self.intensity_clf.classes_[int(np.argmax(intensity_proba))]),
            "calorie_target": int(round(float(self.calorie_reg.predict(X)[0]) / 10) * 10),
            "protein_g": int(round(float(self.protein_reg.predict(X)[0]))),
            "restrictions": restrictions,
            "model_version": self.version,
        }

    def plan(self, record: dict[str, Any]) -> dict[str, Any]:
        """End-to-end: patient record in, the three Plus cards out."""
        prediction = self.predict(features_from_record(record))
        return compose_plan(prediction, record)


# --- plan composition -------------------------------------------------------------

ARCHETYPE_TITLES = {
    "glycaemic_control": "Steady blood sugar today",
    "blood_pressure_control": "Bring your blood pressure down",
    "lipid_control": "Heart-friendly eating today",
    "weight_loss": "A gentle calorie deficit today",
    "weight_gain": "Build back up today",
    "renal_protective": "Kidney-protective eating today",
    "post_surgical_recovery": "Recovery fuel today",
    "general_maintenance": "Keep your good habits going",
}

ARCHETYPE_RATIONALE = {
    "glycaemic_control": "Built around keeping post-meal glucose flat: paced carbohydrate, protein at every meal, and a short walk after eating.",
    "blood_pressure_control": "Built around lowering sodium and raising potassium-rich produce, the two dietary changes with the clearest effect on blood pressure.",
    "lipid_control": "Built around swapping saturated fat for unsaturated fat and adding soluble fibre, which lowers LDL over weeks.",
    "weight_loss": "A modest deficit you can hold, with protein kept high so what you lose is fat rather than muscle.",
    "weight_gain": "A surplus built from calorie-dense whole foods and frequent meals rather than empty calories.",
    "renal_protective": "Protein moderated and potassium, phosphate and sodium kept in check to reduce the load on your kidneys.",
    "post_surgical_recovery": "Extra energy and protein while tissue repairs, with gentle movement to protect circulation.",
    "general_maintenance": "Nothing needs correcting today — this keeps the habits that are already working.",
}

MEALS: dict[str, dict[str, str]] = {
    "glycaemic_control": {
        "Breakfast": "Vegetable besan chilla or 2 eggs with one multigrain roti — protein first keeps the morning spike down.",
        "Lunch": "One cup brown rice or 2 rotis, dal, a large portion of sabzi, curd. Fill half the plate with vegetables before the carbohydrate.",
        "Snack": "A handful of roasted chana or 6–8 almonds with green tea.",
        "Dinner": "Grilled paneer, fish or chicken with sautéed vegetables and one roti. Finish eating 2–3 hours before bed.",
    },
    "blood_pressure_control": {
        "Breakfast": "Oats with milk, banana and flaxseed. No added salt at the table.",
        "Lunch": "Rice or roti with dal cooked light on salt, plenty of leafy greens, curd.",
        "Snack": "Fruit — orange, papaya or a banana — for potassium.",
        "Dinner": "Home-cooked vegetables and lentils. Skip pickle, papad, packaged snacks and restaurant food today.",
    },
    "lipid_control": {
        "Breakfast": "Oats or dalia with walnuts — soluble fibre plus unsaturated fat.",
        "Lunch": "Whole grains, rajma or chana, a big salad dressed with mustard or olive oil.",
        "Snack": "A small handful of unsalted nuts, or roasted makhana.",
        "Dinner": "Baked fish or soya with steamed vegetables. Keep ghee, butter, cream and fried food off the plate today.",
    },
    "weight_loss": {
        "Breakfast": "Eggs, sprouts or paneer with one slice of whole-grain toast — a high-protein start blunts hunger later.",
        "Lunch": "Half the plate vegetables, a quarter protein, a quarter grain. Eat slowly and stop at comfortably full.",
        "Snack": "Buttermilk, cucumber or a fruit — not biscuits.",
        "Dinner": "Soup plus a protein-heavy sabzi, one roti at most. Nothing after dinner.",
    },
    "weight_gain": {
        "Breakfast": "Full-fat milk with banana and peanut butter, plus poha or upma.",
        "Lunch": "Rice with dal and ghee, paneer or chicken, curd.",
        "Snack": "Dry fruit, a milkshake, or a peanut chikki — eat between meals, not instead of them.",
        "Dinner": "Two rotis with a protein curry and a glass of milk before bed.",
    },
    "renal_protective": {
        "Breakfast": "Poha or upma with limited salt. Check with your dietitian before adding a high-potassium fruit.",
        "Lunch": "Measured portion of rice with a moderate serving of dal, low-potassium vegetables such as bottle gourd or cabbage.",
        "Snack": "Apple or pear (lower potassium than banana or orange).",
        "Dinner": "A small portion of protein with a light vegetable. Keep total fluid to what your nephrologist has advised.",
    },
    "post_surgical_recovery": {
        "Breakfast": "Eggs or paneer with fruit and milk — protein supports wound healing.",
        "Lunch": "Rice or roti with dal, a protein portion, curd and cooked vegetables.",
        "Snack": "Milk, a protein shake or sprouts.",
        "Dinner": "Soft, well-cooked protein and vegetables. Keep fluids up and fibre steady to avoid constipation.",
    },
    "general_maintenance": {
        "Breakfast": "Whatever you normally eat, with a source of protein added.",
        "Lunch": "Half the plate vegetables and fruit, a quarter whole grains, a quarter protein.",
        "Snack": "Fruit or nuts.",
        "Dinner": "A home-cooked meal, finished a couple of hours before bed.",
    },
}

AVOID_TEXT = {
    "sodium_limit": "pickles, papad, packaged snacks, restaurant food (keep salt under 5 g)",
    "sugar_limit": "sweets, sugary drinks, fruit juice, refined flour",
    "saturated_fat_limit": "fried food, butter, cream, red meat, bakery items",
    "potassium_limit": "banana, orange, coconut water, tomato, potato (unless your nephrologist allows)",
    "purine_limit": "organ meat, red meat, shellfish, beer",
    "caffeine_limit": "coffee, strong tea and cola after 3 pm",
    "alcohol_avoid": "alcohol entirely",
}

WORKOUTS: dict[str, list[dict[str, Any]]] = {
    "gentle": [
        {"name": "Easy walk", "minutes": 20, "intensity": "gentle",
         "moves": ["flat ground", "conversational pace", "stop if breathless"]},
        {"name": "Mobility and breathing", "minutes": 10, "intensity": "gentle",
         "moves": ["ankle pumps", "shoulder rolls", "diaphragmatic breathing"]},
    ],
    "moderate": [
        {"name": "Brisk walk", "minutes": 30, "intensity": "moderate",
         "moves": ["5 min warm-up", "20 min brisk", "5 min cool-down"]},
        {"name": "Strength circuit", "minutes": 20, "intensity": "moderate",
         "moves": ["bodyweight squats", "wall push-ups", "glute bridges", "bird dog"]},
    ],
    "vigorous": [
        {"name": "Cardio session", "minutes": 35, "intensity": "vigorous",
         "moves": ["run, cycle or swim", "keep effort where talking is hard"]},
        {"name": "Full-body strength", "minutes": 30, "intensity": "vigorous",
         "moves": ["squats", "push-ups", "rows", "plank", "3 sets each"]},
    ],
}

LIFESTYLE_RULES: list[tuple[str, str, str]] = [
    ("sleep_short", "Get to bed 45 minutes earlier tonight",
     "Adds ~5 hours of sleep a week — the fastest lever you have on appetite, blood pressure and mood."),
    ("smoker", "Set a quit date this week and tell one person about it",
     "Blood pressure and circulation start improving within weeks; quit attempts that are announced are roughly twice as likely to stick."),
    ("sedentary", "Take a 10-minute walk after your largest meal",
     "Cuts the post-meal glucose peak measurably and is far easier to keep up than a gym plan."),
    ("alcohol", "Keep three days this week completely alcohol-free",
     "Lowers blood pressure and liver strain, and improves sleep quality within days."),
    ("hydration", "Keep a filled bottle at your desk and finish it twice",
     "Steady hydration reduces the headaches and afternoon fatigue that get blamed on other things."),
    ("stress", "Take ten slow breaths before your first task and after your last",
     "Two minutes of paced breathing lowers heart rate and blunts the stress response."),
]


def compose_plan(prediction: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    """Turn model outputs into the three cards the Plus tab renders."""
    archetype = prediction["archetype"]
    restrictions = [
        name for name, value in prediction["restrictions"].items() if value["flag"]
    ]
    weight = _num(record.get("weight_kg"))
    litres = 2.5 if np.isnan(weight) else round(np.clip(weight * 0.033, 1.8, 4.0), 1)

    diet = {
        "kind": "diet",
        "title": ARCHETYPE_TITLES.get(archetype, "Today's eating plan"),
        "rationale": ARCHETYPE_RATIONALE.get(archetype, ""),
        "score": prediction["archetype_confidence"],
        "payload": {
            "archetype": archetype,
            "targets": {
                "kcal_a_day": prediction["calorie_target"],
                "g_protein": prediction["protein_g"],
                "litres_water": litres,
            },
            "meals": MEALS.get(archetype, MEALS["general_maintenance"]),
            "avoid": [AVOID_TEXT[name] for name in restrictions if name in AVOID_TEXT],
            "restrictions": restrictions,
        },
    }

    intensity = prediction["workout_intensity"]
    workout = {
        "kind": "workout",
        "title": {
            "gentle": "Keep moving, gently",
            "moderate": "Today's movement",
            "vigorous": "Push a little today",
        }[intensity],
        "rationale": _workout_rationale(intensity, archetype),
        "score": prediction["archetype_confidence"],
        "payload": {
            "intensity": intensity,
            "sessions": WORKOUTS[intensity],
            "weekly_target_minutes": {"gentle": 90, "moderate": 150, "vigorous": 210}[intensity],
        },
    }

    change, effect = _pick_lifestyle(record, prediction)
    lifestyle = {
        "kind": "lifestyle",
        "title": "One change worth making",
        "rationale": "Chosen as the single highest-return habit change for your current record.",
        "score": prediction["archetype_confidence"],
        "payload": {"change": change, "expected_effect": effect},
    }

    return {
        "model_version": prediction["model_version"],
        "prediction": prediction,
        "cards": [diet, workout, lifestyle],
    }


def _workout_rationale(intensity: str, archetype: str) -> str:
    if intensity == "gentle":
        return (
            "Your record points to taking it easy right now — circulation and mobility "
            "matter more than intensity. Stop at any pain or breathlessness."
        )
    if intensity == "vigorous":
        return "You have the fitness base for harder work — keep one full rest day this week."
    if archetype == "glycaemic_control":
        return "Movement after meals is doing double duty here: it lowers the post-meal glucose peak directly."
    return "Enough to hit the weekly activity target without needing a gym."


def _pick_lifestyle(record: dict[str, Any], prediction: dict[str, Any]) -> tuple[str, str]:
    sleep = _num(record.get("sleep_hours"), default=7.0)
    activity = _num(record.get("activity_level"), default=1.0)
    alcohol = _num(record.get("alcohol_units_week"), default=0.0)
    restrictions = prediction["restrictions"]

    if record.get("smoker"):
        key = "smoker"
    elif sleep < 6.5:
        key = "sleep_short"
    elif alcohol >= 7 or restrictions.get("alcohol_avoid", {}).get("flag"):
        key = "alcohol"
    elif activity <= 1:
        key = "sedentary"
    elif restrictions.get("caffeine_limit", {}).get("flag"):
        key = "stress"
    else:
        key = "hydration"
    change, effect = next((c, e) for k, c, e in LIFESTYLE_RULES if k == key)
    return change, effect


# --- training ---------------------------------------------------------------------


def _classifier(seed: int) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        max_iter=350,
        learning_rate=0.07,
        max_leaf_nodes=31,
        min_samples_leaf=20,
        l2_regularization=1.0,
        early_stopping=True,
        n_iter_no_change=20,
        random_state=seed,
    )


def _regressor(seed: int) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        max_iter=400,
        learning_rate=0.06,
        max_leaf_nodes=31,
        min_samples_leaf=20,
        l2_regularization=1.0,
        early_stopping=True,
        n_iter_no_change=25,
        random_state=seed,
    )


def train_wellness(X: pd.DataFrame, y: pd.DataFrame, seed: int = 0) -> WellnessModel:
    archetype_clf = _classifier(seed).fit(X, y["archetype"])
    intensity_clf = _classifier(seed).fit(X, y["workout_intensity"])
    calorie_reg = _regressor(seed).fit(X, y["calorie_target"])
    protein_reg = _regressor(seed).fit(X, y["protein_g"])
    restriction_clfs = {
        name: _classifier(seed).fit(X, y[name]) for name in RESTRICTION_LABELS
    }
    return WellnessModel(
        archetype_clf=archetype_clf,
        intensity_clf=intensity_clf,
        calorie_reg=calorie_reg,
        protein_reg=protein_reg,
        restriction_clfs=restriction_clfs,
        features=list(X.columns),
        trained_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )


ARTIFACT = "wellness"


def save_wellness(model: WellnessModel):
    return registry.save(ARTIFACT, model)


def load_wellness() -> WellnessModel:
    return registry.load(ARTIFACT)

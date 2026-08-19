"""Model 1 — the general health-guidance assistant.

Two classifier heads over the same text:

1. **Intent** (29 classes) picks which piece of guidance to give.
2. **Urgency** (routine / see_doctor / emergency) decides whether guidance is
   appropriate at all.

Both use a word + character n-gram TF-IDF union. Character n-grams are what make
this hold up against how patients actually type — "hedache", "bukhaar", "chst
pain" all still land, where a word-only model would miss them.

Safety design, in order of precedence at serving time:

1. A deterministic red-flag phrase list. If it fires, the model's opinion is
   irrelevant and the answer is "get emergency care now". Rules first, model
   second, because the cost of a missed emergency is not symmetric with the cost
   of a false alarm.
2. The urgency head. `emergency` escalates; `see_doctor` appends a "get this
   looked at" line to the answer.
3. Low intent confidence falls back to a safe capabilities message rather than
   guessing.

The assistant never diagnoses, never names a drug or dose to start or stop, and
every non-trivial answer carries the disclaimer. That is a product requirement,
not a model one, so it is enforced in code here rather than left to the corpus.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from healthnexus_ml.config import TRIAGE_VERSION
from healthnexus_ml.models import registry

DISCLAIMER = (
    "This is general guidance, not a diagnosis. For anything specific to your "
    "condition, your doctor is one tap away in the app."
)

SEE_DOCTOR_LINE = (
    "Given what you've described, please get this looked at by a doctor — you can "
    "book a consultation from the app."
)

EMERGENCY_ANSWER = (
    "This needs emergency care right now — not a chatbot. Use the red Emergency "
    "button in the app to get an ambulance dispatched with your records sent ahead, "
    "or call your local emergency number immediately. If someone is with you, tell "
    "them now."
)

# Deterministic red flags. Checked before the model, on a normalised string.
RED_FLAG_PATTERNS: tuple[str, ...] = (
    r"chest pain", r"crushing.{0,15}chest", r"pain.{0,12}(left arm|jaw)",
    r"seene? me[in]? dard", r"can'?t breathe", r"cannot breathe", r"not breathing",
    r"unable to breathe", r"breathless", r"saans nahi", r"gasping",
    r"unconscious", r"not responding", r"unresponsive", r"collapsed", r"fainted",
    r"seizure", r"fitting", r"convulsion",
    r"stroke", r"face droop", r"slurred speech", r"numbness on one side",
    r"bleeding heavily", r"bleeding.{0,10}(won'?t|not) stop", r"coughing up blood",
    r"vomiting blood", r"blood in vomit",
    r"overdose", r"took too many (tablets|pills)", r"poison",
    r"swallow(ed)?.{0,25}(strip|bottle|pills|tablets|medicines)",
    r"(ate|drank|took).{0,25}(whole|all).{0,20}(strip|bottle|pills|tablets|medicines)",
    r"taken all (her|his|my|the) (medicines|tablets|pills)",
    r"suicid", r"end my life", r"kill myself", r"harm(ing)? myself", r"self ?harm",
    r"throat swelling", r"anaphyla", r"stiff neck.{0,20}confus",
    r"head injury", r"severe head",
)
_RED_FLAG_RE = re.compile("|".join(RED_FLAG_PATTERNS), re.IGNORECASE)

# Guidance text per intent. Written once, reviewed once, served consistently —
# a generative model here would be a liability, not a feature.
ANSWERS: dict[str, str] = {
    "hydration": (
        "Most adults do well on about 2–3 litres of fluid a day, and more in hot weather "
        "or around exercise. Tea, coffee, milk and the water in food all count. Pale "
        "straw-coloured urine is the simplest sign you're getting enough."
    ),
    "sleep": (
        "Adults generally need 7–9 hours. What moves the needle most is a consistent "
        "wake-up time, daylight in the morning, and keeping screens and caffeine out of "
        "the last two hours before bed. If you sleep the hours but still wake unrefreshed "
        "most days, that's worth mentioning to your doctor."
    ),
    "diet_general": (
        "A simple balanced plate: half vegetables and fruit, a quarter whole grains, a "
        "quarter protein, with a little healthy fat. Most adults need roughly 0.8–1 g of "
        "protein per kg of body weight a day. Cutting added sugar and ultra-processed "
        "snacks usually matters more than any specific diet plan."
    ),
    "exercise": (
        "About 150 minutes of moderate activity a week — brisk walking counts — plus two "
        "sessions of strength work. Consistency beats intensity: three 20-minute walks "
        "you actually do beat a gym plan you don't. Build up gradually if you're starting out."
    ),
    "weight_bmi": (
        "BMI is weight in kg divided by height in metres squared; 18.5–24.9 is the usual "
        "normal band, and your profile calculates it once height and weight are saved. A "
        "safe rate of change is about 0.25–0.5 kg a week. BMI is a rough screen, not a "
        "verdict — muscle mass and body shape matter too."
    ),
    "medication_missed_dose": (
        "The general rule is to take a missed dose when you remember, unless it's nearly "
        "time for the next one — in that case skip it and carry on. Never double up to "
        "catch up. Some medicines (blood thinners, insulin, epilepsy medicines) have their "
        "own rules, so check with your doctor or pharmacist for those."
    ),
    "medication_timing": (
        "Follow the timing written on your prescription — it's in the app under your "
        "current prescription, including whether each medicine is before or after food. "
        "Don't stop a course early just because you feel better, and don't combine "
        "medicines without asking. Your doctor can confirm anything specific in chat."
    ),
    "medication_side_effect": (
        "Mild side effects often settle in the first week, but a rash, swelling, "
        "breathlessness, severe dizziness or anything that's getting worse is a reason to "
        "stop waiting and speak to your doctor. Don't stop a prescribed medicine on your "
        "own first — message your doctor in the app; the medicine and dose are already on "
        "your record for them to see."
    ),
    "fever": (
        "Rest and fluids handle most short fevers. Get medical review if the fever is "
        "above 38°C for more than three days, is above 40°C, comes with a stiff neck, "
        "rash, confusion or breathlessness, or if it's in an infant, an older adult or "
        "someone with a weak immune system."
    ),
    "headache": (
        "Most headaches come from dehydration, missed meals, poor sleep or screen strain, "
        "and settle with fluids, rest and a break from screens. A sudden severe headache, "
        "one with vision changes, weakness, fever with a stiff neck, or one that keeps "
        "worsening needs prompt medical review."
    ),
    "cold_cough": (
        "Most colds are viral and settle in 7–10 days — fluids, rest, steam and warm "
        "saline gargles are what help. Antibiotics don't work on viruses. See a doctor if "
        "a cough lasts beyond three weeks, or comes with breathlessness, chest pain, blood "
        "or a high fever that won't settle."
    ),
    "stomach": (
        "For loose motions, oral rehydration and simple food (rice, banana, curd) are the "
        "priority — fluid loss is the real risk. For acidity, smaller meals, less late-night "
        "eating and less caffeine help. Get reviewed if there's blood, severe or "
        "persistent pain, or symptoms lasting more than a couple of days."
    ),
    "diabetes": (
        "Commonly used targets are roughly 80–130 mg/dL fasting, under 180 mg/dL two hours "
        "after a meal, and HbA1c under 7% — but your doctor sets yours, and they may "
        "differ. Carbohydrate portion size, regular meal timing and a walk after meals are "
        "the three things that reliably move post-meal numbers."
    ),
    "blood_pressure": (
        "Under 120/80 is ideal and 140/90 or above is generally treated as high. Less salt "
        "(under 5 g a day), regular activity, weight control, less alcohol and better sleep "
        "all lower it measurably. Measure sitting, after five minutes of rest, and record "
        "readings in the app so your doctor sees the trend rather than one number."
    ),
    "cholesterol": (
        "LDL is the one to watch — under 100 mg/dL for most people and lower if you have "
        "heart disease or diabetes. Replacing saturated fat with nuts, seeds and oily fish, "
        "adding soluble fibre (oats, beans), and regular activity all help. If you've been "
        "prescribed a statin, take it as directed."
    ),
    "thyroid": (
        "TSH is the usual screening test; the normal range is roughly 0.4–4.0 mIU/L, "
        "though pregnancy and treatment change the target. Thyroid medicine is usually "
        "taken on an empty stomach, 30–60 minutes before breakfast, and away from calcium "
        "or iron. Dose changes are your doctor's call based on repeat bloods."
    ),
    "mental_health": (
        "Low mood, anxiety and burnout are common and treatable. Regular sleep, daily "
        "movement, daylight and staying connected to people all help, and so does talking "
        "to a professional — that isn't a last resort. If symptoms have lasted more than "
        "two weeks or are affecting work, sleep or relationships, book a consultation. "
        "If you ever feel unsafe, use the Emergency button or call a crisis line right away."
    ),
    "pregnancy": (
        "Folic acid, iron and adequate protein matter throughout, and iodine and calcium "
        "through the later months. Moderate activity like walking or prenatal yoga is "
        "usually encouraged. Avoid raw or undercooked food, unpasteurised dairy, alcohol "
        "and smoking, and check every medicine — even over-the-counter ones — with your "
        "obstetrician."
    ),
    "child_health": (
        "Children's fluid needs, doses and warning signs differ from adults', so a "
        "paediatrician's advice is worth getting early rather than late. Watch for poor "
        "feeding, unusual drowsiness, fewer wet nappies, fast breathing or a rash that "
        "doesn't fade under pressure — those need same-day review."
    ),
    "lab_report": (
        "Your reports are stored in the app under the reports timeline, and the doctor who "
        "requested a test sees it as soon as the lab uploads it. Fasting tests such as "
        "lipid profile and fasting glucose usually need 8–12 hours without food, water "
        "allowed. Rather than reading a single value in isolation, ask your doctor in the "
        "chat — they can see the trend across all your past reports."
    ),
    "smoking_alcohol": (
        "Quitting smoking is the single highest-return change most people can make; "
        "circulation and lung function start improving within weeks. For alcohol, less is "
        "better and there's no level that's actively good for you. Nicotine replacement "
        "and structured quit support roughly double success rates — your doctor can set "
        "that up."
    ),
    "vaccination": (
        "Adults are commonly advised an annual flu shot, a tetanus booster every ten "
        "years, and additional vaccines depending on age, pregnancy, travel and chronic "
        "conditions. Children follow the national immunisation schedule. Mild soreness or "
        "a day of low fever afterwards is expected and not a reason to skip the next dose."
    ),
    "app_booking": (
        "You can book a doctor's appointment or a lab test from the app, and send your "
        "prescription straight to a pharmacy to have the order ready. Old prescriptions "
        "and reports can be uploaded and edited into your timeline; new ones are added "
        "automatically. Insurance claims are filed from the Insurance tab by attaching the "
        "bill. HealthNexus Plus adds daily personalised guidance and best-match "
        "recommendations for doctors, labs, pharmacies and policies."
    ),
    "greeting": (
        "Hello. I can help with general questions about sleep, diet, hydration, exercise, "
        "your medicine schedule and how to use the app. What's on your mind?"
    ),
    "thanks": "Glad that helped. Ask me anything else whenever you need to.",
    "emergency": EMERGENCY_ANSWER,
    "out_of_scope": (
        "I only cover health and how to use HealthNexus — general questions about sleep, "
        "diet, hydration, exercise, medicines and your records. Ask me one of those and "
        "I'll help."
    ),
}

FALLBACK_ANSWER = (
    "I'm not sure I understood that one. I can help with general questions about sleep, "
    "diet, hydration, exercise, your medicines and your reports, or with using the app — "
    "booking appointments, lab tests, medicine orders and insurance claims. For anything "
    "about your specific condition, message your doctor in the chat tab."
)

# Intents where a tailored line from the patient's own record adds real value.
PERSONALISABLE = {
    "medication_missed_dose", "medication_timing", "medication_side_effect",
    "diabetes", "blood_pressure", "cholesterol", "thyroid", "diet_general",
    "exercise", "weight_bmi", "lab_report",
}

MIN_INTENT_CONFIDENCE = 0.30


def _build_vectoriser() -> FeatureUnion:
    # Word features carry the meaning; character features carry the robustness to
    # typos and transliteration. Left unweighted the char block produces an order
    # of magnitude more features and drowns the word signal, which showed up as
    # "throbbing pain in my head" being scored like "chest pain" — so the char
    # block is down-weighted rather than removed.
    return FeatureUnion(
        [
            ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)),
            (
                "char",
                TfidfVectorizer(
                    analyzer="char_wb", ngram_range=(3, 5), min_df=3, sublinear_tf=True
                ),
            ),
        ],
        transformer_weights={"word": 1.0, "char": 0.45},
    )


def _build_pipeline(class_weight="balanced") -> Pipeline:
    return Pipeline(
        [
            ("features", _build_vectoriser()),
            (
                "clf",
                LogisticRegression(
                    C=3.0, max_iter=3000, class_weight=class_weight, n_jobs=None
                ),
            ),
        ]
    )


@dataclass
class TriageModel:
    intent_clf: Pipeline
    urgency_clf: Pipeline
    metrics: dict[str, Any] = field(default_factory=dict)
    version: str = TRIAGE_VERSION
    trained_at: str = ""

    # --- inference ---------------------------------------------------------------

    def classify(self, question: str) -> dict[str, Any]:
        text = (question or "").strip()
        if not text:
            return {
                "intent": "out_of_scope",
                "intent_confidence": 0.0,
                "urgency": "routine",
                "red_flag": False,
            }

        red_flag = bool(_RED_FLAG_RE.search(text.lower()))

        intent_probabilities = self.intent_clf.predict_proba([text])[0]
        intent_index = int(np.argmax(intent_probabilities))
        intent = str(self.intent_clf.classes_[intent_index])
        confidence = float(intent_probabilities[intent_index])

        urgency_probabilities = self.urgency_clf.predict_proba([text])[0]
        urgency = str(self.urgency_clf.classes_[int(np.argmax(urgency_probabilities))])
        emergency_probability = float(
            urgency_probabilities[list(self.urgency_clf.classes_).index("emergency")]
            if "emergency" in self.urgency_clf.classes_
            else 0.0
        )

        # Rules win. A model that is unsure about chest pain must still escalate,
        # so the red-flag list and a low probability threshold both force it.
        if red_flag or emergency_probability >= 0.35:
            urgency = "emergency"

        return {
            "intent": intent,
            "intent_confidence": round(confidence, 4),
            "urgency": urgency,
            "emergency_probability": round(emergency_probability, 4),
            "red_flag": red_flag,
        }

    def answer(
        self, question: str, patient: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Full reply: classification, guidance text and whether to escalate."""
        result = self.classify(question)

        if result["urgency"] == "emergency":
            return {
                **result,
                "intent": "emergency",
                "answer": EMERGENCY_ANSWER,
                "escalate": True,
                "model_version": self.version,
            }

        if result["intent_confidence"] < MIN_INTENT_CONFIDENCE:
            return {
                **result,
                "answer": FALLBACK_ANSWER,
                "escalate": False,
                "model_version": self.version,
            }

        body = ANSWERS.get(result["intent"], FALLBACK_ANSWER)
        personal = _personalise(result["intent"], patient)
        if personal:
            body = f"{body} {personal}"
        if result["urgency"] == "see_doctor":
            body = f"{body} {SEE_DOCTOR_LINE}"
        if result["intent"] not in {"greeting", "thanks", "out_of_scope", "app_booking"}:
            body = f"{body} ({DISCLAIMER})"

        return {**result, "answer": body, "escalate": False, "model_version": self.version}


def _personalise(intent: str, patient: dict[str, Any] | None) -> str:
    """One grounded sentence from the patient's own record, where it helps."""
    if not patient or intent not in PERSONALISABLE:
        return ""
    conditions = [c.get("name") for c in (patient.get("conditions") or []) if c.get("name")]
    medicines = [m for m in (patient.get("medicines") or []) if m]
    bmi = patient.get("bmi")

    if intent in {"medication_missed_dose", "medication_timing", "medication_side_effect"} and medicines:
        listed = ", ".join(medicines[:3])
        return f"Your current prescription lists {listed} — the exact timing for each is on that prescription in the app."
    if intent == "weight_bmi" and bmi:
        band = (
            "in the healthy range" if 18.5 <= bmi < 25
            else "below the healthy range" if bmi < 18.5
            else "above the healthy range"
        )
        return f"Your recorded BMI is {bmi}, which is {band}."
    if intent in {"diabetes", "blood_pressure", "cholesterol", "thyroid"} and conditions:
        relevant = [c for c in conditions if _matches(intent, c)]
        if relevant:
            return f"Your record shows {relevant[0]} as an active condition, so your doctor's targets take precedence over the general ones."
    if intent in {"diet_general", "exercise"} and conditions:
        return f"Your plan should also account for {conditions[0]}, which is active on your record."
    if intent == "lab_report" and patient.get("latest_report"):
        return f"Your most recent report on file is {patient['latest_report']}."
    return ""


def _matches(intent: str, condition: str) -> bool:
    keywords = {
        "diabetes": ("diabet", "sugar"),
        "blood_pressure": ("hypertens", "blood pressure"),
        "cholesterol": ("cholesterol", "lipid"),
        "thyroid": ("thyroid",),
    }[intent]
    return any(k in condition.lower() for k in keywords)


def train_triage(
    texts: list[str],
    intents: list[str],
    urgencies: list[str],
) -> TriageModel:
    intent_clf = _build_pipeline()
    intent_clf.fit(texts, intents)
    # Emergencies are the minority class and the expensive one to miss, so the
    # urgency head is trained with balanced class weights.
    urgency_clf = _build_pipeline(class_weight="balanced")
    urgency_clf.fit(texts, urgencies)
    return TriageModel(
        intent_clf=intent_clf,
        urgency_clf=urgency_clf,
        trained_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )


ARTIFACT = "triage"


def save_triage(model: TriageModel):
    return registry.save(ARTIFACT, model)


def load_triage() -> TriageModel:
    return registry.load(ARTIFACT)

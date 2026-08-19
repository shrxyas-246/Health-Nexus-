"""Turns the simulated marketplace into labelled learning-to-rank datasets.

For each query (one patient, one candidate set) a *true utility* is computed
from the candidate's attributes and the patient's latent preferences. Utility is
then converted to a graded relevance label 0–4 by position within the query, the
standard target for NDCG-style ranking evaluation, plus a binary `chosen` flag
sampled softmax-style so the data also supports click-model style training.

The utility functions encode the product's stated intent:

* severe or surgical cases weight **outcomes** (success rate, volume) and stop
  caring much about distance;
* routine cases weight **convenience and price**;
* price sensitivity is latent and only partly observable, so no model can (or
  should) reach a perfect score.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from healthnexus_ml.datagen import universe as uni
from healthnexus_ml.features import build_frame
from healthnexus_ml.knowledge import SURGICAL_SPECIALITIES, specialities_for

GRADES = 5  # relevance levels 0..4


@dataclass
class RankDataset:
    X: pd.DataFrame
    y: np.ndarray            # graded relevance 0..4
    utility: np.ndarray      # the latent ground-truth score
    groups: np.ndarray       # query id per row
    kind: str
    # Raw request payloads per query id, kept so the shipped heuristic can be
    # scored on exactly the same held-out queries as the model.
    queries: list[dict] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.X)

    @property
    def n_queries(self) -> int:
        return len(np.unique(self.groups))


def _norm(values: np.ndarray) -> np.ndarray:
    """Scale to 0..1 within a query; all-equal or empty collapses to 0.5."""
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return np.full(values.shape, 0.5)
    low, high = finite.min(), finite.max()
    if high == low:
        return np.where(np.isfinite(values), 0.5, 0.5)
    out = (values - low) / (high - low)
    return np.where(np.isfinite(out), out, 0.5)


def _column(cands: list[dict], key: str, default=np.nan) -> np.ndarray:
    return np.array(
        [float(c[key]) if c.get(key) is not None else default for c in cands], dtype=float
    )


# --- utility per kind ------------------------------------------------------------


def doctor_utility(patient: uni.Patient, cands: list[dict], rng) -> np.ndarray:
    wanted = specialities_for(patient.condition_names)
    severe = patient.severity >= 2

    rating = _column(cands, "rating_avg")
    experience = _column(cands, "years_experience")
    fee = _column(cands, "consultation_fee")
    success = _column(cands, "complex_case_success_rate")
    procedures = _column(cands, "procedures_performed")
    distance = np.nan_to_num(_column(cands, "distance_km"), nan=12.0)
    verified = np.array([1.0 if c.get("is_verified") else 0.0 for c in cands])
    match = np.array([1.0 if c.get("specialization") in wanted else 0.0 for c in cands])
    general = np.array([1.0 if c.get("specialization") == "General Medicine" else 0.0 for c in cands])
    surgical = np.array(
        [1.0 if c.get("specialization") in SURGICAL_SPECIALITIES else 0.0 for c in cands]
    )

    utility = (
        3.2 * match
        + 0.9 * general * (1 - match)
        + patient.quality_weight * (1.6 * (rating - 4.0) + 0.035 * np.minimum(experience, 30))
        + 0.45 * verified
        - patient.price_sensitivity * 2.4 * _norm(fee)
        - patient.convenience_weight * (0.4 if severe else 1.9) * _norm(distance)
    )
    if severe:
        utility += (
            0.075 * (success - 88.0)
            + 0.55 * _norm(procedures)
            + 0.6 * surgical
            - 1.5 * general * (match.sum() > 0)
        )
    return utility + rng.normal(0, 0.45, size=len(cands))


def hospital_utility(patient: uni.Patient, cands: list[dict], rng, need: str | None) -> np.ndarray:
    wanted = specialities_for(patient.condition_names)
    severe = patient.severity >= 2

    rating = _column(cands, "rating_avg")
    success = _column(cands, "surgery_success_rate")
    complex_cases = _column(cands, "complex_cases_handled")
    icu = _column(cands, "icu_bed_count")
    fee = _column(cands, "avg_consultation_fee")
    distance = np.nan_to_num(_column(cands, "distance_km"), nan=12.0)
    emergency = np.array([1.0 if c.get("has_emergency") else 0.0 for c in cands])
    accredited = np.array([1.0 if c.get("accreditation") else 0.0 for c in cands])
    need_match = np.array(
        [
            1.0
            if need and need.lower() in str(c.get("specializations", "")).lower()
            else 0.0
            for c in cands
        ]
    )
    speciality_match = np.array(
        [
            1.0 if any(w.lower() in str(c.get("specializations", "")).lower() for w in wanted) else 0.0
            for c in cands
        ]
    )

    utility = (
        2.4 * need_match
        + 1.3 * speciality_match
        + patient.quality_weight * (1.5 * (rating - 4.0) + 0.9 * accredited)
        - patient.price_sensitivity * 1.8 * _norm(fee)
        - patient.convenience_weight * (0.5 if severe else 1.8) * _norm(distance)
        + 0.5 * emergency
    )
    if severe:
        utility += 0.09 * (success - 92.0) + 0.7 * _norm(complex_cases) + 0.5 * _norm(icu)
    return utility + rng.normal(0, 0.45, size=len(cands))


def lab_utility(patient: uni.Patient, cands: list[dict], rng) -> np.ndarray:
    coverage = _column(cands, "coverage", default=1.0)
    quote = _column(cands, "quoted_total")
    # A lab that cannot run the tests is worthless however cheap it looks.
    price_position = _norm(np.where(np.isfinite(quote), quote, np.nanmax(quote) if np.isfinite(quote).any() else 0))
    rating = _column(cands, "rating_avg")
    turnaround = _column(cands, "turnaround_hours")
    distance = np.nan_to_num(_column(cands, "distance_km"), nan=12.0)
    home = np.array([1.0 if c.get("home_collection") else 0.0 for c in cands])
    accredited = np.array([1.0 if c.get("accreditation") else 0.0 for c in cands])

    utility = (
        3.0 * coverage
        - patient.price_sensitivity * 3.0 * price_position
        + patient.quality_weight * (1.2 * (rating - 4.0) + 0.8 * accredited)
        + patient.convenience_weight * (0.9 * home - 1.2 * _norm(distance) - 0.7 * _norm(turnaround))
    )
    utility = np.where(np.isfinite(quote), utility, utility - 2.5)
    return utility + rng.normal(0, 0.4, size=len(cands))


def pharmacy_utility(patient: uni.Patient, cands: list[dict], rng) -> np.ndarray:
    coverage = _column(cands, "coverage", default=1.0)
    quote = _column(cands, "quoted_total")
    price_position = _norm(np.where(np.isfinite(quote), quote, np.nanmax(quote) if np.isfinite(quote).any() else 0))
    rating = _column(cands, "rating_avg")
    minutes = np.nan_to_num(_column(cands, "avg_delivery_minutes"), nan=120.0)
    distance = np.nan_to_num(_column(cands, "distance_km"), nan=12.0)
    delivers = np.array([1.0 if c.get("delivers") else 0.0 for c in cands])
    always_open = np.array([1.0 if c.get("is_24x7") else 0.0 for c in cands])

    utility = (
        3.4 * coverage
        - patient.price_sensitivity * 3.2 * price_position
        + patient.quality_weight * 1.0 * (rating - 4.0)
        + patient.convenience_weight
        * (1.0 * delivers - 1.1 * _norm(minutes) - 0.9 * _norm(distance) + 0.4 * always_open)
    )
    utility = np.where(np.isfinite(quote), utility, utility - 2.5)
    return utility + rng.normal(0, 0.4, size=len(cands))


def insurance_utility(patient: uni.Patient, cands: list[dict], rng, has_chronic: bool) -> np.ndarray:
    cover = _column(cands, "cover_amount")
    premium = _column(cands, "annual_premium")
    value = np.divide(cover, np.where(premium > 0, premium, np.nan))
    settlement = _column(cands, "claim_settlement_ratio")
    network = _column(cands, "network_hospital_count")
    waiting = _column(cands, "waiting_period_months")
    pre_existing = np.array([1.0 if c.get("covers_pre_existing") else 0.0 for c in cands])
    opd = np.array([1.0 if c.get("covers_opd") else 0.0 for c in cands])
    insurer_rating = _column(cands, "insurer_rating")

    utility = (
        2.6 * _norm(value)
        + 0.12 * (settlement - 92.0)
        + 0.6 * _norm(network)
        + 0.5 * insurer_rating
        + 0.4 * opd
        - patient.price_sensitivity * 2.6 * _norm(premium)
        + patient.quality_weight * 0.9 * _norm(cover)
    )
    if has_chronic:
        # A chronic patient buying a policy that excludes pre-existing disease
        # for four years has bought very little.
        utility += 2.2 * pre_existing - 0.045 * waiting * (1 - pre_existing)
    return utility + rng.normal(0, 0.4, size=len(cands))


# --- dataset assembly ------------------------------------------------------------


def _grade(utility: np.ndarray) -> np.ndarray:
    """Graded relevance 0..4 by rank position inside the query."""
    order = np.argsort(np.argsort(-utility))  # 0 = best
    n = len(utility)
    if n == 1:
        return np.array([GRADES - 1])
    cut = np.floor(order / n * GRADES).astype(int)
    return np.clip(GRADES - 1 - cut, 0, GRADES - 1)


def build_dataset(kind: str, n_queries: int, seed: int) -> RankDataset:
    """Generate `n_queries` labelled ranking queries for one recommender."""
    rng = np.random.default_rng(seed)
    frames, grades, utilities, groups, queries = [], [], [], [], []

    for query_id in range(n_queries):
        patient = uni.make_patient(rng)
        n_candidates = int(rng.integers(6, 25))
        context: dict = {}

        if kind == "doctor":
            cands = uni.make_doctors(rng, n_candidates, patient)
            context = {"conditions": patient.condition_names}
            utility = doctor_utility(patient, cands, rng)
        elif kind == "hospital":
            need = (
                str(rng.choice(list(specialities_for(patient.condition_names)) or ["Cardiology"]))
                if rng.random() < 0.6
                else None
            )
            cands = uni.make_hospitals(rng, n_candidates, patient)
            context = {"need": need}
            utility = hospital_utility(patient, cands, rng, need)
        elif kind == "lab":
            n_tests = int(rng.integers(1, 5))
            tests = [str(t) for t in rng.choice(uni.TEST_POOL, size=n_tests, replace=False)]
            cands = uni.make_labs(rng, n_candidates, patient, n_tests)
            context = {"tests": tests}
            utility = lab_utility(patient, cands, rng)
        elif kind == "pharmacy":
            n_items = int(rng.integers(1, 6))
            cands = uni.make_pharmacies(rng, n_candidates, patient, n_items)
            context = {"prescription_id": query_id}
            utility = pharmacy_utility(patient, cands, rng)
        elif kind == "insurance":
            has_chronic = any(
                c["category"] == "chronic" for c in patient.payload["conditions"]
            )
            cands = uni.make_insurance_plans(rng, n_candidates, patient)
            context = {"has_chronic_condition": has_chronic}
            utility = insurance_utility(patient, cands, rng, has_chronic)
        else:
            raise ValueError(f"unknown kind {kind!r}")

        frame = build_frame(kind, patient.payload, cands, context)
        frames.append(frame)
        utilities.append(utility)
        grades.append(_grade(utility))
        groups.append(np.full(len(cands), query_id))
        queries.append(
            {"query_id": query_id, "patient": patient.payload, "candidates": cands, "context": context}
        )

    X = pd.concat(frames, ignore_index=True)
    return RankDataset(
        X=X,
        y=np.concatenate(grades),
        utility=np.concatenate(utilities),
        groups=np.concatenate(groups),
        kind=kind,
        queries=queries,
    )

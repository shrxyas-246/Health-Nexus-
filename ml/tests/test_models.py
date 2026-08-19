"""Tests for the trained models and the service.

Run with:  python -m pytest ml/tests -q   (from the repo root, after training)

These are behaviour tests, not accuracy tests — accuracy is measured by
`healthnexus_ml.train` and written to artifacts/metrics.json. What is asserted
here is the contract the product depends on: the payload shape the backend
sends, the response shape it expects, and the safety behaviour that must hold
regardless of what the model happens to predict.
"""

from __future__ import annotations

import os

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")

import pytest
from fastapi.testclient import TestClient

from healthnexus_ml import baselines, metrics
from healthnexus_ml.config import RANK_KINDS
from healthnexus_ml.datagen import chat as chat_data
from healthnexus_ml.datagen import ranking as rank_data
from healthnexus_ml.features import build_frame
from healthnexus_ml.models import registry
from healthnexus_ml.models import ranker as ranker_model
from healthnexus_ml.models import triage as triage_model
from healthnexus_ml.models import wellness as wellness_model
from healthnexus_ml.service import app

pytestmark = pytest.mark.filterwarnings("ignore::UserWarning")

trained = pytest.mark.skipif(
    not registry.exists("triage"), reason="models not trained yet; run healthnexus_ml.train"
)


# --- features -----------------------------------------------------------------------


@pytest.mark.parametrize("kind", RANK_KINDS)
def test_featuriser_handles_empty_candidates(kind):
    frame = build_frame(kind, {"age": 40}, [], {})
    assert frame.empty


@pytest.mark.parametrize("kind", RANK_KINDS)
def test_featuriser_tolerates_missing_fields(kind):
    """A candidate with nothing but an id must still produce a full feature row."""
    frame = build_frame(kind, {}, [{"id": 1}, {"id": 2}], {})
    assert len(frame) == 2
    assert frame.notna().any().any()


def test_relative_features_rank_within_the_query():
    candidates = [
        {"id": 1, "consultation_fee": 200, "distance_km": 1.0},
        {"id": 2, "consultation_fee": 900, "distance_km": 9.0},
    ]
    frame = build_frame("doctor", {"age": 30}, candidates, {})
    assert frame["c_fee__rel"].iloc[0] == 0.0
    assert frame["c_fee__rel"].iloc[1] == 1.0


# --- ranking ------------------------------------------------------------------------


@trained
@pytest.mark.parametrize("kind", RANK_KINDS)
def test_ranker_returns_every_candidate_ordered(kind):
    model = ranker_model.load_ranker(kind)
    dataset = rank_data.build_dataset(kind, 1, seed=99)
    query = dataset.queries[0]

    ranked = model.rank(query["patient"], query["candidates"], query["context"])

    assert len(ranked) == len(query["candidates"])
    assert {r["id"] for r in ranked} == {c["id"] for c in query["candidates"]}
    assert [r["rank"] for r in ranked] == list(range(1, len(ranked) + 1))
    assert all(ranked[i]["raw_score"] >= ranked[i + 1]["raw_score"] for i in range(len(ranked) - 1))
    assert all(0 <= r["score"] <= 100 for r in ranked)
    assert all(r["reason"] for r in ranked)


@trained
@pytest.mark.parametrize("kind", RANK_KINDS)
def test_ranker_beats_the_shipped_heuristic(kind):
    """The reason to run a model at all: it must rank better than the rules it replaces."""
    model = ranker_model.load_ranker(kind)
    test = rank_data.build_dataset(kind, 150, seed=4242)

    model_ndcg = metrics.grouped_ndcg(test.y, model.predict_frame(test.X), test.groups, 5)
    heuristic = [
        score
        for query in test.queries
        for score in baselines.heuristic_scores(
            kind, query["patient"], query["candidates"], query["context"]
        )
    ]
    heuristic_ndcg = metrics.grouped_ndcg(test.y, heuristic, test.groups, 5)

    assert model_ndcg > heuristic_ndcg, f"{kind}: {model_ndcg:.4f} <= {heuristic_ndcg:.4f}"


@trained
def test_ranker_survives_a_single_candidate():
    model = ranker_model.load_ranker("doctor")
    ranked = model.rank({"age": 50}, [{"id": 7, "specialization": "Cardiology"}], {})
    assert len(ranked) == 1 and ranked[0]["id"] == 7


# --- guidance assistant --------------------------------------------------------------


@trained
@pytest.mark.parametrize(
    "question",
    [
        "i have chest pain",
        "my father is unconscious",
        "i cannot breathe",
        "swallowed a whole strip of pills",
        "i want to end my life",
        "she collapsed and is not responding",
        "coughing up blood",
        "CHEST PAIN!!",
        "chst pain and left arm hurts",
    ],
)
def test_emergencies_always_escalate(question):
    """The one test that must never be allowed to fail."""
    result = triage_model.load_triage().answer(question)
    assert result["escalate"] is True
    assert result["urgency"] == "emergency"
    assert "Emergency" in result["answer"]


@trained
def test_routine_questions_are_answered_not_escalated():
    model = triage_model.load_triage()
    for question in ["how much water should i drink", "how many hours should i sleep", "hi"]:
        result = model.answer(question)
        assert result["escalate"] is False
        assert len(result["answer"]) > 40


@trained
def test_held_out_phrasings_are_classified():
    """Hand-written phrasings absent from the training corpus."""
    model = triage_model.load_triage()
    correct = sum(
        model.answer(text)["intent"] == intent for text, intent, _ in chat_data.HELD_OUT_CASES
    )
    assert correct / len(chat_data.HELD_OUT_CASES) >= 0.85


@trained
def test_unknown_questions_fall_back_safely():
    result = triage_model.load_triage().answer("qwertyuiop zxcvbnm asdf")
    assert result["escalate"] is False
    assert "general questions" in result["answer"]


@trained
def test_answers_are_personalised_from_the_record():
    model = triage_model.load_triage()
    patient = {"medicines": ["Metformin 500mg", "Telmisartan 40mg"], "conditions": []}
    result = model.answer("i missed my medicine dose", patient)
    assert "Metformin 500mg" in result["answer"]


@trained
def test_guidance_carries_the_disclaimer():
    result = triage_model.load_triage().answer("how much protein do i need")
    assert "not a diagnosis" in result["answer"]


# --- wellness plan --------------------------------------------------------------------


@trained
def test_wellness_plan_from_a_full_record():
    record = {
        "age": 58,
        "gender": "male",
        "height_cm": 172,
        "weight_kg": 88,
        "conditions": [{"name": "Type 2 Diabetes"}, {"name": "Hypertension"}],
        "medicines": ["Metformin", "Telmisartan"],
        "vitals": {"hba1c": 8.1, "systolic": 148, "diastolic": 92},
        "sleep_hours": 5.5,
        "activity_level": 1,
    }
    plan = wellness_model.load_wellness().plan(record)

    kinds = [card["kind"] for card in plan["cards"]]
    assert kinds == ["diet", "workout", "lifestyle"]

    diet = plan["cards"][0]["payload"]
    assert 1200 <= diet["targets"]["kcal_a_day"] <= 4200
    assert 35 <= diet["targets"]["g_protein"] <= 190
    assert diet["meals"]
    # Diabetes plus a high reading should produce sugar and sodium limits.
    assert "sugar_limit" in diet["restrictions"]
    assert "sodium_limit" in diet["restrictions"]

    workout = plan["cards"][1]["payload"]
    assert workout["intensity"] in {"gentle", "moderate", "vigorous"}
    assert workout["sessions"]

    lifestyle = plan["cards"][2]["payload"]
    assert lifestyle["change"] and lifestyle["expected_effect"]


@trained
def test_wellness_plan_from_an_almost_empty_record():
    """A brand-new patient with only an age must still get a usable plan."""
    plan = wellness_model.load_wellness().plan({"age": 30})
    assert len(plan["cards"]) == 3
    assert plan["cards"][0]["payload"]["targets"]["kcal_a_day"] > 0


@trained
def test_renal_records_get_a_protein_ceiling():
    """Clinical sanity: kidney disease must not produce a high-protein plan."""
    model = wellness_model.load_wellness()
    base = {"age": 60, "gender": "male", "height_cm": 170, "weight_kg": 70}
    healthy = model.plan(base)["cards"][0]["payload"]["targets"]["g_protein"]
    renal = model.plan(
        {**base, "conditions": [{"name": "Chronic Kidney Disease"}], "vitals": {"creatinine": 2.4}}
    )["cards"][0]["payload"]["targets"]["g_protein"]
    assert renal < healthy


# --- service --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_health_endpoint(client):
    body = client.get("/health").json()
    assert body["service"] == "health-nexus-ml"
    assert "artifacts" in body


@trained
def test_rank_endpoint_matches_the_backend_contract(client):
    """The exact payload backend/app/services/ml_client.py sends."""
    payload = {
        "kind": "doctor",
        "patient": {
            "age": 45,
            "gender": "male",
            "bmi": 27.2,
            "city": "Bengaluru",
            "is_premium": True,
            "allergies": ["Penicillin"],
            "conditions": [
                {"name": "Type 2 Diabetes", "category": "chronic", "status": "active", "severity": "moderate"}
            ],
        },
        "candidates": [
            {"id": 1, "specialization": "Endocrinology", "rating_avg": 4.8, "rating_count": 120,
             "years_experience": 14, "consultation_fee": 800, "procedures_performed": 300,
             "complex_case_success_rate": 94.0, "distance_km": 3.2, "city": "Bengaluru", "is_verified": True},
            {"id": 2, "specialization": "Dermatology", "rating_avg": 4.1, "rating_count": 20,
             "years_experience": 5, "consultation_fee": 1500, "procedures_performed": 40,
             "complex_case_success_rate": 88.0, "distance_km": 18.0, "city": "Mumbai", "is_verified": False},
        ],
        "context": {"conditions": ["Type 2 Diabetes"]},
    }
    body = client.post("/rank", json=payload).json()
    assert body["model_version"]
    assert [item["id"] for item in body["ranked"]] == [1, 2]
    assert body["ranked"][0]["reason"]


def test_rank_rejects_an_unknown_kind(client):
    assert client.post("/rank", json={"kind": "astrologer", "candidates": []}).status_code == 400


@trained
def test_chat_endpoint_escalates(client):
    body = client.post("/chat", json={"question": "severe chest pain right now"}).json()
    assert body["escalate"] is True
    assert body["urgency"] == "emergency"


@trained
def test_wellness_endpoint(client):
    body = client.post(
        "/wellness/plan",
        json={"patient": {"age": 40, "height_cm": 165, "weight_kg": 82}, "narrate": False},
    ).json()
    assert len(body["cards"]) == 3
    assert body["model_version"]

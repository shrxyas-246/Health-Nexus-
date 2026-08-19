"""The ML service the product backend talks to.

    uvicorn healthnexus_ml.service:app --port 8100

Then point the API at it:

    ML_SERVICE_URL=http://127.0.0.1:8100

Endpoints:

* ``POST /rank``          — model 3. Exactly the contract already documented in
  ``backend/app/services/ml_client.py``; the backend needed no change to use it.
* ``POST /chat``          — model 1, the guidance assistant.
* ``POST /wellness/plan`` — model 2, the premium daily plan.
* ``GET  /health``        — liveness plus which artefacts loaded.
* ``GET  /models``        — versions and held-out metrics for every model.

Design decisions worth knowing:

* Artefacts load lazily and are cached. A missing artefact degrades that one
  endpoint to a 503 rather than preventing the service from starting — the
  backend already falls back to its heuristic on any non-200, so one untrained
  model never takes the product down.
* Nothing here touches the product database. The backend owns patient data and
  passes exactly the fields the models need.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 4))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from healthnexus_ml import __version__, llm
from healthnexus_ml.config import RANK_KINDS
from healthnexus_ml.models import ranker as ranker_model
from healthnexus_ml.models import registry
from healthnexus_ml.models import triage as triage_model
from healthnexus_ml.models import wellness as wellness_model

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Health Nexus ML Service",
    version=__version__,
    description=(
        "Recommendation ranking, the health-guidance assistant and the premium "
        "daily wellness plan for the Health Nexus platform."
    ),
)


# --- lazy artefact loading ---------------------------------------------------------


@lru_cache(maxsize=None)
def _ranker(kind: str):
    return ranker_model.load_ranker(kind)


@lru_cache(maxsize=1)
def _triage():
    return triage_model.load_triage()


@lru_cache(maxsize=1)
def _wellness():
    return wellness_model.load_wellness()


def _require(loader, name: str):
    try:
        return loader()
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=503,
            detail=f"{name} model is not trained yet. Run `python -m healthnexus_ml.train`.",
        ) from error


# --- schemas -----------------------------------------------------------------------


class RankRequest(BaseModel):
    kind: str = Field(..., description="doctor | hospital | lab | pharmacy | insurance")
    patient: dict[str, Any] = Field(default_factory=dict)
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


class RankedItem(BaseModel):
    id: int | None = None
    score: float
    rank: int
    reason: str | None = None
    raw_score: float | None = None


class RankResponse(BaseModel):
    model_version: str
    kind: str
    ranked: list[RankedItem]


class ChatRequest(BaseModel):
    question: str
    patient: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    answer: str
    intent: str
    intent_confidence: float
    urgency: str
    escalate: bool
    red_flag: bool = False
    model_version: str


class WellnessRequest(BaseModel):
    patient: dict[str, Any] = Field(default_factory=dict)
    narrate: bool = Field(
        default=True, description="Allow the LLM narration layer, when configured"
    )


class WellnessCard(BaseModel):
    kind: str
    title: str
    rationale: str
    score: float
    payload: dict[str, Any]
    narrated_by: str | None = None


class WellnessResponse(BaseModel):
    model_version: str
    prediction: dict[str, Any]
    cards: list[WellnessCard]


# --- endpoints ---------------------------------------------------------------------


@app.get("/health", tags=["meta"])
def health() -> dict:
    loaded = {
        f"ranker_{kind}": registry.exists(ranker_model.artifact_name(kind)) for kind in RANK_KINDS
    }
    loaded["triage"] = registry.exists(triage_model.ARTIFACT)
    loaded["wellness"] = registry.exists(wellness_model.ARTIFACT)
    return {
        "status": "ok" if all(loaded.values()) else "degraded",
        "service": "health-nexus-ml",
        "version": __version__,
        "artifacts": loaded,
        "llm_narration": llm.is_enabled(),
    }


@app.get("/models", tags=["meta"])
def models() -> dict:
    """Versions and held-out metrics — what is actually running, and how well."""
    out: dict[str, Any] = {"rankers": {}}
    for kind in RANK_KINDS:
        try:
            model = _ranker(kind)
        except FileNotFoundError:
            out["rankers"][kind] = {"status": "not trained"}
            continue
        out["rankers"][kind] = {
            "version": model.version,
            "trained_at": model.trained_at,
            "n_features": len(model.features),
            "metrics": model.metrics,
        }
    for name, loader in (("triage", _triage), ("wellness", _wellness)):
        try:
            model = loader()
        except FileNotFoundError:
            out[name] = {"status": "not trained"}
            continue
        out[name] = {
            "version": model.version,
            "trained_at": model.trained_at,
            "metrics": model.metrics,
        }
    return out


@app.post("/rank", response_model=RankResponse, tags=["recommendations"])
def rank(request: RankRequest) -> RankResponse:
    """Model 3 — rank a candidate set for one patient."""
    if request.kind not in RANK_KINDS:
        raise HTTPException(status_code=400, detail=f"Unknown kind: {request.kind}")
    model = _require(lambda: _ranker(request.kind), f"{request.kind} ranking")
    ranked = model.rank(request.patient, request.candidates, request.context)
    return RankResponse(
        model_version=model.version, kind=request.kind, ranked=[RankedItem(**r) for r in ranked]
    )


@app.post("/chat", response_model=ChatResponse, tags=["assistant"])
def chat(request: ChatRequest) -> ChatResponse:
    """Model 1 — answer a general health question, escalating anything urgent."""
    model = _require(_triage, "guidance assistant")
    result = model.answer(request.question, request.patient)
    return ChatResponse(
        answer=result["answer"],
        intent=result["intent"],
        intent_confidence=result["intent_confidence"],
        urgency=result["urgency"],
        escalate=result["escalate"],
        red_flag=result.get("red_flag", False),
        model_version=model.version,
    )


@app.post("/wellness/plan", response_model=WellnessResponse, tags=["premium"])
def wellness_plan(request: WellnessRequest) -> WellnessResponse:
    """Model 2 — today's diet, movement and lifestyle plan for one patient."""
    model = _require(_wellness, "wellness")
    plan = model.plan(request.patient)
    cards = plan["cards"]
    if request.narrate:
        cards = llm.narrate(cards, request.patient, plan["prediction"])
    return WellnessResponse(
        model_version=plan["model_version"],
        prediction=plan["prediction"],
        cards=[WellnessCard(**card) for card in cards],
    )

"""Seam between the product API and the model team's service.

The rest of the backend only ever calls `get_ranking`. When `ML_SERVICE_URL` is
configured, the request is forwarded to that service and its ranked ids are used
verbatim. When it is not, the deterministic heuristics in `recommendations.py`
produce the same response shape, so every premium surface works end to end
before the model lands.

The same seam now carries all three model families. Every call returns ``None``
rather than raising when the service is unreachable, so a model outage degrades
a surface to its rule-based fallback instead of failing the request.

Contract expected of the ML service (implemented by ``ml/healthnexus_ml/service.py``):

    POST {ML_SERVICE_URL}/rank                       -- model 3, recommendations
    {
      "kind": "doctor" | "hospital" | "lab" | "pharmacy" | "insurance",
      "patient": { ...PatientFeatures... },
      "candidates": [ { "id": 1, ...features... }, ... ],
      "context": { ... }
    }
    -> { "model_version": "v1", "ranked": [ {"id": 1, "score": 0.93,
                                             "reason": "..."} ] }

    POST {ML_SERVICE_URL}/chat                       -- model 1, guidance assistant
    { "question": "...", "patient": { ...context... } }
    -> { "answer": "...", "intent": "...", "urgency": "routine|see_doctor|emergency",
         "escalate": false, "model_version": "triage-v1" }

    POST {ML_SERVICE_URL}/wellness/plan               -- model 2, daily plan
    { "patient": { ...record... } }
    -> { "model_version": "wellness-v1", "prediction": {...},
         "cards": [ {"kind": "diet", "title": "...", "rationale": "...",
                     "score": 0.9, "payload": {...}}, ... ] }
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from app.core.config import settings

REQUEST_TIMEOUT_SECONDS = 4


@dataclass
class RankedItem:
    id: int
    score: float
    reason: str | None = None


@dataclass
class RankingResult:
    ranked: list[RankedItem]
    model_version: str

    @property
    def by_id(self) -> dict[int, RankedItem]:
        return {item.id: item for item in self.ranked}


def is_ml_service_configured() -> bool:
    return bool(settings.ML_SERVICE_URL)


def _post(path: str, payload: dict[str, Any], timeout: int = REQUEST_TIMEOUT_SECONDS) -> dict | None:
    """POST JSON to the ML service. Returns None on any failure, never raises.

    Every caller has a working fallback, so the right behaviour when the model
    is down is to say so quietly and let the product carry on.
    """
    if not settings.ML_SERVICE_URL:
        return None

    request = urllib.request.Request(
        f"{settings.ML_SERVICE_URL.rstrip('/')}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
        return None


def get_chat_reply(question: str, patient_context: dict[str, Any] | None = None) -> dict | None:
    """Model 1. Returns the assistant's reply, or None to fall back to the FAQ rules."""
    body = _post("/chat", {"question": question, "patient": patient_context or {}})
    if not body or not body.get("answer"):
        return None
    return {
        "answer": body["answer"],
        "escalate": bool(body.get("escalate")),
        "intent": body.get("intent"),
        "urgency": body.get("urgency"),
        "confidence": body.get("intent_confidence"),
        "model_version": body.get("model_version", "unknown"),
    }


def get_wellness_plan(patient_record: dict[str, Any]) -> dict | None:
    """Model 2. Returns the day's diet/movement/lifestyle cards, or None."""
    # The wellness model runs five heads and may call the narration layer, so it
    # gets a longer budget than a ranking call.
    body = _post("/wellness/plan", {"patient": patient_record}, timeout=15)
    if not body or not body.get("cards"):
        return None
    return body


def service_health() -> dict | None:
    """Liveness of the ML service, for the admin/status surface."""
    if not settings.ML_SERVICE_URL:
        return None
    try:
        with urllib.request.urlopen(
            f"{settings.ML_SERVICE_URL.rstrip('/')}/health", timeout=REQUEST_TIMEOUT_SECONDS
        ) as response:
            return json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
        return None


def get_ranking(
    kind: str,
    patient_features: dict[str, Any],
    candidates: list[dict[str, Any]],
    context: dict[str, Any] | None = None,
) -> RankingResult | None:
    """Ask the ML service to rank candidates. Returns None if it is unavailable.

    Callers fall back to the heuristic ranking rather than failing the request:
    a recommendation surface degrading to rules is better than a 500.
    """
    body = _post(
        "/rank",
        {
            "kind": kind,
            "patient": patient_features,
            "candidates": candidates,
            "context": context or {},
        },
    )
    if not body:
        return None

    ranked = [
        RankedItem(id=int(r["id"]), score=float(r.get("score", 0)), reason=r.get("reason"))
        for r in body.get("ranked", [])
        if "id" in r
    ]
    return RankingResult(ranked=ranked, model_version=body.get("model_version", "unknown"))

"""Seam between the product API and the model team's service.

The rest of the backend only ever calls `get_ranking`. When `ML_SERVICE_URL` is
configured, the request is forwarded to that service and its ranked ids are used
verbatim. When it is not, the deterministic heuristics in `recommendations.py`
produce the same response shape, so every premium surface works end to end
before the model lands.

Contract expected of the ML service:

    POST {ML_SERVICE_URL}/rank
    {
      "kind": "doctor" | "hospital" | "lab" | "pharmacy" | "insurance",
      "patient": { ...PatientFeatures... },
      "candidates": [ { "id": 1, ...features... }, ... ],
      "context": { ... }
    }
    -> { "model_version": "v1", "ranked": [ {"id": 1, "score": 0.93,
                                             "reason": "..."} ] }
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
    if not settings.ML_SERVICE_URL:
        return None

    payload = json.dumps(
        {
            "kind": kind,
            "patient": patient_features,
            "candidates": candidates,
            "context": context or {},
        }
    ).encode()

    request = urllib.request.Request(
        f"{settings.ML_SERVICE_URL.rstrip('/')}/rank",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None

    ranked = [
        RankedItem(id=int(r["id"]), score=float(r.get("score", 0)), reason=r.get("reason"))
        for r in body.get("ranked", [])
        if "id" in r
    ]
    return RankingResult(ranked=ranked, model_version=body.get("model_version", "unknown"))

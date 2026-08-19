"""Model 3 — the doctor / hospital / lab / pharmacy / insurance recommenders.

One gradient-boosted regression model per kind, trained pointwise on graded
relevance (0–4) and evaluated with ranking metrics (NDCG, hit rate, MRR) over
held-out *queries*, never held-out rows — splitting rows would leak candidates
from the same query across train and test and inflate every number.

Pointwise regression on graded relevance was chosen over a pairwise objective
deliberately: sklearn ships no pairwise ranker, the candidate sets here are small
(6–25), and the resulting scores are directly interpretable as "predicted
relevance", which the product surfaces as a 0–100 match score.

``HistGradientBoostingRegressor`` handles NaN natively, which matters because a
missing price quote or an ungeocoded clinic is normal in this data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance

from healthnexus_ml.config import RANKER_VERSION
from healthnexus_ml.datagen.ranking import RankDataset
from healthnexus_ml.features import build_frame
from healthnexus_ml.models import registry
from healthnexus_ml.reasons import explain

MAX_RELEVANCE = 4.0


@dataclass
class RankerModel:
    kind: str
    estimator: HistGradientBoostingRegressor
    features: list[str]
    metrics: dict[str, Any] = field(default_factory=dict)
    importances: dict[str, float] = field(default_factory=dict)
    version: str = RANKER_VERSION
    trained_at: str = ""

    # --- inference ---------------------------------------------------------------

    def _align(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Force the training column order; unknown columns drop, missing become NaN."""
        return frame.reindex(columns=self.features)

    def predict_frame(self, frame: pd.DataFrame) -> np.ndarray:
        if frame.empty:
            return np.array([])
        return self.estimator.predict(self._align(frame))

    def rank(
        self,
        patient: dict[str, Any],
        candidates: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Score and order one candidate set. Returns the `/rank` response items."""
        if not candidates:
            return []
        frame = build_frame(self.kind, patient, candidates, context or {})
        raw = self.predict_frame(frame)

        ordered = np.argsort(-raw, kind="stable")
        out = []
        for position, index in enumerate(ordered):
            candidate = candidates[int(index)]
            out.append(
                {
                    "id": candidate.get("id"),
                    # Predicted relevance mapped to the 0–100 match score the UI shows.
                    "score": round(float(np.clip(raw[index] / MAX_RELEVANCE, 0, 1) * 100), 1),
                    "raw_score": round(float(raw[index]), 4),
                    "rank": position + 1,
                    "reason": explain(self.kind, candidate, candidates, patient, context or {}),
                }
            )
        return out


def train_ranker(
    train: RankDataset,
    validation: RankDataset | None = None,
    *,
    seed: int = 0,
    compute_importances: bool = True,
) -> RankerModel:
    """Fit one recommender. `validation` is only used for permutation importance."""
    features = list(train.X.columns)
    estimator = HistGradientBoostingRegressor(
        loss="squared_error",
        max_iter=400,
        learning_rate=0.06,
        max_leaf_nodes=31,
        min_samples_leaf=20,
        l2_regularization=1.0,
        early_stopping=True,
        n_iter_no_change=25,
        validation_fraction=0.15,
        random_state=seed,
    )
    estimator.fit(train.X, train.y)

    importances: dict[str, float] = {}
    if compute_importances and validation is not None and len(validation) > 0:
        # Permutation importance on held-out data — the only importance measure
        # that reflects what the model actually relies on at serving time.
        sample = min(len(validation), 6000)
        result = permutation_importance(
            estimator,
            validation.X.iloc[:sample],
            validation.y[:sample],
            n_repeats=4,
            random_state=seed,
            scoring="r2",
        )
        importances = {
            name: round(float(value), 5)
            for name, value in sorted(
                zip(features, result.importances_mean), key=lambda kv: -kv[1]
            )
        }

    return RankerModel(
        kind=train.kind,
        estimator=estimator,
        features=features,
        importances=importances,
        trained_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )


def artifact_name(kind: str) -> str:
    return f"ranker_{kind}"


def save_ranker(model: RankerModel):
    return registry.save(artifact_name(model.kind), model)


def load_ranker(kind: str) -> RankerModel:
    return registry.load(artifact_name(kind))

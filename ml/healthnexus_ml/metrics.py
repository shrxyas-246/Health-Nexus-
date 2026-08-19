"""Ranking and classification metrics used by training and evaluation."""

from __future__ import annotations

import numpy as np


def dcg_at_k(relevance: np.ndarray, k: int) -> float:
    relevance = np.asarray(relevance, dtype=float)[:k]
    if relevance.size == 0:
        return 0.0
    discounts = 1.0 / np.log2(np.arange(2, relevance.size + 2))
    return float(((2**relevance - 1) * discounts).sum())


def ndcg_at_k(y_true: np.ndarray, y_score: np.ndarray, k: int = 5) -> float:
    """NDCG@k for a single query."""
    y_true = np.asarray(y_true, dtype=float)
    order = np.argsort(-np.asarray(y_score, dtype=float), kind="stable")
    ideal = dcg_at_k(np.sort(y_true)[::-1], k)
    if ideal == 0:
        return 0.0
    return dcg_at_k(y_true[order], k) / ideal


def grouped_ndcg(y_true, y_score, groups, k: int = 5) -> float:
    """Mean NDCG@k across queries."""
    y_true, y_score, groups = map(np.asarray, (y_true, y_score, groups))
    scores = [
        ndcg_at_k(y_true[groups == g], y_score[groups == g], k) for g in np.unique(groups)
    ]
    return float(np.mean(scores)) if scores else 0.0


def hit_rate_at_k(y_true, y_score, groups, k: int = 3) -> float:
    """Share of queries where the truly best candidate lands in the top k."""
    y_true, y_score, groups = map(np.asarray, (y_true, y_score, groups))
    hits = []
    for g in np.unique(groups):
        mask = groups == g
        truth, scores = y_true[mask], y_score[mask]
        best = int(np.argmax(truth))
        top_k = np.argsort(-scores, kind="stable")[:k]
        hits.append(1.0 if best in top_k else 0.0)
    return float(np.mean(hits)) if hits else 0.0


def mean_reciprocal_rank(y_true, y_score, groups) -> float:
    """MRR of the truly best candidate under the predicted ordering."""
    y_true, y_score, groups = map(np.asarray, (y_true, y_score, groups))
    reciprocals = []
    for g in np.unique(groups):
        mask = groups == g
        best = int(np.argmax(y_true[mask]))
        order = list(np.argsort(-y_score[mask], kind="stable"))
        reciprocals.append(1.0 / (order.index(best) + 1))
    return float(np.mean(reciprocals)) if reciprocals else 0.0


def spearman(a, b) -> float:
    """Rank correlation without pulling in scipy."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a.size < 2:
        return 0.0
    ra, rb = _rankdata(a), _rankdata(b)
    ra, rb = ra - ra.mean(), rb - rb.mean()
    denominator = np.sqrt((ra**2).sum() * (rb**2).sum())
    return float((ra * rb).sum() / denominator) if denominator else 0.0


def _rankdata(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="stable")
    ranks = np.empty(len(values), dtype=float)
    ranks[order] = np.arange(1, len(values) + 1, dtype=float)
    # Average ties so correlations are not biased by input order.
    unique, inverse, counts = np.unique(values, return_inverse=True, return_counts=True)
    if (counts > 1).any():
        sums = np.zeros(len(unique))
        np.add.at(sums, inverse, ranks)
        ranks = (sums / counts)[inverse]
    return ranks


def ranking_report(y_true, y_score, groups, utility=None) -> dict[str, float]:
    report = {
        "ndcg@3": round(grouped_ndcg(y_true, y_score, groups, 3), 4),
        "ndcg@5": round(grouped_ndcg(y_true, y_score, groups, 5), 4),
        "hit@1": round(hit_rate_at_k(y_true, y_score, groups, 1), 4),
        "hit@3": round(hit_rate_at_k(y_true, y_score, groups, 3), 4),
        "mrr": round(mean_reciprocal_rank(y_true, y_score, groups), 4),
    }
    if utility is not None:
        report["spearman_vs_true_utility"] = round(spearman(utility, y_score), 4)
    return report

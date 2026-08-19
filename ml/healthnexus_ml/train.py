"""Train, evaluate and persist every Health Nexus model.

    python -m healthnexus_ml.train                 # everything
    python -m healthnexus_ml.train --only ranker   # just the recommenders
    python -m healthnexus_ml.train --queries 6000  # bigger ranking corpus

Every model is scored against a baseline it has to beat before it is worth
shipping: the recommenders against the rule-based ranking the API uses today,
the classifiers against a majority-class predictor, the regressors against
predicting the mean. Results land in ``artifacts/metrics.json`` and are printed
as a table.

Ranking is split by *query*, never by row — putting candidates from one query on
both sides of the split leaks the answer and inflates NDCG.
"""

from __future__ import annotations

import argparse
import json
import os
import warnings
from datetime import UTC, datetime

# joblib probes physical core count via wmic, which no longer ships on Windows 11.
os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 4))

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    mean_absolute_error,
    r2_score,
    recall_score,
)
from sklearn.model_selection import train_test_split

from healthnexus_ml import baselines, metrics as rank_metrics
from healthnexus_ml.config import ARTIFACT_DIR, RANK_KINDS, RANDOM_SEED
from healthnexus_ml.datagen import chat as chat_data
from healthnexus_ml.datagen import ranking as rank_data
from healthnexus_ml.datagen import wellness as wellness_data
from healthnexus_ml.knowledge import RESTRICTION_LABELS
from healthnexus_ml.models import ranker as ranker_model
from healthnexus_ml.models import triage as triage_model
from healthnexus_ml.models import wellness as wellness_model

warnings.filterwarnings("ignore", category=UserWarning, module="joblib")


# --- model 3: recommenders ---------------------------------------------------------


def train_rankers(n_queries: int = 4000, seed: int = RANDOM_SEED) -> dict:
    report: dict = {}
    for index, kind in enumerate(RANK_KINDS):
        print(f"\n[ranker:{kind}] generating {n_queries} training queries…")
        train = rank_data.build_dataset(kind, n_queries, seed + index)
        # A separate generator seed, so the test queries are genuinely fresh
        # patients and providers rather than a slice of the same draw.
        test = rank_data.build_dataset(kind, max(n_queries // 4, 200), seed + 5000 + index)

        print(f"[ranker:{kind}] fitting on {len(train)} rows / {train.n_queries} queries…")
        model = ranker_model.train_ranker(train, test, seed=seed)

        predictions = model.predict_frame(test.X)
        model_report = rank_metrics.ranking_report(test.y, predictions, test.groups, test.utility)

        heuristic = np.concatenate(
            [
                baselines.heuristic_scores(kind, q["patient"], q["candidates"], q["context"])
                for q in test.queries
            ]
        )
        heuristic_report = rank_metrics.ranking_report(
            test.y, heuristic, test.groups, test.utility
        )

        model.metrics = {
            "model": model_report,
            "heuristic_baseline": heuristic_report,
            "lift_ndcg@5": round(model_report["ndcg@5"] - heuristic_report["ndcg@5"], 4),
            "lift_hit@1": round(model_report["hit@1"] - heuristic_report["hit@1"], 4),
            "n_train_queries": train.n_queries,
            "n_test_queries": test.n_queries,
            "n_train_rows": len(train),
            "n_features": len(model.features),
            "top_features": dict(list(model.importances.items())[:8]),
        }
        ranker_model.save_ranker(model)
        report[kind] = model.metrics

        print(
            f"[ranker:{kind}] NDCG@5 model {model_report['ndcg@5']:.4f} "
            f"vs heuristic {heuristic_report['ndcg@5']:.4f} "
            f"({model.metrics['lift_ndcg@5']:+.4f})  |  hit@1 "
            f"{model_report['hit@1']:.3f} vs {heuristic_report['hit@1']:.3f}"
        )
    return report


# --- model 1: guidance assistant ---------------------------------------------------


def train_triage(seed: int = RANDOM_SEED) -> dict:
    print("\n[triage] building corpus…")
    texts, intents, urgencies = chat_data.build_corpus(seed=seed % 2**31)
    print(f"[triage] {len(texts)} utterances across {len(set(intents))} intents")

    X_train, X_test, intent_train, intent_test, urgency_train, urgency_test = train_test_split(
        texts, intents, urgencies, test_size=0.25, random_state=seed % 2**31, stratify=intents
    )

    model = triage_model.train_triage(X_train, intent_train, urgency_train)

    intent_predictions = model.intent_clf.predict(X_test)
    urgency_predictions = model.urgency_clf.predict(X_test)

    # The split that matters: phrasings written by hand, absent from the corpus.
    held_out_texts = [t for t, _, _ in chat_data.HELD_OUT_CASES]
    held_out_intents = [i for _, i, _ in chat_data.HELD_OUT_CASES]
    held_out_urgencies = [u for _, _, u in chat_data.HELD_OUT_CASES]
    held_out_results = [model.answer(t) for t in held_out_texts]
    held_out_intent_predictions = [r["intent"] for r in held_out_results]
    held_out_urgency_predictions = [r["urgency"] for r in held_out_results]

    emergency_recall = recall_score(
        urgency_test, urgency_predictions, labels=["emergency"], average="macro", zero_division=0
    )
    held_out_emergency_recall = recall_score(
        held_out_urgencies,
        held_out_urgency_predictions,
        labels=["emergency"],
        average="macro",
        zero_division=0,
    )

    majority = max(set(intent_train), key=intent_train.count)
    model.metrics = {
        "n_utterances": len(texts),
        "n_intents": len(set(intents)),
        "intent_accuracy": round(accuracy_score(intent_test, intent_predictions), 4),
        "intent_macro_f1": round(
            f1_score(intent_test, intent_predictions, average="macro", zero_division=0), 4
        ),
        "intent_majority_baseline": round(
            accuracy_score(intent_test, [majority] * len(intent_test)), 4
        ),
        "urgency_accuracy": round(accuracy_score(urgency_test, urgency_predictions), 4),
        "urgency_emergency_recall": round(float(emergency_recall), 4),
        "held_out_intent_accuracy": round(
            accuracy_score(held_out_intents, held_out_intent_predictions), 4
        ),
        "held_out_urgency_accuracy": round(
            accuracy_score(held_out_urgencies, held_out_urgency_predictions), 4
        ),
        "held_out_emergency_recall": round(float(held_out_emergency_recall), 4),
        "held_out_cases": len(chat_data.HELD_OUT_CASES),
        "trained_at": model.trained_at,
    }

    # An escalation the safety layer misses is the one failure that matters.
    missed = [
        text
        for text, (_, _, urgency), result in zip(
            held_out_texts, chat_data.HELD_OUT_CASES, held_out_results
        )
        if urgency == "emergency" and not result["escalate"]
    ]
    model.metrics["missed_escalations"] = missed
    if missed:
        print(f"[triage] WARNING — emergency phrasings not escalated: {missed}")

    triage_model.save_triage(model)
    print(
        f"[triage] intent acc {model.metrics['intent_accuracy']:.4f} "
        f"(majority {model.metrics['intent_majority_baseline']:.4f}) | "
        f"held-out acc {model.metrics['held_out_intent_accuracy']:.4f} | "
        f"emergency recall {model.metrics['held_out_emergency_recall']:.4f}"
    )
    print(
        classification_report(
            urgency_test, urgency_predictions, zero_division=0, digits=3
        )
    )
    return model.metrics


# --- model 2: wellness plan --------------------------------------------------------


def train_wellness(n: int = 12000, seed: int = RANDOM_SEED) -> dict:
    print(f"\n[wellness] simulating {n} patient records…")
    X, y = wellness_data.build_dataset(n, seed % 2**31)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=seed % 2**31, stratify=y["archetype"]
    )

    model = wellness_model.train_wellness(X_train, y_train, seed=seed % 2**31)

    archetype_predictions = model.archetype_clf.predict(X_test)
    intensity_predictions = model.intensity_clf.predict(X_test)
    calorie_predictions = model.calorie_reg.predict(X_test)
    protein_predictions = model.protein_reg.predict(X_test)

    majority_archetype = y_train["archetype"].mode()[0]
    mean_calories = float(y_train["calorie_target"].mean())

    restriction_scores = {}
    for name in RESTRICTION_LABELS:
        predictions = model.restriction_clfs[name].predict(X_test)
        restriction_scores[name] = {
            "f1": round(f1_score(y_test[name], predictions, zero_division=0), 4),
            "accuracy": round(accuracy_score(y_test[name], predictions), 4),
            "positive_rate": round(float(y_test[name].mean()), 4),
        }

    model.metrics = {
        "n_records": n,
        "archetype_accuracy": round(accuracy_score(y_test["archetype"], archetype_predictions), 4),
        "archetype_macro_f1": round(
            f1_score(y_test["archetype"], archetype_predictions, average="macro", zero_division=0), 4
        ),
        "archetype_majority_baseline": round(
            accuracy_score(y_test["archetype"], [majority_archetype] * len(y_test)), 4
        ),
        "intensity_accuracy": round(
            accuracy_score(y_test["workout_intensity"], intensity_predictions), 4
        ),
        "calorie_mae": round(mean_absolute_error(y_test["calorie_target"], calorie_predictions), 1),
        "calorie_mae_mean_baseline": round(
            mean_absolute_error(y_test["calorie_target"], [mean_calories] * len(y_test)), 1
        ),
        "calorie_r2": round(r2_score(y_test["calorie_target"], calorie_predictions), 4),
        "protein_mae": round(mean_absolute_error(y_test["protein_g"], protein_predictions), 2),
        "protein_r2": round(r2_score(y_test["protein_g"], protein_predictions), 4),
        "restrictions": restriction_scores,
        "restriction_macro_f1": round(
            float(np.mean([s["f1"] for s in restriction_scores.values()])), 4
        ),
        "trained_at": model.trained_at,
    }
    wellness_model.save_wellness(model)
    print(
        f"[wellness] archetype acc {model.metrics['archetype_accuracy']:.4f} "
        f"(majority {model.metrics['archetype_majority_baseline']:.4f}) | "
        f"calorie MAE {model.metrics['calorie_mae']} kcal "
        f"(mean baseline {model.metrics['calorie_mae_mean_baseline']}) | "
        f"restriction macro-F1 {model.metrics['restriction_macro_f1']:.4f}"
    )
    return model.metrics


# --- entry point -------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the Health Nexus models")
    parser.add_argument(
        "--only", choices=["ranker", "triage", "wellness"], help="train one family only"
    )
    parser.add_argument("--queries", type=int, default=4000, help="ranking queries per kind")
    parser.add_argument("--records", type=int, default=12000, help="wellness records")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    args = parser.parse_args()

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    metrics_path = ARTIFACT_DIR / "metrics.json"
    report = {}
    if metrics_path.exists():
        report = json.loads(metrics_path.read_text())

    if args.only in (None, "ranker"):
        report["rankers"] = train_rankers(args.queries, args.seed)
    if args.only in (None, "triage"):
        report["triage"] = train_triage(args.seed)
    if args.only in (None, "wellness"):
        report["wellness"] = train_wellness(args.records, args.seed)

    report["generated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    metrics_path.write_text(json.dumps(report, indent=2))
    print(f"\nMetrics written to {metrics_path}")
    print(f"Artefacts in {ARTIFACT_DIR}")


if __name__ == "__main__":
    main()

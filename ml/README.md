# Health Nexus — machine learning

Three model families, served to the product over one HTTP service.

| # | Model | What it does | Where it shows up |
|---|-------|--------------|-------------------|
| 1 | **Guidance assistant** (`models/triage.py`) | Classifies a patient's question by intent and urgency, answers general health questions, and escalates anything that needs emergency care | The "Health assistant" chat on the Today tab |
| 2 | **Wellness plan** (`models/wellness.py`) | Predicts today's plan archetype, calorie and protein targets, dietary restrictions and training intensity from the patient's record | The three cards on the Plus tab |
| 3 | **Recommenders** (`models/ranker.py`) | Ranks doctors, hospitals, labs, pharmacies and insurance plans for one patient | Every premium recommendation surface |

---

## Quick start

```bash
# from the repo root, using the backend's virtualenv
pip install -r ml/requirements.txt

cd ml
python -m healthnexus_ml.train           # trains all seven artefacts, prints metrics
python -m pytest tests -q                # 44 behaviour tests
uvicorn healthnexus_ml.service:app --port 8100
```

Then point the API at it and restart the backend:

```bash
# backend/.env
ML_SERVICE_URL=http://127.0.0.1:8100
```

That single variable is the whole integration. With it unset, every surface falls
back to the rules that shipped before the models existed — nothing breaks, the
recommendations are just worse.

Verify the wiring end to end:

```bash
cd backend
ML_SERVICE_URL=http://127.0.0.1:8100 python ml_integration_test.py    # 47 checks
```

---

## Results

Everything below is measured on **held-out data**, against a baseline that had to
be beaten for the model to be worth running. Regenerate with
`python -m healthnexus_ml.train`; the full report lands in `artifacts/metrics.json`.

### Model 3 — recommenders

4,000 training queries per kind, 1,000 held-out queries, split by *query* (never
by row — splitting rows puts candidates from the same query on both sides and
inflates every number). The baseline is the hand-tuned ranking the API shipped
with, re-implemented in `baselines.py` and scored on the identical queries.

| Recommender | NDCG@5 model | NDCG@5 heuristic | Lift | MRR model / heuristic |
|---|---|---|---|---|
| Doctor | **0.935** | 0.899 | +0.035 | 0.561 / 0.531 |
| Hospital | **0.914** | 0.781 | +0.133 | 0.518 / 0.442 |
| Lab | **0.851** | 0.809 | +0.042 | 0.490 / 0.473 |
| Pharmacy | **0.840** | 0.751 | +0.089 | 0.480 / 0.419 |
| Insurance | **0.947** | 0.808 | +0.140 | 0.539 / 0.435 |

The two biggest wins are the two places the hand-written rules were weakest:

* **Insurance** — the model's top three features by permutation importance are
  `chronic × covers_pre_existing`, `chronic × waiting_period` and the plan's
  cover-per-premium *rank within the offered set*. The heuristic had a flat +30
  bonus for pre-existing cover; the model learned that for a chronic patient this
  interaction dominates everything else, and that for everyone else it is nearly
  irrelevant.
* **Hospital** — the model leans on speciality match to the patient's actual
  conditions, which the old rule only checked against a free-text `need`
  parameter that is usually absent.

Absolute hit@1 sits near 0.30 for all five. That is a property of the data, not a
weakness of the models: patient preference is partly latent (see below), so the
top two or three candidates are genuinely near-tied and no ranker can separate
them reliably. NDCG and MRR are the honest measures here, and the models beat the
baseline on both across every kind.

### Model 1 — guidance assistant

3,359 utterances, 27 intents, word + character n-gram TF-IDF into logistic
regression.

| Metric | Score | Baseline |
|---|---|---|
| Intent accuracy (random split) | 0.996 | 0.105 (majority class) |
| Intent macro-F1 | 0.995 | — |
| **Intent accuracy (hand-written held-out phrasings)** | **1.000** | — |
| Urgency accuracy | 1.000 | — |
| **Emergency recall (held-out)** | **1.000** | — |

The random-split number is close to meaningless on generated data — it mostly
measures memorisation of the template that produced the row. The number that
matters is the 31 hand-written phrasings in `datagen/chat.py::HELD_OUT_CASES`,
which appear nowhere in the training corpus. That set is what caught the two real
defects during development: an over-eager emergency classification of "throbbing
pain in my head" (fixed by down-weighting the character n-gram block, which was
swamping the word features), and — much more seriously — *"swallowed a whole
strip of pills"* not escalating. Both are now regression-tested.

### Model 2 — wellness plan

12,000 simulated records, 25% held out.

| Head | Metric | Score | Baseline |
|---|---|---|---|
| Plan archetype (8 classes) | accuracy | 0.958 | 0.244 (majority) |
| Plan archetype | macro-F1 | 0.949 | — |
| Workout intensity (3 classes) | accuracy | 0.958 | — |
| Calorie target | MAE | **103 kcal** | 355 kcal (mean) |
| Calorie target | R² | 0.906 | — |
| Protein target | MAE | **4.9 g** | — |
| Protein target | R² | 0.879 | — |
| Dietary restrictions (7 binary heads) | macro-F1 | 0.884 | — |

Per-restriction F1: sodium 0.968, sugar 0.969, saturated fat 0.941, caffeine
0.948, alcohol 0.907, potassium 0.788, purine 0.669. The two weak ones are the
two rare ones — purine restriction depends on gout, which about 3% of the
simulated population has, and potassium on renal impairment. Both are the right
places to spend the next round of work.

---

## How the training data was made, and why you should read the numbers carefully

The platform has no click log and no dietitian's caseload — the seed database has
three doctors and two labs. So all three models train on simulated data, and it
is worth being precise about what that does and does not prove.

**Model 3.** `datagen/universe.py` generates a marketplace, then assigns each
patient latent preference weights — price sensitivity, convenience weight,
quality weight — that are **deliberately not exposed as features**. They are only
partly inferable from what the platform can observe (premium status, age,
severity). `datagen/ranking.py` computes each candidate's true utility from those
weights plus noise, and grades relevance 0–4 within the query. So the model is
learning to recover a choice process it can only partially see. That is why the
scores are good but not perfect, and it is the point: labels that were a giveaway
would produce a 0.99 NDCG that meant nothing.

**Model 2.** The labels are a *documented clinical policy* — Mifflin-St Jeor
energy needs, protein targets by goal and renal function, restriction sets by
condition. The model is not discovering nutrition science; it is learning to
apply a reviewed policy across **incomplete records**. 45–55% of simulated
patients have no HbA1c, no lipid panel or no creatinine on file, each record is
attributed to one of eight clinicians with different thresholds, and 4% of
archetype labels are flipped to a clinically adjacent choice. That is the actual
production problem: writing the policy as `if` statements in the API means one
missing lab value drops a patient to a generic plan, whereas the model infers
from proxies (medicines, diagnoses, BMI, age) and still produces the right plan.

**Model 1.** The corpus is template-generated with paraphrase, typo and
transliteration augmentation, which is why the held-out hand-written set —
not the random split — is the number quoted above.

**When real usage data arrives**, `train.py` is the only file that needs to
change for models 1 and 3: swap the generated dataset for logged queries and
outcomes, keep the featuriser, the metrics and the baseline comparison exactly as
they are. The featuriser (`features.py`) already runs on production payloads
unchanged, so there is no offline/online skew to unpick.

---

## Safety

The assistant is the only model that talks directly to patients, so its
guardrails are in code, not left to the classifier:

1. **A deterministic red-flag phrase list runs before the model.** If it fires,
   the model's opinion is discarded and the answer is "get emergency care now".
   Rules first, because the cost of a missed emergency is not symmetric with the
   cost of a false alarm.
2. **The urgency head escalates at a probability of 0.35**, not 0.5 — biased
   towards over-escalation on purpose.
3. **Low intent confidence falls back** to a capabilities message rather than
   guessing at an answer.
4. **Answer text is written and reviewed**, not generated. The model chooses
   *which* reviewed answer to give. It never names a drug or dose to start or
   stop, never diagnoses, and every non-trivial answer carries the disclaimer.
5. **The fallback escalates too.** When the ML service is down the backend's FAQ
   rules take over — and they keep their own emergency keyword check, so an
   outage cannot turn off escalation.

`tests/test_models.py::test_emergencies_always_escalate` is the test that must
never be allowed to fail.

---

## Layout

```
ml/
  healthnexus_ml/
    config.py        paths and model versions
    knowledge.py     clinical vocabulary shared by data, features and service
    features.py      model 3 featuriser — the same code offline and online
    baselines.py     the shipped heuristic, for honest lift measurement
    metrics.py       NDCG, MRR, hit rate, Spearman
    reasons.py       the "why" attached to every ranked result
    llm.py           optional LLM narration over model 2's output
    train.py         trains and evaluates everything; writes artifacts/metrics.json
    service.py       the FastAPI service the backend calls
    datagen/         universe, ranking labels, chat corpus, wellness records
    models/          ranker, triage, wellness, registry
  artifacts/         trained .joblib bundles + metrics.json
  tests/             44 behaviour and contract tests
```

## Service API

| Endpoint | Model | Notes |
|---|---|---|
| `POST /rank` | 3 | The contract the backend already had, unchanged |
| `POST /chat` | 1 | Returns answer, intent, urgency, escalate |
| `POST /wellness/plan` | 2 | Returns the three plan cards |
| `GET /health` | — | Which artefacts loaded |
| `GET /models` | — | Versions and held-out metrics for everything running |

Artefacts load lazily and cache. A missing artefact degrades that one endpoint to
a 503 rather than stopping the service, and the backend treats any non-200 as
"use the fallback" — so one untrained model can never take the product down.

## On the "fine-tuned LLM" in the spec

Model 2 was specified as a fine-tuned LLM. Fine-tuning is not available for
Claude, and no local base model ships with this repo, so what is built instead is
the standard architecture for this task: **trained models decide everything
clinical** (archetype, calorie and protein targets, restrictions, intensity), and
an optional LLM rewrites only the one-line *explanation* in the patient's context
(`llm.py`, off unless `HNX_LLM_NARRATION=1` and a key are set). An LLM is not
permitted to invent a target, and the structured payload is kept whatever comes
back. If a fine-tuned open-weights model is added later it slots in behind the
same `narrate` interface with no change above it.

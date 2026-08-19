# Health Nexus

A connected healthcare ecosystem: patients, doctors, hospitals, diagnostic labs,
pharmacies and insurers on one platform.

The patient and doctor journeys are wired end to end against a real database.
The other four roles have complete schemas and working APIs; their dedicated
frontends are the next slice of work.

---

## Running it

Two terminals. Backend first.

**Backend** (Python 3.11+)

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env            # optional — defaults work as-is
python seed.py                  # creates the DB and loads demo data
uvicorn app.main:app --reload   # http://127.0.0.1:8000
```

Interactive API docs: <http://127.0.0.1:8000/docs>

**Frontend** (Node 18+)

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

Vite proxies `/api` to the backend, so the browser never needs its origin.

### Demo accounts

All use the password `Password123!`

| Role | Email | Notes |
|---|---|---|
| Patient | `rahul.verma@example.com` | Premium, two years of history |
| Patient | `aisha.khan@example.com` | Free tier — shows the premium gate |
| Doctor | `ananya.sharma@healthnexus.app` | Rahul's treating physician |
| Doctor | `rakesh.iyer@healthnexus.app` | Cardiology |
| Doctor | `meera.nair@healthnexus.app` | Endocrinology |
| Hospital | `ops@apollo.health` | |
| Lab | `ops@metropolis.in` | |
| Pharmacy | `ops@wellnessforever.in` | |
| Insurer | `claims@hdfcergo.in` | |

### Verifying it works

```bash
cd backend
python seed.py && python smoke_test.py
```

116 checks covering auth, access control, prescription versioning, lab and
pharmacy orders, claims, commission splits, recommendations, reminders,
the chatbot and the emergency flow. A further 47 checks in
`ml_integration_test.py` confirm the trained models — not the fallbacks — are
driving each surface, and that the fallbacks hold when the ML service is down.

---

## How it is put together

```
backend/
  app/
    core/        config, JWT security, enums
    db/          engine, session, declarative base
    models/      44 SQLAlchemy tables across 6 domains
    schemas/     Pydantic request/response contracts
    api/
      deps.py    authentication + the record-access rules
      v1/        routers, one per domain
    services/    timeline, payments, ratings, recommendations, ML client
  seed.py        demo dataset
  smoke_test.py  end-to-end journey checks
frontend/
  src/
    lib/api.js         typed-ish API client
    context/           auth session + toast/modal UI state
    hooks/             useResource — load / error / empty lifecycle
    sections/          one component per screen section
```

### Key design decisions

**Prescriptions are immutable.** Editing one writes a new row pointing at
`supersedes_id` and marks the old version `superseded`. Nothing is ever
overwritten, so the full drug history stays auditable. `GET
/prescriptions/{id}/versions` walks the chain in both directions.

**The timeline is materialised, not derived.** Services append to
`timeline_events` whenever a clinical record is created, so the patient's
history reads with one query. Records a provider generated are locked; entries
the patient backfilled themselves stay editable. The API enforces that
distinction — it is not just a UI affordance.

**Record access needs a real care relationship.** `deps.resolve_patient_access`
lets a doctor in only via care-team membership, a past encounter, or a booked
appointment. A doctor with no relationship gets a 403, tested explicitly.

**Commission is recorded on the payment row.** Every transaction stores
`amount`, `commission_rate`, `commission_amount` and `payout_amount`, so the
platform's cut and the provider's settlement are both auditable per payment.

**Cover is consumed on settlement, not approval.** An approved claim does not
touch `used_amount` until it is actually settled.

---

## The ML integration

All three models are **built, trained, tested and wired in** — see
[`ml/README.md`](ml/README.md) for the architecture, the metrics and how the
training data was made.

```bash
pip install -r ml/requirements.txt
cd ml
python -m healthnexus_ml.train                       # trains all seven artefacts
python -m pytest tests -q                            # 44 tests
uvicorn healthnexus_ml.service:app --port 8100
```

Then set one variable in `backend/.env` and restart the API:

```
ML_SERVICE_URL=http://127.0.0.1:8100
```

That is the entire integration. Unset it and every surface falls back to the
rules that shipped before the models existed — nothing breaks, the
recommendations are just worse.

```bash
cd backend
ML_SERVICE_URL=http://127.0.0.1:8100 python ml_integration_test.py   # 47 checks
```

### Model 1 — health guidance assistant

Two classifier heads (27 intents, 3 urgency levels) over word + character
n-gram TF-IDF. Serves the chat on the Today tab via `POST /chat`.

**100% intent accuracy and 100% emergency recall** on 31 hand-written phrasings
that appear nowhere in the training corpus — the split that actually measures
generalisation, rather than the random split (99.6%) which mostly measures
memorisation.

Safety is enforced in code, not left to the classifier: a deterministic red-flag
phrase list runs *before* the model and overrides it, the urgency head escalates
at p ≥ 0.35 rather than 0.5, low-confidence intents fall back to a safe
capabilities message, and answer text is written and reviewed — the model only
chooses which reviewed answer to give. The backend's FAQ fallback keeps its own
escalation check, so an ML outage cannot switch escalation off.

### Model 2 — daily wellness plan (premium)

Five heads over one patient feature row: plan archetype (8 classes), workout
intensity (3), calorie target, protein target, and seven independent binary
dietary-restriction heads. Writes the three cards the Plus tab already rendered,
cached as `ml_recommendations` rows for a day, with a "rebuild from my latest
record" button.

Archetype accuracy **0.958** (majority baseline 0.244), calorie MAE **103 kcal**
(mean baseline 355), protein MAE **4.9 g**, restriction macro-F1 **0.884**. The
models learn a documented clinical policy across *incomplete* records — around
half the simulated patients are missing the lab value that would decide the
plan, which is exactly why this is a model and not an `if` statement.

### Model 3 — recommender systems (premium)

One gradient-boosted ranker per kind, trained pointwise on graded relevance and
evaluated over held-out *queries*. Every one beats the hand-tuned ranking the API
shipped with, measured on identical queries:

| Recommender | NDCG@5 model | NDCG@5 heuristic | Lift |
|---|---|---|---|
| Doctor | 0.935 | 0.899 | +0.035 |
| Hospital | 0.914 | 0.781 | +0.133 |
| Lab | 0.851 | 0.809 | +0.042 |
| Pharmacy | 0.840 | 0.751 | +0.089 |
| Insurance | 0.947 | 0.808 | +0.140 |

The biggest gains are where the rules were weakest. For insurance the model's
top features are the *interactions* `chronic × covers_pre_existing` and
`chronic × waiting_period` — the old rule gave a flat bonus for pre-existing
cover; the model learned it dominates for a chronic patient and barely matters
for anyone else.

Features are computed by the same code offline and online
(`ml/healthnexus_ml/features.py`), so there is no training/serving skew, and each
result carries a plain-English reason.

---

## Status

**Working end to end:** all three ML model families trained, tested and
serving; authentication for all six roles, patient record and
timeline, conditions, vitals, allergies, documents, prescription writing and
versioning, appointment booking, lab booking and reporting, pharmacy orders,
insurance claims through to settlement, payments with commission, reviews and
ratings, patient–doctor and doctor–doctor chat, the article feed, reminders,
the guidance chatbot, all five recommenders, and one-tap emergency dispatch.

**Next for the models:** retrain on real usage once there is a click log —
`train.py` is the only file that changes; swap the generated dataset for logged
queries and keep the featuriser, metrics and baseline comparison as they are.
The two weakest heads (purine and potassium restrictions, F1 0.67 and 0.79) are
rare-class problems worth the next round of work.

**Next:** dedicated frontends for the hospital, lab, pharmacy and insurer
consoles (their APIs are done and tested); real file uploads (currently URL
references); a payment gateway behind `services/payments.record_payment`;
Alembic migrations for production; WebSockets for live chat.

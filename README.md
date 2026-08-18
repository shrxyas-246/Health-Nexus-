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
the chatbot and the emergency flow.

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

Three models are planned. Each has a working non-ML implementation behind it, so
every surface functions today and improves when a model is plugged in — no
frontend changes needed.

### Model 1 — health guidance chatbot

**Where it plugs in:** `app/api/v1/wellness.py` → the `_answer(question)` function.

Currently rule-based over `FAQ_RULES`. It already implements the safety
behaviour you specified: `ESCALATION_KEYWORDS` catches critical symptoms (chest
pain, breathlessness, self-harm, stroke…) and returns a hard redirect to
emergency care or a doctor, with `escalated_to_doctor` set on the stored
message. Every non-urgent answer carries a not-a-diagnosis disclaimer.

Replace `_answer` with a call to the agent. Keep the escalation check running
*before* the model — a safety gate should not depend on model output. Transcript
persistence (`chatbot_messages`) is already in place for context.

### Model 2 — fine-tuned health-maintenance LLM (premium)

**Where it plugs in:** the `ml_recommendations` table and
`GET /api/v1/recommendations/daily`.

The pipeline writes rows with `kind` in `diet` / `workout` / `lifestyle`, a
`title`, a `rationale`, and a free-form JSON `payload`. The frontend already
renders three payload shapes (nutrient targets + meals, workout sessions,
single lifestyle change), so a model producing those keys needs no UI work.

`services/recommendations.patient_features()` assembles the input the model
needs — age, BMI, allergies, active conditions with severity — and the current
prescription, doctor's diet advice and vitals history are all queryable off the
same patient id.

### Model 3 — recommender systems (premium)

**Where it plugs in:** `app/services/ml_client.py` → `get_ranking()`.

Set `ML_SERVICE_URL` and every recommender forwards to it:

```
POST {ML_SERVICE_URL}/rank
{ "kind": "doctor" | "hospital" | "lab" | "pharmacy" | "insurance",
  "patient": {...features...},
  "candidates": [{"id": 1, ...features...}],
  "context": {...} }

-> { "model_version": "v1",
     "ranked": [{"id": 1, "score": 0.93, "reason": "..."}] }
```

If the service is unreachable the request does not fail — it falls back to the
heuristics in `services/recommendations.py`, which produce the identical
response shape. The candidate features passed to the model are exactly the
signals you described:

- **Doctor / hospital** — condition severity drives the weighting. At
  `severity >= severe` the ranking shifts from convenience to outcomes:
  `complex_case_success_rate`, `procedures_performed`, and for hospitals
  `surgery_success_rate`, `complex_cases_handled` and accreditation. Below that
  threshold, distance and rating dominate. A generalist is actively penalised
  for a severe case.
- **Lab** — the requested test basket is priced against each lab's own
  catalogue; coverage, accreditation, home collection, distance and the real
  quoted total all feed in, with an explicit bonus for the cheapest complete
  basket.
- **Pharmacy** — the patient's live prescription is priced item by item against
  each store's stock. Stores missing items are marked; the cheapest store that
  can fill the *whole* order is boosted.
- **Insurance** — cover-per-premium ratio, pre-existing-condition cover weighted
  by whether the patient actually has a chronic condition, insurer settlement
  ratio and network size.

---

## Status

**Working end to end:** authentication for all six roles, patient record and
timeline, conditions, vitals, allergies, documents, prescription writing and
versioning, appointment booking, lab booking and reporting, pharmacy orders,
insurance claims through to settlement, payments with commission, reviews and
ratings, patient–doctor and doctor–doctor chat, the article feed, reminders,
the guidance chatbot, all five recommenders, and one-tap emergency dispatch.

**Next:** dedicated frontends for the hospital, lab, pharmacy and insurer
consoles (their APIs are done and tested); real file uploads (currently URL
references); a payment gateway behind `services/payments.record_payment`;
Alembic migrations for production; WebSockets for live chat.

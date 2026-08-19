"""Proves the trained models are actually driving the product surfaces.

`smoke_test.py` checks the journeys work. This checks *which brain* is answering:
with ML_SERVICE_URL set, recommendations must be model-ranked, the assistant must
be the trained classifier, and the daily plan must carry the wellness model's
version — and with it unset, every one of those must still work on the fallbacks.

Run with the ML service up:

    uvicorn healthnexus_ml.service:app --port 8100      # from ml/
    ML_SERVICE_URL=http://127.0.0.1:8100 python ml_integration_test.py
"""

import sys

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services import ml_client

PASSWORD = "Password123!"
PREMIUM_PATIENT = "rahul.verma@example.com"

client = TestClient(app)
passed = 0
failed: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global passed
    if condition:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed.append(f"{label} — {detail}")
        print(f"  FAIL  {label}  {detail}")


def login(email: str) -> dict:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


if not settings.ML_SERVICE_URL:
    print("ML_SERVICE_URL is not set — start the ML service and set it, then rerun.")
    sys.exit(1)

if ml_client.service_health() is None:
    print(f"ML service at {settings.ML_SERVICE_URL} is not reachable.")
    sys.exit(1)

patient = login(PREMIUM_PATIENT)

print("\n=== service wiring ===")
status = client.get("/api/v1/ml/status", headers=patient).json()
check("backend reports the ML service reachable", status["reachable"] is True, str(status))
check(
    "all seven artefacts are loaded",
    all(status["service"]["artifacts"].values()),
    str(status["service"]["artifacts"]),
)

print("\n=== model 3: recommendations ===")
for kind, path, params in (
    ("doctors", "/api/v1/recommendations/doctors", ""),
    ("hospitals", "/api/v1/recommendations/hospitals", ""),
    ("labs", "/api/v1/recommendations/labs", "?tests=Complete Blood Count,HbA1c"),
    ("pharmacies", "/api/v1/recommendations/pharmacies", ""),
    ("insurance", "/api/v1/recommendations/insurance", ""),
):
    response = client.get(path + params, headers=patient)
    body = response.json() if response.status_code == 200 else []
    check(f"{kind} are recommended", response.status_code == 200 and len(body) > 0, response.text[:120])
    if body:
        scores = [item["match_score"] for item in body]
        # The model emits a calibrated 0-100 match score; the heuristic it
        # replaced routinely runs past 150, so this distinguishes the two.
        check(
            f"{kind} carry a model match score (0-100)",
            all(0 <= s <= 100 for s in scores),
            str(scores),
        )
        check(
            f"{kind} are returned best-first",
            scores == sorted(scores, reverse=True),
            str(scores),
        )
        check(f"{kind} explain themselves", all(item["match_reason"] for item in body))

print("\n=== model 2: daily wellness plan ===")
refreshed = client.post("/api/v1/recommendations/daily/refresh", headers=patient)
cards = refreshed.json() if refreshed.status_code == 200 else []
check("the plan rebuilds on demand", refreshed.status_code == 200, refreshed.text[:150])
check("three cards: diet, workout, lifestyle",
      sorted(c["kind"] for c in cards) == ["diet", "lifestyle", "workout"], str([c["kind"] for c in cards]))
check("cards are stamped with the wellness model version",
      all(c["model_version"] == "wellness-v1" for c in cards),
      str({c["kind"]: c["model_version"] for c in cards}))

diet = next((c for c in cards if c["kind"] == "diet"), None)
if diet:
    targets = diet["payload"]["targets"]
    check("diet card carries a calorie target", 1200 <= targets["kcal_a_day"] <= 4200, str(targets))
    check("diet card carries a protein target", 35 <= targets["g_protein"] <= 190, str(targets))
    check("diet card carries meals", len(diet["payload"]["meals"]) >= 3)
    # The seeded patient has type 2 diabetes and borderline high cholesterol,
    # with a normal blood pressure — so the right answer is a sugar limit and a
    # saturated fat limit, and *no* sodium limit.
    restrictions = set(diet["payload"]["restrictions"])
    check("diabetes produces a sugar limit", "sugar_limit" in restrictions, str(restrictions))
    check("high cholesterol produces a saturated fat limit",
          "saturated_fat_limit" in restrictions, str(restrictions))
    check("normal blood pressure does not produce a sodium limit",
          "sodium_limit" not in restrictions, str(restrictions))

workout = next((c for c in cards if c["kind"] == "workout"), None)
if workout:
    check("workout card carries sessions", len(workout["payload"]["sessions"]) > 0)
    check("workout intensity is one of the three trained classes",
          workout["payload"]["intensity"] in {"gentle", "moderate", "vigorous"})

check("the cached plan now serves the model's cards",
      [c["id"] for c in client.get("/api/v1/recommendations/daily", headers=patient).json()]
      == [c["id"] for c in cards])

print("\n=== model 1: guidance assistant ===")
reply = client.post(
    "/api/v1/wellness/chatbot/ask", headers=patient, json={"question": "how much protein do i need"}
).json()
check("a general question is answered", len(reply) == 2 and len(reply[1]["body"]) > 80)
check("the answer carries the disclaimer", "not a diagnosis" in reply[1]["body"].lower())
check("the answer is not escalated", reply[1]["escalated_to_doctor"] is False)

personal = client.post(
    "/api/v1/wellness/chatbot/ask", headers=patient, json={"question": "i missed my tablet today"}
).json()
check("the answer is grounded in the patient's own prescription",
      "prescription" in personal[1]["body"].lower(), personal[1]["body"][:160])

for urgent in ("crushing pain in my chest and left arm", "my father collapsed and is not responding",
               "i swallowed a whole strip of pills", "i dont want to be alive anymore"):
    escalated = client.post(
        "/api/v1/wellness/chatbot/ask", headers=patient, json={"question": urgent}
    ).json()
    check(f"escalates: {urgent[:38]}…",
          escalated[1]["escalated_to_doctor"] is True and "Emergency" in escalated[1]["body"],
          escalated[1]["body"][:100])

print("\n=== fallback when the model is down ===")
original = settings.ML_SERVICE_URL
settings.ML_SERVICE_URL = "http://127.0.0.1:1"  # nothing listening
try:
    down = client.get("/api/v1/recommendations/doctors", headers=patient)
    check("recommendations fall back to the heuristic instead of failing",
          down.status_code == 200 and len(down.json()) > 0, down.text[:120])
    chat = client.post(
        "/api/v1/wellness/chatbot/ask", headers=patient, json={"question": "how much water should i drink"}
    )
    check("the assistant falls back to the FAQ rules",
          chat.status_code == 200 and len(chat.json()[1]["body"]) > 40, chat.text[:120])
    chat_urgent = client.post(
        "/api/v1/wellness/chatbot/ask", headers=patient, json={"question": "i have chest pain"}
    ).json()
    check("the fallback still escalates emergencies",
          chat_urgent[1]["escalated_to_doctor"] is True, str(chat_urgent[1])[:120])
    cached = client.get("/api/v1/recommendations/daily", headers=patient)
    check("the cached plan is still served while the model is down",
          cached.status_code == 200 and len(cached.json()) == 3, cached.text[:120])
    stale = client.post("/api/v1/recommendations/daily/refresh", headers=patient)
    check("a forced rebuild reports the outage honestly", stale.status_code == 503, str(stale.status_code))
finally:
    settings.ML_SERVICE_URL = original

print("\n" + "=" * 60)
print(f"  {passed} passed, {len(failed)} failed")
if failed:
    print("\nFailures:")
    for item in failed:
        print(f"  - {item}")
    sys.exit(1)
print("  Models are serving every surface, and the fallbacks hold when they are not.")

"""End-to-end check of the main journeys against the seeded database.

Run with:  python smoke_test.py     (expects `python seed.py` to have run first)
"""

from fastapi.testclient import TestClient

from app.main import app

PASSWORD = "Password123!"
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


print("\n=== auth ===")
patient = login("rahul.verma@example.com")
doctor = login("ananya.sharma@healthnexus.app")
other_doctor = login("meera.nair@healthnexus.app")
lab = login("ops@metropolis.in")
pharmacy = login("ops@wellnessforever.in")
insurer = login("claims@hdfcergo.in")
hospital = login("ops@apollo.health")
check("login issues tokens for all six roles", True)

me = client.get("/api/v1/auth/me", headers=patient).json()
check("auth/me returns the patient", me["email"] == "rahul.verma@example.com", str(me))
check("unauthenticated request is rejected", client.get("/api/v1/patients/me").status_code == 401)

print("\n=== patient record ===")
profile = client.get("/api/v1/patients/me", headers=patient).json()
patient_id = profile["id"]
check("profile has medical id", profile["medical_id"] == "HNX-482913", str(profile.get("medical_id")))
check("BMI is computed", profile["bmi"] == 23.7, str(profile.get("bmi")))
check("age is computed", isinstance(profile["age"], int) and profile["age"] > 30, str(profile.get("age")))
check("allergies are attached", len(profile["allergies"]) == 2, str(len(profile["allergies"])))

summary = client.get("/api/v1/patients/me/summary", headers=patient).json()
check("summary returns 6 metric tiles", len(summary["metrics"]) == 6, str(len(summary["metrics"])))
check("summary counts active medicines", summary["active_medicines"] == 3, str(summary["active_medicines"]))
check("summary counts active conditions", summary["active_conditions"] == 2, str(summary["active_conditions"]))
check("summary shows insurance active", summary["insurance_status"] == "Active", summary["insurance_status"])
check("summary has activity feed", len(summary["activity"]) > 0)

timeline = client.get(f"/api/v1/patients/{patient_id}/timeline", headers=patient).json()
check("timeline is populated", len(timeline) >= 10, str(len(timeline)))
check("timeline is newest first", timeline[0]["occurred_at"] >= timeline[-1]["occurred_at"])
check("timeline resolves doctor names", any(e["doctor_name"] for e in timeline))

conditions = client.get(f"/api/v1/patients/{patient_id}/conditions", headers=patient).json()
check("conditions include chronic + resolved", len(conditions) == 3, str(len(conditions)))

vitals = client.get(f"/api/v1/patients/{patient_id}/vitals?kind=hba1c&days=3650", headers=patient).json()
check("HbA1c series trends downward", vitals[0]["value"] == 7.4 and vitals[-1]["value"] == 5.8,
      str([v["value"] for v in vitals]))

print("\n=== access control ===")
other = client.get("/api/v1/patients/lookup/HNX-771204", headers=patient)
check("patient cannot read another patient's record", other.status_code == 403, str(other.status_code))
check("treating doctor can read the record",
      client.get(f"/api/v1/patients/{patient_id}", headers=doctor).status_code == 200)
check("unrelated doctor is blocked",
      client.get(f"/api/v1/patients/{patient_id}", headers=other_doctor).status_code == 403)

print("\n=== prescriptions & versioning ===")
current = client.get(f"/api/v1/prescriptions/patients/{patient_id}/current", headers=patient).json()
check("current prescription is v2", current["version"] == 2, str(current["version"]))
check("current has 3 medicines", len(current["items"]) == 3, str(len(current["items"])))
check("current carries diet advice", bool(current["diet_advice"]))
check("current carries test requests", len(current["test_requests"]) == 2, str(len(current["test_requests"])))

versions = client.get(f"/api/v1/prescriptions/{current['id']}/versions", headers=patient).json()
check("version history has both versions", len(versions) == 2, str(len(versions)))
check("history is newest first", versions[0]["version"] == 2)
check("supersede note is retained", bool(versions[0]["change_note"]))

revision = client.post(
    f"/api/v1/prescriptions/{current['id']}/revise",
    headers=doctor,
    json={
        "change_note": "Atorvastatin increased to 20 mg after cardiology review.",
        "diagnosis_summary": "Type 2 Diabetes controlled; LDL above target",
        "items": [
            {"medicine_name": "Metformin", "strength": "850 mg", "dosage": "1 tablet",
             "frequency": "twice daily", "duration_days": 30, "quantity": 60},
            {"medicine_name": "Atorvastatin", "strength": "20 mg", "dosage": "1 tablet",
             "frequency": "nightly", "duration_days": 30, "quantity": 30},
        ],
    },
)
check("doctor can revise a prescription", revision.status_code == 200, revision.text[:200])
if revision.status_code == 200:
    rev = revision.json()
    check("revision is v3", rev["version"] == 3, str(rev["version"]))
    check("revision links to previous", rev["supersedes_id"] == current["id"])
    old = client.get(f"/api/v1/prescriptions/{current['id']}", headers=patient).json()
    check("previous version is marked superseded", old["status"] == "superseded", old["status"])
    check("previous version keeps its 3 items", len(old["items"]) == 3, str(len(old["items"])))

blocked = client.post(
    f"/api/v1/prescriptions/patients/{patient_id}",
    headers=other_doctor,
    json={"items": [{"medicine_name": "Test"}]},
)
check("unrelated doctor cannot prescribe", blocked.status_code == 403, str(blocked.status_code))

print("\n=== labs ===")
labs = client.get("/api/v1/labs", headers=patient).json()
check("lab directory lists labs", len(labs) == 2, str(len(labs)))
tests = client.get("/api/v1/labs/tests/search?q=HbA1c", headers=patient).json()
check("test search finds both labs, cheapest first",
      len(tests) == 2 and tests[0]["price"] <= tests[1]["price"], str([t["price"] for t in tests]))
check("effective price applies the discount",
      tests[0]["effective_price"] < tests[0]["price"], str(tests[0]))

catalogue = client.get(f"/api/v1/labs/{labs[0]['id']}/tests", headers=patient).json()
booking = client.post(
    "/api/v1/labs/orders",
    headers=patient,
    json={"lab_id": labs[0]["id"], "lab_test_ids": [catalogue[0]["id"]], "home_collection": False},
)
check("patient can book a test", booking.status_code == 201, booking.text[:200])
if booking.status_code == 201:
    order = booking.json()
    check("booking is priced", order["total_amount"] > 0, str(order["total_amount"]))
    check("booking starts as booked", order["status"] == "booked", order["status"])

    filed = client.post(
        f"/api/v1/labs/patients/{patient_id}/reports",
        headers=lab,
        json={
            "title": "Follow-up panel", "lab_order_id": order["id"],
            "summary": "Within range.",
            "values": [{"analyte": "HbA1c", "value": 5.6, "unit": "%", "ref_high": 5.7}],
        },
    )
    check("lab can file a report", filed.status_code == 201, filed.text[:200])
    if filed.status_code == 201:
        rep = filed.json()
        check("report auto-flags normal values", rep["values"][0]["flag"] == "normal", str(rep["values"][0]))
        check("filing a report closes the order",
              client.get("/api/v1/labs/orders/me", headers=patient).json()[0]["status"] == "ready")

reports = client.get(f"/api/v1/patients/{patient_id}/reports", headers=patient).json()
check("report history is present", len(reports) >= 3, str(len(reports)))
flagged = [v for r in reports for v in r["values"] if v.get("flag") == "high"]
check("abnormal values are flagged high", len(flagged) >= 3, str(len(flagged)))

inbox = client.get("/api/v1/doctors/me/inbox/reports?unreviewed_only=false", headers=doctor).json()
check("doctor receives forwarded reports", len(inbox) >= 1, str(len(inbox)))

print("\n=== pharmacy ===")
quote = client.post(
    f"/api/v1/pharmacies/{2}/quote?prescription_id={current['id']}", headers=patient
)
check("pharmacy quote prices a prescription", quote.status_code == 200, quote.text[:200])
placed = client.post(
    "/api/v1/pharmacies/orders",
    headers=patient,
    json={"pharmacy_id": 1, "prescription_id": current["id"], "delivery": True},
)
check("patient can forward a prescription to a store", placed.status_code == 201, placed.text[:200])
if placed.status_code == 201:
    mo = placed.json()
    check("order totals include delivery", mo["total_amount"] == mo["subtotal"] + mo["delivery_fee"],
          str(mo["total_amount"]))
    accepted = client.patch(
        f"/api/v1/pharmacies/orders/{mo['id']}/status", headers=pharmacy, json={"status": "ready"}
    )
    check("pharmacy can accept and mark ready", accepted.status_code == 200, accepted.text[:200])
    check("incoming queue shows the order",
          any(o["id"] == mo["id"] for o in client.get("/api/v1/pharmacies/orders/incoming", headers=pharmacy).json()))

print("\n=== appointments ===")
booked = client.post(
    "/api/v1/appointments",
    headers=patient,
    json={"doctor_id": 1, "scheduled_at": "2026-09-15T10:30:00Z", "reason": "Review"},
)
check("patient can book an appointment", booked.status_code == 201, booked.text[:200])
if booked.status_code == 201:
    appt = booked.json()
    check("consultation fee is applied", appt["fee"] == 800, str(appt["fee"]))
    clash = client.post(
        "/api/v1/appointments",
        headers=patient,
        json={"doctor_id": 1, "scheduled_at": "2026-09-15T10:30:00Z", "reason": "Dup"},
    )
    check("double-booking a slot is refused", clash.status_code == 409, str(clash.status_code))
    confirmed = client.patch(
        f"/api/v1/appointments/{appt['id']}/status", headers=doctor, json={"status": "confirmed"}
    )
    check("doctor can confirm", confirmed.status_code == 200, confirmed.text[:200])
    done = client.patch(
        f"/api/v1/appointments/{appt['id']}/status", headers=doctor, json={"status": "completed"}
    )
    check("completing creates an encounter", done.json().get("status") == "completed", done.text[:120])

print("\n=== billing & commission ===")
bill = client.get("/api/v1/billing/summary", headers=patient).json()
check("billing summary totals spend", bill["total_spent"] > 0, str(bill["total_spent"]))
check("billing breaks down by purpose", len(bill["by_purpose"]) >= 4, str(bill["by_purpose"]))
check("settled claims count as reimbursed", bill["reimbursed_amount"] == 62000, str(bill["reimbursed_amount"]))
payments = client.get("/api/v1/billing/payments/me", headers=patient).json()
sample = payments[0]
check("commission is split out on every payment",
      abs(sample["commission_amount"] - round(sample["amount"] * 0.05, 2)) < 0.01, str(sample))
check("payout equals amount minus commission",
      abs(sample["payout_amount"] - (sample["amount"] - sample["commission_amount"])) < 0.01, str(sample))

print("\n=== insurance ===")
policies = client.get("/api/v1/insurance/policies/me", headers=patient).json()
check("policy is linked", len(policies) == 1, str(len(policies)))
policy = policies[0]
check("remaining cover is computed", policy["remaining_amount"] == 938000, str(policy["remaining_amount"]))
check("cover utilisation percent is computed", policy["used_percent"] == 6.2, str(policy["used_percent"]))

claim = client.post(
    "/api/v1/insurance/claims",
    headers=patient,
    json={"patient_policy_id": policy["id"], "amount_claimed": 15000,
          "description": "Diagnostics and consultation",
          "documents": [{"label": "Hospital bill", "file_url": "/uploads/bill.pdf"}]},
)
check("patient can file a claim", claim.status_code == 201, claim.text[:200])
if claim.status_code == 201:
    cl = claim.json()
    check("claim gets a number and submitted status",
          cl["claim_number"].startswith("CLM-") and cl["status"] == "submitted", str(cl["status"]))
    check("claim documents attach", len(cl["documents"]) == 1)
    queue = client.get("/api/v1/insurance/claims/incoming", headers=insurer).json()
    check("insurer sees the claim in its queue", any(c["id"] == cl["id"] for c in queue), str(len(queue)))
    approved = client.post(
        f"/api/v1/insurance/claims/{cl['id']}/decision",
        headers=insurer,
        json={"status": "approved", "amount_approved": 12000, "reviewer_note": "Approved less consumables."},
    )
    check("insurer can approve", approved.status_code == 200, approved.text[:200])
    settled = client.post(
        f"/api/v1/insurance/claims/{cl['id']}/decision", headers=insurer, json={"status": "settled"}
    )
    check("insurer can settle", settled.status_code == 200, settled.text[:200])
    after = client.get("/api/v1/insurance/policies/me", headers=patient).json()[0]
    check("settling consumes policy cover",
          after["used_amount"] == 74000, str(after["used_amount"]))

overclaim = client.post(
    "/api/v1/insurance/claims",
    headers=patient,
    json={"patient_policy_id": policy["id"], "amount_claimed": 99000000},
)
check("claim beyond remaining cover is refused", overclaim.status_code == 409, str(overclaim.status_code))

print("\n=== premium recommendations (model 3 seam) ===")
docs = client.get("/api/v1/recommendations/doctors", headers=patient).json()
check("doctor recommender returns ranked doctors", len(docs) >= 3, str(len(docs)))
check("recommendations carry a score and reason",
      docs[0].get("match_score") is not None and bool(docs[0].get("match_reason")), str(docs[0])[:200])
check("ranking is descending by score",
      all(docs[i]["match_score"] >= docs[i + 1]["match_score"] for i in range(len(docs) - 1)))
check("top match is a speciality relevant to the patient's conditions",
      docs[0]["specialization"] in ("Endocrinology", "General Medicine", "Cardiology", "Diabetology"),
      docs[0]["specialization"])
check("top match explains why it was chosen",
      "Specialises" in docs[0]["match_reason"], docs[0]["match_reason"])

rec_labs = client.get("/api/v1/recommendations/labs?tests=HbA1c,Lipid Profile", headers=patient).json()
check("lab recommender quotes a real basket price",
      rec_labs[0]["quoted_total"] is not None and rec_labs[0]["quoted_total"] > 0, str(rec_labs[0])[:200])
check("cheapest complete basket ranks first",
      rec_labs[0]["quoted_total"] <= rec_labs[1]["quoted_total"],
      str([lb["quoted_total"] for lb in rec_labs]))

rec_ph = client.get("/api/v1/recommendations/pharmacies", headers=patient).json()
check("pharmacy recommender quotes the live prescription",
      rec_ph[0]["quoted_total"] is not None, str(rec_ph[0])[:160])

rec_ins = client.get("/api/v1/recommendations/insurance", headers=patient).json()
check("insurance recommender ranks plans", len(rec_ins) >= 3, str(len(rec_ins)))
check("chronic patient gets a pre-existing-cover plan first",
      rec_ins[0]["covers_pre_existing"] is True, str(rec_ins[0]["name"]))

rec_hosp = client.get("/api/v1/recommendations/hospitals?need=Cardiology", headers=patient).json()
check("hospital recommender weighs surgical success",
      rec_hosp[0]["surgery_success_rate"] is not None, str(rec_hosp[0])[:160])

daily = client.get("/api/v1/recommendations/daily", headers=patient).json()
check("daily advice returns diet/workout payloads (model 2 seam)", len(daily) == 3, str(len(daily)))
check("advice payload carries structured targets",
      "targets" in (daily[0].get("payload") or {}) or "sessions" in (daily[0].get("payload") or {}),
      str(daily[0].get("payload"))[:160])

free = login("aisha.khan@example.com")
gated = client.get("/api/v1/recommendations/doctors", headers=free)
check("non-premium user is gated with 402", gated.status_code == 402, str(gated.status_code))

print("\n=== chatbot (model 1 seam) ===")
answer = client.post("/api/v1/wellness/chatbot/ask", headers=patient, json={"question": "How much water should I drink?"})
check("chatbot answers a general question", answer.status_code == 200 and len(answer.json()) == 2)
check("answer carries the not-a-diagnosis disclaimer",
      "not a diagnosis" in answer.json()[1]["body"].lower(), answer.json()[1]["body"][:120])
urgent = client.post("/api/v1/wellness/chatbot/ask", headers=patient, json={"question": "I have severe chest pain right now"})
check("critical question escalates to a doctor", urgent.json()[1]["escalated_to_doctor"] is True,
      str(urgent.json()[1]))
check("chatbot history is persisted",
      len(client.get("/api/v1/wellness/chatbot/history", headers=patient).json()) == 4)

print("\n=== reminders ===")
today = client.get("/api/v1/wellness/reminders/today", headers=patient).json()
check("today's schedule expands reminder times", len(today) >= 8, str(len(today)))
check("schedule is time-ordered", all(today[i]["due_at"] <= today[i + 1]["due_at"] for i in range(len(today) - 1)))
first = today[0]
completed = client.post(
    f"/api/v1/wellness/reminders/{first['reminder_id']}/complete",
    headers=patient, json={"due_at": first["due_at"]},
)
check("a reminder can be ticked off", completed.status_code == 200, completed.text[:150])
after_today = client.get("/api/v1/wellness/reminders/today", headers=patient).json()
check("completion is reflected back",
      any(t["completed"] for t in after_today), str([t["completed"] for t in after_today[:3]]))

print("\n=== chat, feed & reviews ===")
threads = client.get("/api/v1/chat/threads", headers=patient).json()
check("patient sees their doctor thread", len(threads) == 1, str(len(threads)))
msgs = client.get(f"/api/v1/chat/threads/{threads[0]['id']}/messages", headers=patient).json()
check("messages load oldest-first", len(msgs) == 3 and msgs[0]["sent_at"] <= msgs[-1]["sent_at"])
sent = client.post(
    f"/api/v1/chat/threads/{threads[0]['id']}/messages", headers=patient, json={"body": "Thanks doctor!"}
)
check("patient can send a message", sent.status_code == 201, sent.text[:150])
doc_threads = client.get("/api/v1/chat/threads", headers=doctor).json()
check("doctor sees patient + peer consult threads", len(doc_threads) == 2, str(len(doc_threads)))

posts = client.get("/api/v1/posts", headers=patient).json()
check("patient feed hides doctor-only posts", all(p["audience"] == "everyone" for p in posts), str(len(posts)))
doc_posts = client.get("/api/v1/posts", headers=doctor).json()
check("doctor feed includes research posts", len(doc_posts) > len(posts), f"{len(doc_posts)} vs {len(posts)}")

reviews = client.get("/api/v1/reviews?target_kind=doctor&target_id=1", headers=patient).json()
check("reviews are listed for a doctor", len(reviews) == 1, str(len(reviews)))
ratings = client.get("/api/v1/doctors/1/ratings", headers=patient).json()
check("rating breakdown returns star histogram", sum(ratings["stars"].values()) == ratings["count"], str(ratings))

print("\n=== doctor & hospital dashboards ===")
my_patients = client.get("/api/v1/doctors/me/patients", headers=doctor).json()
check("doctor sees their patient list", len(my_patients) >= 1, str(len(my_patients)))
schedule = client.get("/api/v1/doctors/me/schedule", headers=doctor).json()
check("doctor schedule loads", isinstance(schedule, list))
prior = client.get(f"/api/v1/doctors/patients/{patient_id}/prior-doctors", headers=doctor).json()
check("prior treating doctors are listed for consult", isinstance(prior, list))
stats = client.get("/api/v1/hospitals/me/stats", headers=hospital).json()
check("hospital dashboard reports stats", stats["doctors"] == 2 and stats["patients"] >= 1, str(stats))
hosp_patients = client.get("/api/v1/hospitals/me/patients", headers=hospital).json()
check("hospital sees its patients", len(hosp_patients) >= 1, str(len(hosp_patients)))

print("\n=== emergency ===")
emergency = client.post(
    "/api/v1/emergency", headers=patient,
    json={"complaint": "Severe chest pain and breathlessness"},
)
check("one-tap emergency dispatches", emergency.status_code == 201, emergency.text[:200])
if emergency.status_code == 201:
    em = emergency.json()
    check("nearest emergency-capable hospital is chosen",
          em["hospital_name"] == "Apollo Multi-Speciality Hospital", str(em["hospital_name"]))
    check("ambulance is dispatched with an ETA",
          em["status"] == "ambulance_dispatched" and em["ambulance_eta_minutes"] > 0, str(em))
    check("record is pushed ahead of arrival", em["record_pushed_at"] is not None)
    check("paperwork is deferred", em["paperwork_deferred"] is True)
    active = client.get("/api/v1/emergency/active", headers=patient).json()
    check("active emergency is retrievable", active and active["id"] == em["id"])

print("\n=== timeline auto-append ===")
final_timeline = client.get(f"/api/v1/patients/{patient_id}/timeline", headers=patient).json()
kinds = {e["kind"] for e in final_timeline}
check("new clinical events landed on the timeline automatically",
      {"prescription", "lab_report", "emergency", "consultation"} <= kinds, str(sorted(kinds)))

legacy = [e for e in final_timeline if e["editable_by_patient"]]
generated = [e for e in final_timeline if not e["editable_by_patient"]]
check("patient-added entries are editable", len(legacy) >= 1, str(len(legacy)))
check("provider-generated entries are locked", len(generated) >= 10, str(len(generated)))
if generated:
    locked = client.patch(
        f"/api/v1/patients/{patient_id}/timeline/{generated[0]['id']}",
        headers=patient, json={"title": "hacked"},
    )
    check("patient cannot edit a provider record", locked.status_code == 403, str(locked.status_code))

print("\n" + "=" * 60)
print(f"  {passed} passed, {len(failed)} failed")
if failed:
    print("\nFailures:")
    for item in failed:
        print(f"  - {item}")
    raise SystemExit(1)
print("  All journeys working.")

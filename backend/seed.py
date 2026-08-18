"""Populate a working demo dataset across all six roles.

Run with:  python seed.py           (drops and recreates every table)
           python seed.py --keep    (only fills an empty database)

Every account uses the password below so the demo is easy to drive.
"""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

import app.models  # noqa: F401
from app.core.enums import (
    AppointmentStatus,
    ClaimStatus,
    ConditionCategory,
    ConditionStatus,
    EncounterType,
    LabOrderStatus,
    MedicineOrderStatus,
    PrescriptionStatus,
    ReminderKind,
    ReminderSource,
    Role,
    TimelineKind,
    VitalType,
)
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import (
    Allergy,
    Appointment,
    CareTeamLink,
    ChatMessage,
    ChatParticipant,
    ChatThread,
    Condition,
    Document,
    DoctorProfile,
    Encounter,
    Hospital,
    InsuranceClaim,
    InsurancePlan,
    Insurer,
    Lab,
    LabOrder,
    LabOrderItem,
    LabReport,
    LabReportValue,
    LabTest,
    MedicineOrder,
    MedicineOrderItem,
    MLRecommendation,
    PatientPolicy,
    PatientProfile,
    Pharmacy,
    PharmacyItem,
    Post,
    Prescription,
    PrescriptionItem,
    Reminder,
    Review,
    Surgery,
    TestRequest,
    User,
    VitalReading,
)
from app.services.payments import record_payment
from app.services.ratings import recompute_rating
from app.services.timeline import record_event

PASSWORD = "Password123!"
NOW = datetime.now(UTC)
TODAY = NOW.date()


def dt(days_ago: int, hour: int = 10, minute: int = 0) -> datetime:
    return (NOW - timedelta(days=days_ago)).replace(hour=hour, minute=minute, second=0, microsecond=0)


def make_user(db, email, name, role, phone=None) -> User:
    user = User(
        email=email,
        phone=phone,
        full_name=name,
        role=role,
        hashed_password=hash_password(PASSWORD),
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def seed(db) -> None:
    # ---------------------------------------------------------------- hospitals
    apollo = Hospital(
        name="Apollo Multi-Speciality Hospital",
        owner_user_id=make_user(db, "ops@apollo.health", "Apollo Operations", Role.HOSPITAL).id,
        kind="multi_speciality",
        address="21 Greams Lane, Anna Salai",
        city="Chennai",
        phone="+91 44 2829 3333",
        latitude=13.0604,
        longitude=80.2496,
        specializations="Cardiology,Endocrinology,Orthopaedics,Neurology,Oncology,General Medicine",
        services="Emergency,ICU,Surgery,Radiology,Dialysis,Maternity",
        bed_count=560,
        icu_bed_count=72,
        doctor_count=180,
        employee_count=2400,
        has_emergency=True,
        has_ambulance=True,
        avg_consultation_fee=800,
        accreditation="NABH",
        surgery_success_rate=96.4,
        complex_cases_handled=3200,
        rating_avg=4.6,
        rating_count=1840,
        is_verified=True,
        about="Tertiary care hospital with a dedicated cardiac and endocrine centre.",
    )
    citycare = Hospital(
        name="CityCare Clinic & Day Hospital",
        owner_user_id=make_user(db, "ops@citycare.health", "CityCare Front Desk", Role.HOSPITAL).id,
        kind="clinic",
        address="4 Kilpauk Garden Road",
        city="Chennai",
        phone="+91 44 2641 8080",
        latitude=13.0798,
        longitude=80.2402,
        specializations="General Medicine,Dermatology,Paediatrics",
        services="OPD,Day Care,Vaccination,Minor Surgery",
        bed_count=40,
        icu_bed_count=4,
        doctor_count=18,
        employee_count=120,
        has_emergency=True,
        has_ambulance=False,
        avg_consultation_fee=400,
        accreditation=None,
        surgery_success_rate=91.0,
        complex_cases_handled=120,
        rating_avg=4.1,
        rating_count=260,
        is_verified=True,
        about="Neighbourhood clinic for everyday care and follow-ups.",
    )
    db.add_all([apollo, citycare])
    db.flush()

    # ------------------------------------------------------------------ doctors
    ananya_user = make_user(db, "ananya.sharma@healthnexus.app", "Dr. Ananya Sharma", Role.DOCTOR, "+91 98400 11111")
    ananya = DoctorProfile(
        user_id=ananya_user.id,
        registration_no="TN-MED-24519",
        specialization="General Medicine",
        qualifications="MBBS, MD (Internal Medicine)",
        years_experience=12,
        hospital_id=apollo.id,
        consultation_fee=800,
        languages="English, Tamil, Hindi",
        city="Chennai",
        latitude=13.0604,
        longitude=80.2496,
        bio="Internal medicine physician with a focus on diabetes and metabolic health.",
        accepts_teleconsult=True,
        rating_avg=4.8,
        rating_count=312,
        is_verified=True,
        procedures_performed=0,
        complex_case_success_rate=None,
        treats_severity="mild,moderate",
    )
    rakesh_user = make_user(db, "rakesh.iyer@healthnexus.app", "Dr. Rakesh Iyer", Role.DOCTOR, "+91 98400 22222")
    rakesh = DoctorProfile(
        user_id=rakesh_user.id,
        registration_no="TN-MED-18822",
        specialization="Cardiology",
        qualifications="MBBS, MD, DM (Cardiology)",
        years_experience=19,
        hospital_id=apollo.id,
        consultation_fee=1400,
        languages="English, Tamil",
        city="Chennai",
        latitude=13.0604,
        longitude=80.2496,
        bio="Interventional cardiologist. Angioplasty and structural heart disease.",
        accepts_teleconsult=False,
        rating_avg=4.9,
        rating_count=486,
        is_verified=True,
        procedures_performed=740,
        complex_case_success_rate=97.2,
        treats_severity="moderate,severe",
    )
    meera_user = make_user(db, "meera.nair@healthnexus.app", "Dr. Meera Nair", Role.DOCTOR, "+91 98400 33333")
    meera = DoctorProfile(
        user_id=meera_user.id,
        registration_no="TN-MED-30144",
        specialization="Endocrinology",
        qualifications="MBBS, MD, DM (Endocrinology)",
        years_experience=9,
        hospital_id=citycare.id,
        consultation_fee=900,
        languages="English, Malayalam, Tamil",
        city="Chennai",
        latitude=13.0798,
        longitude=80.2402,
        bio="Diabetes, thyroid and hormonal disorders.",
        accepts_teleconsult=True,
        rating_avg=4.5,
        rating_count=128,
        is_verified=True,
        procedures_performed=40,
        complex_case_success_rate=93.5,
        treats_severity="mild,moderate,severe",
    )
    db.add_all([ananya, rakesh, meera])
    db.flush()

    # ---------------------------------------------------------------------- labs
    lifeline = Lab(
        name="Lifeline Diagnostics",
        owner_user_id=make_user(db, "ops@lifelinelabs.in", "Lifeline Front Desk", Role.LAB).id,
        address="88 Poonamallee High Road",
        city="Chennai",
        phone="+91 44 2532 6060",
        latitude=13.0731,
        longitude=80.2401,
        accreditation="NABL",
        home_collection=True,
        home_collection_fee=150,
        opens_at="06:30",
        closes_at="21:00",
        rating_avg=4.5,
        rating_count=920,
        is_verified=True,
        about="Full-service pathology lab with same-day reporting on routine panels.",
    )
    metropolis = Lab(
        name="Metropolis Labs",
        owner_user_id=make_user(db, "ops@metropolis.in", "Metropolis Desk", Role.LAB).id,
        address="12 Nungambakkam High Road",
        city="Chennai",
        phone="+91 44 4200 7070",
        latitude=13.0569,
        longitude=80.2425,
        accreditation="NABL, CAP",
        home_collection=True,
        home_collection_fee=0,
        opens_at="07:00",
        closes_at="20:00",
        rating_avg=4.7,
        rating_count=1450,
        is_verified=True,
        about="Reference laboratory with free home sample collection.",
    )
    db.add_all([lifeline, metropolis])
    db.flush()

    # Same tests, different prices — this is what the lab recommender ranks on.
    catalogue = [
        ("HbA1c", "HBA1C", "Diabetes", 650, 480, 24, True),
        ("Fasting Blood Glucose", "FBS", "Diabetes", 180, 120, 6, True),
        ("Lipid Profile", "LIPID", "Cardiac", 900, 700, 24, True),
        ("Complete Blood Count", "CBC", "Haematology", 400, 300, 6, False),
        ("Thyroid Profile (T3 T4 TSH)", "THYROID", "Endocrine", 750, 600, 24, False),
        ("Liver Function Test", "LFT", "Biochemistry", 850, 650, 24, True),
        ("Kidney Function Test", "KFT", "Biochemistry", 800, 620, 24, True),
        ("Vitamin D (25-OH)", "VITD", "Vitamins", 1800, 1400, 48, False),
        ("ECG", "ECG", "Cardiac", 500, 350, 1, False),
        ("2D Echocardiogram", "ECHO", "Cardiac", 2500, 2000, 4, False),
    ]
    for name, code, category, life_price, metro_price, tat, fasting in catalogue:
        db.add(
            LabTest(
                lab_id=lifeline.id, name=name, code=code, category=category, price=life_price,
                discount_percent=10, turnaround_hours=tat, fasting_required=fasting,
            )
        )
        db.add(
            LabTest(
                lab_id=metropolis.id, name=name, code=code, category=category, price=metro_price,
                discount_percent=5, turnaround_hours=tat, fasting_required=fasting,
            )
        )
    db.flush()

    # ---------------------------------------------------------------- pharmacies
    wellness = Pharmacy(
        name="Wellness Forever Pharmacy",
        owner_user_id=make_user(db, "ops@wellnessforever.in", "Wellness Counter", Role.PHARMACY).id,
        address="30 Sterling Road, Nungambakkam",
        city="Chennai",
        phone="+91 44 2822 9090",
        latitude=13.0604,
        longitude=80.2380,
        licence_no="TN-PH-88201",
        delivers=True,
        delivery_fee=40,
        avg_delivery_minutes=45,
        is_24x7=True,
        rating_avg=4.4,
        rating_count=610,
        is_verified=True,
    )
    medplus = Pharmacy(
        name="MedPlus Kilpauk",
        owner_user_id=make_user(db, "ops@medplus.in", "MedPlus Counter", Role.PHARMACY).id,
        address="7 Ormes Road, Kilpauk",
        city="Chennai",
        phone="+91 44 2532 1122",
        latitude=13.0810,
        longitude=80.2390,
        licence_no="TN-PH-77410",
        delivers=True,
        delivery_fee=0,
        avg_delivery_minutes=90,
        is_24x7=False,
        rating_avg=4.2,
        rating_count=340,
        is_verified=True,
    )
    db.add_all([wellness, medplus])
    db.flush()

    stock = [
        ("Metformin", "850 mg", "tablet", "USV", 42, 38, 34, 400, 260),
        ("Vitamin D3", "60000 IU", "capsule", "Abbott", 95, 88, 82, 150, 120),
        ("Atorvastatin", "10 mg", "tablet", "Cipla", 120, 105, 98, 300, 180),
        ("Telmisartan", "40 mg", "tablet", "Glenmark", 145, 130, 122, 220, 0),
        ("Paracetamol", "650 mg", "tablet", "GSK", 30, 27, 25, 900, 700),
        ("Pantoprazole", "40 mg", "tablet", "Sun Pharma", 88, 80, 74, 260, 190),
    ]
    for name, strength, form, maker, mrp, w_price, m_price, w_qty, m_qty in stock:
        db.add(
            PharmacyItem(
                pharmacy_id=wellness.id, medicine_name=name, strength=strength, form=form,
                manufacturer=maker, mrp=mrp, selling_price=w_price, stock_qty=w_qty,
            )
        )
        db.add(
            PharmacyItem(
                pharmacy_id=medplus.id, medicine_name=name, strength=strength, form=form,
                manufacturer=maker, mrp=mrp, selling_price=m_price, stock_qty=m_qty,
            )
        )
    db.flush()

    # ------------------------------------------------------------------ insurers
    starhealth = Insurer(
        name="Star Health Insurance",
        owner_user_id=make_user(db, "claims@starhealth.in", "Star Claims Desk", Role.INSURER).id,
        irdai_reg_no="IRDAI/HLT/2006/129",
        support_phone="1800 425 2255",
        claim_settlement_ratio=96.4,
        avg_settlement_days=9,
        rating_avg=4.3,
        rating_count=2100,
        about="Standalone health insurer with a large cashless hospital network.",
    )
    hdfcergo = Insurer(
        name="HDFC ERGO Health",
        owner_user_id=make_user(db, "claims@hdfcergo.in", "HDFC ERGO Desk", Role.INSURER).id,
        irdai_reg_no="IRDAI/HLT/2002/146",
        support_phone="1800 266 0700",
        claim_settlement_ratio=98.1,
        avg_settlement_days=7,
        rating_avg=4.5,
        rating_count=1780,
        about="Comprehensive health cover with day-one chronic care options.",
    )
    db.add_all([starhealth, hdfcergo])
    db.flush()

    plans = [
        (starhealth, "Family Health Optima", 500000, 14500, 5000, 36, False, True, False, 14000,
         "Cashless at 14,000 hospitals,Free annual health check,No room rent cap"),
        (starhealth, "Senior Citizens Red Carpet", 1000000, 32000, 8000, 12, True, True, True, 14000,
         "Pre-existing cover after 12 months,OPD included,Domiciliary care"),
        (hdfcergo, "Optima Secure", 1000000, 21500, None, 36, False, True, False, 12500,
         "2x cover from day one,4x by year 5,No sub-limits"),
        (hdfcergo, "Optima Restore Chronic", 750000, 27800, 7500, 0, True, True, True, 12500,
         "Day-one cover for diabetes & hypertension,OPD consultations,Unlimited restore"),
    ]
    for insurer, name, cover, premium, room, wait, pre_ex, daycare, opd, network, highlights in plans:
        db.add(
            InsurancePlan(
                insurer_id=insurer.id, name=name, cover_amount=cover, annual_premium=premium,
                room_rent_limit=room, waiting_period_months=wait, covers_pre_existing=pre_ex,
                covers_daycare=daycare, covers_opd=opd, network_hospital_count=network,
                highlights=highlights,
            )
        )
    db.flush()

    # ------------------------------------------------------------------- patient
    rahul_user = make_user(db, "rahul.verma@example.com", "Rahul Verma", Role.PATIENT, "+91 98765 43210")
    rahul = PatientProfile(
        user_id=rahul_user.id,
        medical_id="HNX-482913",
        date_of_birth=date(1991, 3, 14),
        gender="male",
        blood_group="O+",
        height_cm=176,
        weight_kg=73.5,
        address="12/4 Barnaby Road, Kilpauk",
        city="Chennai",
        latitude=13.0820,
        longitude=80.2410,
        emergency_contact_name="Priya Verma",
        emergency_contact_phone="+91 98765 11223",
        is_premium=True,
        is_verified=True,
    )
    db.add(rahul)
    db.flush()

    db.add_all([
        Allergy(patient_id=rahul.id, substance="Penicillin", reaction="Skin rash, hives",
                severity="moderate", noted_on=date(2019, 7, 2)),
        Allergy(patient_id=rahul.id, substance="Dust mites", reaction="Sneezing, watery eyes",
                severity="mild", noted_on=date(2016, 11, 20)),
    ])

    # A second patient, so doctor and hospital dashboards are not single-row.
    aisha_user = make_user(db, "aisha.khan@example.com", "Aisha Khan", Role.PATIENT, "+91 90000 12345")
    aisha = PatientProfile(
        user_id=aisha_user.id, medical_id="HNX-771204", date_of_birth=date(1985, 9, 8),
        gender="female", blood_group="B+", height_cm=162, weight_kg=68,
        address="9 Harrington Road, Chetpet", city="Chennai",
        latitude=13.0730, longitude=80.2420, is_verified=True,
    )
    db.add(aisha)
    db.flush()

    # ---------------------------------------------------------------- conditions
    diabetes = Condition(
        patient_id=rahul.id, name="Type 2 Diabetes Mellitus", icd10_code="E11",
        category=ConditionCategory.CHRONIC, status=ConditionStatus.MANAGED, severity="moderate",
        onset_date=date(2023, 6, 18), diagnosed_by_doctor_id=ananya.id,
        notes="Diet-controlled initially; metformin added after HbA1c rose above 7.0%.",
    )
    cholesterol = Condition(
        patient_id=rahul.id, name="Borderline High Cholesterol", icd10_code="E78.0",
        category=ConditionCategory.CHRONIC, status=ConditionStatus.ACTIVE, severity="mild",
        onset_date=date(2025, 2, 9), diagnosed_by_doctor_id=ananya.id,
        notes="LDL 142 mg/dL on first reading. Statin started.",
    )
    dengue = Condition(
        patient_id=rahul.id, name="Dengue Fever", icd10_code="A90",
        category=ConditionCategory.INFECTIOUS, status=ConditionStatus.RESOLVED, severity="moderate",
        onset_date=date(2024, 8, 20), resolved_date=date(2024, 9, 2),
        notes="Hospitalised 3 days for platelet monitoring. Full recovery.",
    )
    db.add_all([diabetes, cholesterol, dengue])
    db.flush()

    # ---------------------------------------------------------------- encounters
    admission = Encounter(
        patient_id=rahul.id, doctor_id=ananya.id, hospital_id=apollo.id, condition_id=dengue.id,
        kind=EncounterType.ADMISSION, started_at=dt(729, 9), ended_at=dt(726, 11),
        chief_complaint="High fever, body ache, low platelet count",
        diagnosis="Dengue fever with thrombocytopenia",
        clinical_notes="Admitted to general ward. IV fluids, platelet monitoring. Discharged stable.",
    )
    diagnosis_visit = Encounter(
        patient_id=rahul.id, doctor_id=ananya.id, hospital_id=apollo.id, condition_id=diabetes.id,
        kind=EncounterType.CONSULTATION, started_at=dt(180, 10, 15), ended_at=dt(180, 10, 40),
        chief_complaint="Fatigue, increased thirst", diagnosis="Type 2 Diabetes — HbA1c 7.4%",
        clinical_notes="Started metformin 500 mg BD. Dietary counselling given.",
        follow_up_on=(TODAY - timedelta(days=90)),
    )
    recent_visit = Encounter(
        patient_id=rahul.id, doctor_id=ananya.id, hospital_id=apollo.id, condition_id=diabetes.id,
        kind=EncounterType.FOLLOW_UP, started_at=dt(6, 10, 26), ended_at=dt(6, 10, 50),
        chief_complaint="Routine diabetes review", diagnosis="Type 2 Diabetes — well controlled",
        clinical_notes="HbA1c improved to 5.8%. BP 128/82. Metformin increased to 850 mg BD.",
        follow_up_on=(TODAY + timedelta(days=21)),
    )
    aisha_visit = Encounter(
        patient_id=aisha.id, doctor_id=meera.id, hospital_id=citycare.id,
        kind=EncounterType.CONSULTATION, started_at=dt(14, 11), ended_at=dt(14, 11, 25),
        chief_complaint="Weight gain, fatigue", diagnosis="Subclinical hypothyroidism",
    )
    db.add_all([admission, diagnosis_visit, recent_visit, aisha_visit])
    db.flush()

    db.add(Surgery(
        patient_id=rahul.id, hospital_id=apollo.id, surgeon_doctor_id=rakesh.id,
        name="Appendectomy (laparoscopic)", performed_on=date(2018, 4, 12),
        anaesthesia="General", outcome="Uncomplicated recovery, discharged in 2 days",
        is_legacy=True,
    ))

    db.add_all([
        CareTeamLink(patient_id=rahul.id, doctor_id=ananya.id, is_primary=True),
        CareTeamLink(patient_id=rahul.id, doctor_id=rakesh.id),
        CareTeamLink(patient_id=aisha.id, doctor_id=meera.id, is_primary=True),
    ])
    db.flush()

    # ------------------------------------------------------------- prescriptions
    rx_v1 = Prescription(
        patient_id=rahul.id, doctor_id=ananya.id, encounter_id=diagnosis_visit.id,
        condition_id=diabetes.id, version=1, status=PrescriptionStatus.SUPERSEDED,
        issued_at=dt(180, 10, 45), diagnosis_summary="Type 2 Diabetes, newly diagnosed",
        diet_advice="Low glycaemic index diet. Avoid refined sugar and white rice.",
        lifestyle_advice="30 minutes brisk walking, 5 days a week.",
    )
    db.add(rx_v1)
    db.flush()
    db.add_all([
        PrescriptionItem(prescription_id=rx_v1.id, medicine_name="Metformin", strength="500 mg",
                         form="tablet", purpose="Type 2 diabetes support", dosage="1 tablet",
                         frequency="twice daily", timing="after food", duration_days=90, quantity=180),
        PrescriptionItem(prescription_id=rx_v1.id, medicine_name="Vitamin D3", strength="60000 IU",
                         form="capsule", purpose="Vitamin D deficiency", dosage="1 capsule",
                         frequency="weekly", duration_days=56, quantity=8),
    ])

    rx_v2 = Prescription(
        patient_id=rahul.id, doctor_id=ananya.id, encounter_id=recent_visit.id,
        condition_id=diabetes.id, supersedes_id=rx_v1.id, version=2,
        status=PrescriptionStatus.ACTIVE, issued_at=dt(6, 10, 26),
        valid_until=TODAY + timedelta(days=24),
        diagnosis_summary="Type 2 Diabetes — controlled; borderline cholesterol",
        diet_advice=(
            "Continue low GI diet. Add 25–30 g fibre daily. Two portions of leafy greens. "
            "Limit saturated fat to under 15 g/day."
        ),
        lifestyle_advice="45 minutes moderate cardio, 5 days a week. Sleep 7–8 hours.",
        change_note="Metformin increased to 850 mg; atorvastatin added for raised LDL.",
    )
    db.add(rx_v2)
    db.flush()
    items_v2 = [
        PrescriptionItem(prescription_id=rx_v2.id, medicine_name="Metformin", strength="850 mg",
                         form="tablet", purpose="Type 2 diabetes support", dosage="1 tablet",
                         frequency="twice daily", timing="after food", duration_days=30, quantity=60),
        PrescriptionItem(prescription_id=rx_v2.id, medicine_name="Vitamin D3", strength="60000 IU",
                         form="capsule", purpose="Supplement", dosage="1 capsule",
                         frequency="weekly", duration_days=30, quantity=4),
        PrescriptionItem(prescription_id=rx_v2.id, medicine_name="Atorvastatin", strength="10 mg",
                         form="tablet", purpose="Cholesterol management", dosage="1 tablet",
                         frequency="nightly", timing="after dinner", duration_days=30, quantity=30),
    ]
    db.add_all(items_v2)
    db.flush()

    hba1c_request = TestRequest(
        prescription_id=rx_v2.id, patient_id=rahul.id, doctor_id=ananya.id,
        test_name="HbA1c", reason="3-month glycaemic control review", urgency="routine",
    )
    lipid_request = TestRequest(
        prescription_id=rx_v2.id, patient_id=rahul.id, doctor_id=ananya.id,
        test_name="Lipid Profile", reason="Monitor response to statin", urgency="routine",
    )
    db.add_all([hba1c_request, lipid_request])
    db.flush()

    # Medicine reminders generated from the live prescription.
    for item in items_v2:
        times = {"twice daily": "08:00,20:00", "nightly": "21:00", "weekly": "09:00"}
        db.add(Reminder(
            patient_id=rahul.id, kind=ReminderKind.MEDICINE,
            title=f"Take {item.medicine_name} {item.strength}",
            description=f"{item.dosage} · {item.frequency}" + (f" · {item.timing}" if item.timing else ""),
            times_of_day=times.get(item.frequency, "09:00"),
            prescription_item_id=item.id, source=ReminderSource.DOCTOR,
        ))
    db.add_all([
        Reminder(patient_id=rahul.id, kind=ReminderKind.WATER, title="Drink a glass of water",
                 description="Target 2.5 litres across the day",
                 times_of_day="08:00,11:00,14:00,17:00,20:00", target_value=2500, unit="ml",
                 source=ReminderSource.ML),
        Reminder(patient_id=rahul.id, kind=ReminderKind.EXERCISE, title="45 min brisk walk",
                 description="Moderate cardio as advised by Dr. Sharma", times_of_day="18:30",
                 days_of_week="mon,tue,wed,thu,fri", source=ReminderSource.DOCTOR),
        Reminder(patient_id=rahul.id, kind=ReminderKind.SLEEP, title="Wind down for bed",
                 description="Aim for lights out by 22:30 for 7–8 hours",
                 times_of_day="22:00", source=ReminderSource.ML),
        Reminder(patient_id=rahul.id, kind=ReminderKind.DIET, title="Log your meals",
                 description="Keep fibre above 25 g and saturated fat under 15 g",
                 times_of_day="13:00,21:00", source=ReminderSource.ML),
    ])

    # ---------------------------------------------------------------- lab orders
    order = LabOrder(
        patient_id=rahul.id, lab_id=metropolis.id, doctor_id=ananya.id, prescription_id=rx_v2.id,
        status=LabOrderStatus.READY, scheduled_at=dt(4, 7, 30), home_collection=True,
        collection_address=rahul.address, subtotal=1140, discount=0, total_amount=1140,
    )
    db.add(order)
    db.flush()
    db.add_all([
        LabOrderItem(lab_order_id=order.id, test_request_id=hba1c_request.id, test_name="HbA1c", price=456),
        LabOrderItem(lab_order_id=order.id, test_request_id=lipid_request.id, test_name="Lipid Profile", price=665),
    ])
    hba1c_request.fulfilled = True
    lipid_request.fulfilled = True
    db.flush()

    report = LabReport(
        patient_id=rahul.id, lab_id=metropolis.id, lab_order_id=order.id,
        title="Diabetes & Lipid Panel", issued_at=dt(3, 18),
        summary="HbA1c improved to 5.8% from 7.4%. LDL still marginally above target.",
        shared_with_doctor_id=ananya.id, doctor_reviewed_at=dt(3, 20),
        doctor_remarks="Excellent glycaemic control. Continue statin; recheck lipids in 3 months.",
    )
    db.add(report)
    db.flush()
    values = [
        ("HbA1c", 5.8, "%", None, 5.7, "high"),
        ("Fasting Glucose", 102, "mg/dL", 70, 100, "high"),
        ("Total Cholesterol", 186, "mg/dL", 125, 200, "normal"),
        ("LDL Cholesterol", 118, "mg/dL", None, 100, "high"),
        ("HDL Cholesterol", 48, "mg/dL", 40, None, "normal"),
        ("Triglycerides", 142, "mg/dL", None, 150, "normal"),
    ]
    for analyte, value, unit, low, high, flag in values:
        db.add(LabReportValue(report_id=report.id, analyte=analyte, value=value, unit=unit,
                              ref_low=low, ref_high=high, flag=flag))

    old_report = LabReport(
        patient_id=rahul.id, lab_id=lifeline.id, title="Baseline Diabetes Panel",
        issued_at=dt(181, 17), summary="HbA1c 7.4% — consistent with new type 2 diabetes.",
        is_legacy=True,
    )
    db.add(old_report)
    db.flush()
    db.add_all([
        LabReportValue(report_id=old_report.id, analyte="HbA1c", value=7.4, unit="%", ref_high=5.7, flag="high"),
        LabReportValue(report_id=old_report.id, analyte="Fasting Glucose", value=148, unit="mg/dL",
                       ref_low=70, ref_high=100, flag="high"),
    ])

    # ----------------------------------------------------------- medicine orders
    med_order = MedicineOrder(
        patient_id=rahul.id, pharmacy_id=wellness.id, prescription_id=rx_v2.id,
        status=MedicineOrderStatus.FULFILLED, delivery=True, delivery_address=rahul.address,
        subtotal=2712, discount=0, delivery_fee=40, total_amount=2752, ready_at=dt(5, 15),
    )
    db.add(med_order)
    db.flush()
    db.add_all([
        MedicineOrderItem(medicine_order_id=med_order.id, medicine_name="Metformin", strength="850 mg",
                          quantity=60, unit_price=38, line_total=2280),
        MedicineOrderItem(medicine_order_id=med_order.id, medicine_name="Vitamin D3", strength="60000 IU",
                          quantity=4, unit_price=88, line_total=352),
        MedicineOrderItem(medicine_order_id=med_order.id, medicine_name="Atorvastatin", strength="10 mg",
                          quantity=30, unit_price=105, line_total=3150),
    ])

    # ------------------------------------------------------------- appointments
    db.add_all([
        Appointment(patient_id=rahul.id, doctor_id=ananya.id, hospital_id=apollo.id,
                    encounter_id=recent_visit.id, scheduled_at=dt(6, 10, 15),
                    mode="in_person", status=AppointmentStatus.COMPLETED,
                    reason="Routine diabetes review", fee=800),
        Appointment(patient_id=rahul.id, doctor_id=ananya.id, hospital_id=apollo.id,
                    scheduled_at=dt(-21, 11), mode="in_person", status=AppointmentStatus.CONFIRMED,
                    reason="3-week follow-up on new dosage", fee=800, is_follow_up=True),
        Appointment(patient_id=aisha.id, doctor_id=meera.id, hospital_id=citycare.id,
                    encounter_id=aisha_visit.id, scheduled_at=dt(14, 11),
                    mode="in_person", status=AppointmentStatus.COMPLETED,
                    reason="Thyroid review", fee=900),
    ])

    # ------------------------------------------------------------------ vitals
    vital_series = [
        (VitalType.WEIGHT, [(180, 79.2), (150, 78.1), (120, 76.8), (90, 75.9), (60, 74.8), (30, 74.0), (3, 73.5)], "kg"),
        (VitalType.BP_SYSTOLIC, [(180, 142), (150, 138), (120, 136), (90, 133), (60, 130), (30, 129), (3, 128)], "mmHg"),
        (VitalType.BP_DIASTOLIC, [(180, 94), (150, 91), (120, 88), (90, 86), (60, 84), (30, 83), (3, 82)], "mmHg"),
        (VitalType.HBA1C, [(181, 7.4), (90, 6.5), (3, 5.8)], "%"),
        (VitalType.GLUCOSE_FASTING, [(181, 148), (120, 126), (60, 112), (3, 102)], "mg/dL"),
    ]
    for kind, points, unit in vital_series:
        for days_ago, value in points:
            db.add(VitalReading(patient_id=rahul.id, kind=kind, value=value, unit=unit,
                                recorded_at=dt(days_ago, 8), source="clinic"))
    for days_ago in range(14, 0, -1):
        db.add(VitalReading(patient_id=rahul.id, kind=VitalType.STEPS,
                            value=6200 + (days_ago * 137) % 3400, unit="steps",
                            recorded_at=dt(days_ago, 22), source="device"))
        db.add(VitalReading(patient_id=rahul.id, kind=VitalType.SLEEP_HOURS,
                            value=6.4 + ((days_ago * 7) % 16) / 10, unit="hours",
                            recorded_at=dt(days_ago, 7), source="device"))

    # ---------------------------------------------------------------- insurance
    optima = db.scalar(select(InsurancePlan).where(InsurancePlan.name == "Optima Secure"))
    policy = PatientPolicy(
        patient_id=rahul.id, insurer_id=hdfcergo.id, plan_id=optima.id,
        policy_number="HE-2024-8891204", holder_name="Rahul Verma",
        cover_amount=1000000, used_amount=62000, annual_premium=21500,
        starts_on=date(TODAY.year, 4, 1), ends_on=date(TODAY.year + 1, 3, 31), is_active=True,
    )
    db.add(policy)
    db.flush()

    db.add(InsuranceClaim(
        patient_id=rahul.id, patient_policy_id=policy.id, claim_number="CLM-449021",
        status=ClaimStatus.SETTLED, treatment_type="cashless", hospital_id=apollo.id,
        encounter_id=admission.id, amount_claimed=68000, amount_approved=62000,
        incident_date=date(2024, 8, 20), submitted_at=dt(720), decided_at=dt(714),
        settled_at=dt(711), reviewer_note="Approved less non-medical consumables.",
        description="Dengue hospitalisation — 3 day admission at Apollo.",
    ))
    db.add(InsuranceClaim(
        patient_id=rahul.id, patient_policy_id=policy.id, claim_number="CLM-518330",
        status=ClaimStatus.UNDER_REVIEW, treatment_type="reimbursement", hospital_id=apollo.id,
        amount_claimed=4200, amount_approved=0, incident_date=TODAY - timedelta(days=6),
        submitted_at=dt(2), description="OPD consultation and diagnostic panel.",
    ))

    # ------------------------------------------------------------------ payments
    record_payment(db, patient_id=rahul.id, purpose="appointment", amount=800,
                   payee_kind="doctor", payee_id=ananya.id, ref_table="appointments", ref_id=1,
                   description="Consultation — Dr. Ananya Sharma")
    record_payment(db, patient_id=rahul.id, purpose="lab_order", amount=1140,
                   payee_kind="lab", payee_id=metropolis.id, ref_table="lab_orders", ref_id=order.id,
                   description="Lab tests — Metropolis Labs")
    record_payment(db, patient_id=rahul.id, purpose="medicine_order", amount=2752,
                   payee_kind="pharmacy", payee_id=wellness.id, ref_table="medicine_orders",
                   ref_id=med_order.id, description="Medicines — Wellness Forever Pharmacy")
    record_payment(db, patient_id=rahul.id, purpose="premium", amount=299,
                   description="HealthNexus plus — monthly")

    # -------------------------------------------------------------------- posts
    db.add_all([
        Post(author_user_id=ananya_user.id,
             title="Reading your HbA1c: what the number actually means",
             excerpt="A practical guide to interpreting your three-month blood sugar average.",
             body=("HbA1c reflects your average blood glucose over roughly three months. "
                   "Below 5.7% is normal, 5.7–6.4% is prediabetes, and 6.5% or above supports a "
                   "diagnosis of diabetes. What matters more than a single reading is the trend: "
                   "a fall from 7.4% to 5.8% over six months represents real, meaningful change in "
                   "risk. Focus on consistency in diet, movement and medication rather than chasing "
                   "one perfect number."),
             tags="diabetes,lab-reports,explainer", audience="everyone", read_minutes=4,
             like_count=214, published_at=dt(9, 9)),
        Post(author_user_id=rakesh_user.id,
             title="Statins and muscle aches — separating signal from noise",
             excerpt="Most reported statin myalgia is not caused by the statin. Here is what the trials show.",
             body=("Observational reports of muscle pain on statins run far higher than the rates seen "
                   "in blinded randomised trials. The n-of-1 rechallenge literature suggests most "
                   "patients who stop a statin for aches tolerate it on rechallenge. That does not mean "
                   "symptoms are imagined — it means the attribution is often wrong. Before stopping, "
                   "check CK, review interacting drugs, and consider a washout and rechallenge."),
             tags="cardiology,statins,research", audience="doctors", read_minutes=6,
             like_count=88, published_at=dt(4, 16)),
        Post(author_user_id=meera_user.id,
             title="Thyroid tests: when subclinical actually needs treating",
             excerpt="TSH is mildly raised but T4 is normal. Treat, or watch?",
             body=("Subclinical hypothyroidism means a raised TSH with a normal free T4. Treatment is "
                   "usually justified when TSH exceeds 10 mIU/L, when antibodies are positive with "
                   "symptoms, or in pregnancy. For a mildly raised TSH in an asymptomatic adult, "
                   "repeating the test in 8–12 weeks is often the better first move — a third of them "
                   "normalise on their own."),
             tags="endocrinology,thyroid,explainer", audience="everyone", read_minutes=5,
             like_count=132, published_at=dt(2, 11)),
    ])

    # ------------------------------------------------------------------ reviews
    reviews = [
        (rahul_user.id, "doctor", ananya.id, 5, "Genuinely listens",
         "Dr. Sharma explained every change to my prescription and why. My HbA1c is down to 5.8%."),
        (aisha_user.id, "doctor", meera.id, 4, "Thorough and patient",
         "Took time over my thyroid results and did not rush into medication."),
        (rahul_user.id, "hospital", apollo.id, 5, "Well run",
         "Admission during dengue was smooth and the ward staff were attentive."),
        (rahul_user.id, "lab", metropolis.id, 5, "Free home collection is a win",
         "Phlebotomist arrived on time and the report was up in the app the next evening."),
        (rahul_user.id, "pharmacy", wellness.id, 4, "Fast delivery",
         "Order was ready before I reached the counter. Prices are fair."),
        (aisha_user.id, "hospital", citycare.id, 4, "Good for routine visits",
         "Short waits and easy parking. Not for anything complex."),
    ]
    for author_id, kind, target_id, rating, title, comment in reviews:
        db.add(Review(author_user_id=author_id, target_kind=kind, target_id=target_id,
                      rating=rating, title=title, comment=comment, is_verified_visit=True))
    db.flush()
    for _, kind, target_id, *_ in reviews:
        recompute_rating(db, kind, target_id)

    # --------------------------------------------------------------------- chat
    thread = ChatThread(kind="patient_doctor", subject="Diabetes follow-up",
                        last_message_at=dt(1, 9, 12))
    db.add(thread)
    db.flush()
    db.add_all([
        ChatParticipant(thread_id=thread.id, user_id=rahul_user.id),
        ChatParticipant(thread_id=thread.id, user_id=ananya_user.id),
    ])
    db.add_all([
        ChatMessage(thread_id=thread.id, sender_user_id=rahul_user.id,
                    body="Doctor, I've been getting mild nausea after the higher metformin dose. Is that expected?",
                    sent_at=dt(2, 20, 10)),
        ChatMessage(thread_id=thread.id, sender_user_id=ananya_user.id,
                    body=("Yes, that's common in the first two weeks after a dose increase. Take it "
                          "straight after a full meal and it usually settles. If it's still there in a "
                          "week, message me and we'll adjust."),
                    sent_at=dt(2, 21, 5)),
        ChatMessage(thread_id=thread.id, sender_user_id=rahul_user.id,
                    body="Thank you — will do. Also saw the lipid report came through.",
                    sent_at=dt(1, 9, 12)),
    ])

    # A doctor-to-doctor consult about a shared patient.
    consult = ChatThread(kind="doctor_doctor", subject="Rahul Verma — statin choice",
                         about_patient_id=rahul.id, condition_id=cholesterol.id,
                         last_message_at=dt(3, 15, 40))
    db.add(consult)
    db.flush()
    db.add_all([
        ChatParticipant(thread_id=consult.id, user_id=ananya_user.id),
        ChatParticipant(thread_id=consult.id, user_id=rakesh_user.id),
    ])
    db.add_all([
        ChatMessage(thread_id=consult.id, sender_user_id=ananya_user.id,
                    body="Rakesh — LDL 118 on atorvastatin 10. Push to 20 or add ezetimibe given family history?",
                    sent_at=dt(3, 15, 20)),
        ChatMessage(thread_id=consult.id, sender_user_id=rakesh_user.id,
                    body="At his age and risk profile I'd double the atorvastatin first and recheck at 8 weeks.",
                    sent_at=dt(3, 15, 40)),
    ])

    # ------------------------------------------------- ML recommendation samples
    # Shape only — model 2 replaces the payloads with real generated plans.
    db.add_all([
        MLRecommendation(
            patient_id=rahul.id, kind="diet", title="Today's plate: fibre-forward, low GI",
            rationale=("Built from your HbA1c trend (5.8%), Dr. Sharma's low-GI advice and your "
                       "current metformin dose."),
            score=0.92, model_version="seed-placeholder", generated_at=NOW,
            expires_at=NOW + timedelta(days=1),
            payload={
                "targets": {"fibre_g": 30, "saturated_fat_g": 15, "added_sugar_g": 25, "protein_g": 88},
                "meals": {
                    "breakfast": "Vegetable oats upma + 1 boiled egg",
                    "lunch": "2 multigrain rotis + dal + palak sabzi + curd",
                    "snack": "Roasted chana, handful of almonds",
                    "dinner": "Grilled fish + sauteed greens + half cup brown rice",
                },
                "avoid": ["White rice at dinner", "Fruit juice", "Deep-fried snacks"],
            },
        ),
        MLRecommendation(
            patient_id=rahul.id, kind="workout", title="45 min zone-2 walk + 15 min resistance",
            rationale="Your step count averaged 7,400/day this fortnight; sleep is stable at 7h.",
            score=0.88, model_version="seed-placeholder", generated_at=NOW,
            expires_at=NOW + timedelta(days=1),
            payload={
                "sessions": [
                    {"type": "cardio", "name": "Brisk walk", "minutes": 45, "intensity": "zone 2"},
                    {"type": "resistance", "name": "Bodyweight circuit", "minutes": 15,
                     "moves": ["Squats 3x12", "Push-ups 3x10", "Plank 3x40s"]},
                ],
                "weekly_target_minutes": 225,
            },
        ),
        MLRecommendation(
            patient_id=rahul.id, kind="lifestyle", title="Move your last meal 90 minutes earlier",
            rationale="Fasting glucose runs highest on days you log dinner after 21:30.",
            score=0.81, model_version="seed-placeholder", generated_at=NOW,
            expires_at=NOW + timedelta(days=3),
            payload={"change": "Dinner before 20:00", "expected_effect": "Lower morning fasting glucose"},
        ),
    ])

    # ---------------------------------------------------------------- documents
    db.add_all([
        Document(patient_id=rahul.id, uploaded_by_user_id=rahul_user.id, kind="discharge_summary",
                 title="Apollo discharge summary — dengue admission",
                 file_url="/uploads/demo/discharge-2024-09-02.pdf", mime_type="application/pdf",
                 document_date=date(2024, 9, 2), is_legacy=True),
        Document(patient_id=rahul.id, uploaded_by_user_id=rahul_user.id, kind="prescription",
                 title="Old prescription — Dr. S. Rao (2019)",
                 file_url="/uploads/demo/rx-2019.jpg", mime_type="image/jpeg",
                 document_date=date(2019, 7, 2), is_legacy=True),
    ])

    # ----------------------------------------------------------------- timeline
    events = [
        (TimelineKind.SURGERY, datetime(2018, 4, 12, 9, tzinfo=UTC), "Appendectomy (laparoscopic)",
         "Apollo — uncomplicated recovery", None, apollo.id, None, True),
        (TimelineKind.DIAGNOSIS, datetime(2024, 8, 20, 9, tzinfo=UTC), "Diagnosed: Dengue Fever",
         "Admitted 3 days for platelet monitoring", ananya.id, apollo.id, dengue.id, False),
        (TimelineKind.ADMISSION, dt(729, 9), "Hospital admission — General ward",
         "Dengue fever with thrombocytopenia. Discharged 23 Aug.", ananya.id, apollo.id, dengue.id, False),
        (TimelineKind.DIAGNOSIS, datetime(2023, 6, 18, 10, tzinfo=UTC), "Diagnosed: Type 2 Diabetes Mellitus",
         "HbA1c 7.4% at diagnosis", ananya.id, apollo.id, diabetes.id, False),
        (TimelineKind.CONSULTATION, dt(180, 10, 15), "Consultation with Dr. Ananya Sharma",
         "Fatigue, increased thirst — type 2 diabetes diagnosed", ananya.id, apollo.id, diabetes.id, False),
        (TimelineKind.PRESCRIPTION, dt(180, 10, 45), "Prescription from Dr. Ananya Sharma",
         "Metformin 500 mg, Vitamin D3", ananya.id, None, diabetes.id, False),
        (TimelineKind.LAB_REPORT, dt(181, 17), "Baseline Diabetes Panel",
         "HbA1c 7.4% — consistent with new type 2 diabetes", None, None, diabetes.id, False),
        (TimelineKind.CONSULTATION, dt(6, 10, 26), "Consultation with Dr. Ananya Sharma",
         "Routine diabetes review — well controlled", ananya.id, apollo.id, diabetes.id, False),
        (TimelineKind.PRESCRIPTION, dt(6, 10, 26), "Prescription updated (v2)",
         "Metformin increased to 850 mg; atorvastatin added", ananya.id, None, diabetes.id, False),
        (TimelineKind.LAB_REPORT, dt(3, 18), "Diabetes & Lipid Panel",
         "HbA1c improved to 5.8%. LDL marginally above target.", ananya.id, None, diabetes.id, False),
    ]
    for kind, when, title, summary, doctor_id, hospital_id, condition_id, legacy in events:
        record_event(db, patient_id=rahul.id, kind=kind, occurred_at=when, title=title,
                     summary=summary, doctor_id=doctor_id, hospital_id=hospital_id,
                     condition_id=condition_id, is_legacy=legacy, editable_by_patient=legacy)
    record_event(db, patient_id=rahul.id, kind=TimelineKind.LAB_REPORT, occurred_at=dt(3, 18),
                 title="Lab report shared with Dr. Sharma", summary="Reviewed with remarks",
                 lab_id=metropolis.id, doctor_id=ananya.id, ref_table="lab_reports", ref_id=report.id)

    record_event(db, patient_id=aisha.id, kind=TimelineKind.CONSULTATION, occurred_at=dt(14, 11),
                 title="Consultation with Dr. Meera Nair", summary="Subclinical hypothyroidism",
                 doctor_id=meera.id, hospital_id=citycare.id)

    db.commit()


def main() -> None:
    keep = "--keep" in sys.argv
    db = SessionLocal()
    try:
        if not keep:
            print("Dropping and recreating all tables…")
            Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

        if keep and db.scalar(select(User.id)):
            print("Database already has data — nothing to do (--keep).")
            return

        seed(db)
        print("Seed complete.\n")
        print(f"  All accounts use the password: {PASSWORD}\n")
        print("  Patient   rahul.verma@example.com      (premium, full history)")
        print("  Patient   aisha.khan@example.com")
        print("  Doctor    ananya.sharma@healthnexus.app  (Rahul's physician)")
        print("  Doctor    rakesh.iyer@healthnexus.app    (cardiology)")
        print("  Doctor    meera.nair@healthnexus.app     (endocrinology)")
        print("  Hospital  ops@apollo.health")
        print("  Lab       ops@metropolis.in")
        print("  Pharmacy  ops@wellnessforever.in")
        print("  Insurer   claims@hdfcergo.in")
    finally:
        db.close()


if __name__ == "__main__":
    main()

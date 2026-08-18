"""ORM -> schema helpers.

Response schemas carry display names (`doctor_name`, `lab_name`, ...) that live
on related rows. These helpers do that enrichment in one place so routers stay
thin and every endpoint labels entities the same way.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models import (
    Appointment,
    Condition,
    DoctorProfile,
    Encounter,
    Hospital,
    InsuranceClaim,
    InsurancePlan,
    Insurer,
    Lab,
    LabOrder,
    LabReport,
    MedicineOrder,
    PatientPolicy,
    PatientProfile,
    Payment,
    Pharmacy,
    Post,
    Prescription,
    Surgery,
    TimelineEvent,
    User,
)
from app.schemas.clinical import EncounterOut, PrescriptionOut
from app.schemas.finance import InsuranceClaimOut, PatientPolicyOut, PaymentOut
from app.schemas.orders import (
    AppointmentOut,
    LabOrderOut,
    LabReportOut,
    MedicineOrderOut,
)
from app.schemas.patient import ConditionOut, PatientOut, SurgeryOut, TimelineEventOut
from app.schemas.providers import DoctorOut, InsurancePlanOut, LabOut, PharmacyOut
from app.schemas.social import PostOut


def _doctor_name(db: Session, doctor_id: int | None) -> str | None:
    if not doctor_id:
        return None
    doctor = db.get(DoctorProfile, doctor_id)
    if not doctor:
        return None
    user = db.get(User, doctor.user_id)
    return user.full_name if user else None


def _name_of(db: Session, model, entity_id: int | None) -> str | None:
    if not entity_id:
        return None
    row = db.get(model, entity_id)
    return row.name if row else None


def calculate_age(dob: date | None) -> int | None:
    if not dob:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def patient_out(db: Session, patient: PatientProfile) -> PatientOut:
    user = db.get(User, patient.user_id)
    return PatientOut(
        id=patient.id,
        user_id=patient.user_id,
        medical_id=patient.medical_id,
        full_name=user.full_name if user else "",
        email=user.email if user else None,
        phone=user.phone if user else None,
        date_of_birth=patient.date_of_birth,
        age=calculate_age(patient.date_of_birth),
        gender=patient.gender,
        blood_group=patient.blood_group,
        height_cm=patient.height_cm,
        weight_kg=patient.weight_kg,
        bmi=patient.bmi,
        address=patient.address,
        city=patient.city,
        emergency_contact_name=patient.emergency_contact_name,
        emergency_contact_phone=patient.emergency_contact_phone,
        is_premium=patient.is_premium,
        is_verified=patient.is_verified,
        allergies=patient.allergies,
    )


def doctor_out(
    db: Session,
    doctor: DoctorProfile,
    *,
    distance_km: float | None = None,
    match_score: float | None = None,
    match_reason: str | None = None,
) -> DoctorOut:
    user = db.get(User, doctor.user_id)
    return DoctorOut(
        id=doctor.id,
        user_id=doctor.user_id,
        full_name=user.full_name if user else "",
        avatar_url=user.avatar_url if user else None,
        specialization=doctor.specialization,
        qualifications=doctor.qualifications,
        registration_no=doctor.registration_no,
        years_experience=doctor.years_experience,
        consultation_fee=doctor.consultation_fee,
        languages=doctor.languages,
        bio=doctor.bio,
        city=doctor.city,
        hospital_id=doctor.hospital_id,
        hospital_name=_name_of(db, Hospital, doctor.hospital_id),
        accepts_teleconsult=doctor.accepts_teleconsult,
        rating_avg=doctor.rating_avg,
        rating_count=doctor.rating_count,
        is_verified=doctor.is_verified,
        procedures_performed=doctor.procedures_performed,
        complex_case_success_rate=doctor.complex_case_success_rate,
        distance_km=distance_km,
        match_score=match_score,
        match_reason=match_reason,
    )


def prescription_out(db: Session, prescription: Prescription) -> PrescriptionOut:
    doctor = db.get(DoctorProfile, prescription.doctor_id) if prescription.doctor_id else None
    return PrescriptionOut(
        id=prescription.id,
        version=prescription.version,
        status=prescription.status,
        issued_at=prescription.issued_at,
        valid_until=prescription.valid_until,
        patient_id=prescription.patient_id,
        doctor_id=prescription.doctor_id,
        doctor_name=_doctor_name(db, prescription.doctor_id),
        doctor_specialization=doctor.specialization if doctor else None,
        encounter_id=prescription.encounter_id,
        condition_id=prescription.condition_id,
        supersedes_id=prescription.supersedes_id,
        diagnosis_summary=prescription.diagnosis_summary,
        diet_advice=prescription.diet_advice,
        lifestyle_advice=prescription.lifestyle_advice,
        change_note=prescription.change_note,
        notes=prescription.notes,
        is_legacy=prescription.is_legacy,
        items=prescription.items,
        test_requests=prescription.test_requests,
    )


def encounter_out(db: Session, encounter: Encounter) -> EncounterOut:
    return EncounterOut(
        id=encounter.id,
        kind=encounter.kind,
        started_at=encounter.started_at,
        ended_at=encounter.ended_at,
        patient_id=encounter.patient_id,
        doctor_id=encounter.doctor_id,
        doctor_name=_doctor_name(db, encounter.doctor_id),
        hospital_id=encounter.hospital_id,
        hospital_name=_name_of(db, Hospital, encounter.hospital_id),
        condition_id=encounter.condition_id,
        condition_name=_name_of(db, Condition, encounter.condition_id),
        chief_complaint=encounter.chief_complaint,
        diagnosis=encounter.diagnosis,
        clinical_notes=encounter.clinical_notes,
        follow_up_on=encounter.follow_up_on,
        is_legacy=encounter.is_legacy,
    )


def timeline_out(db: Session, event: TimelineEvent) -> TimelineEventOut:
    return TimelineEventOut(
        id=event.id,
        kind=event.kind,
        occurred_at=event.occurred_at,
        title=event.title,
        summary=event.summary,
        doctor_id=event.doctor_id,
        doctor_name=_doctor_name(db, event.doctor_id),
        hospital_id=event.hospital_id,
        hospital_name=_name_of(db, Hospital, event.hospital_id),
        lab_id=event.lab_id,
        lab_name=_name_of(db, Lab, event.lab_id),
        condition_id=event.condition_id,
        ref_table=event.ref_table,
        ref_id=event.ref_id,
        is_legacy=event.is_legacy,
        editable_by_patient=event.editable_by_patient,
    )


def condition_out(db: Session, condition: Condition) -> ConditionOut:
    return ConditionOut(
        id=condition.id,
        name=condition.name,
        icd10_code=condition.icd10_code,
        category=condition.category,
        status=condition.status,
        severity=condition.severity,
        onset_date=condition.onset_date,
        resolved_date=condition.resolved_date,
        diagnosed_by_doctor_id=condition.diagnosed_by_doctor_id,
        doctor_name=_doctor_name(db, condition.diagnosed_by_doctor_id),
        notes=condition.notes,
        is_legacy=condition.is_legacy,
    )


def surgery_out(db: Session, surgery: Surgery) -> SurgeryOut:
    return SurgeryOut(
        id=surgery.id,
        name=surgery.name,
        performed_on=surgery.performed_on,
        hospital_id=surgery.hospital_id,
        hospital_name=_name_of(db, Hospital, surgery.hospital_id),
        surgeon_doctor_id=surgery.surgeon_doctor_id,
        surgeon_name=_doctor_name(db, surgery.surgeon_doctor_id),
        anaesthesia=surgery.anaesthesia,
        outcome=surgery.outcome,
        notes=surgery.notes,
    )


def _patient_name(db: Session, patient_id: int | None) -> str | None:
    if not patient_id:
        return None
    patient = db.get(PatientProfile, patient_id)
    if not patient:
        return None
    user = db.get(User, patient.user_id)
    return user.full_name if user else None


def appointment_out(db: Session, appointment: Appointment) -> AppointmentOut:
    doctor = db.get(DoctorProfile, appointment.doctor_id)
    return AppointmentOut(
        id=appointment.id,
        patient_id=appointment.patient_id,
        patient_name=_patient_name(db, appointment.patient_id),
        doctor_id=appointment.doctor_id,
        doctor_name=_doctor_name(db, appointment.doctor_id),
        doctor_specialization=doctor.specialization if doctor else None,
        hospital_id=appointment.hospital_id,
        hospital_name=_name_of(db, Hospital, appointment.hospital_id),
        scheduled_at=appointment.scheduled_at,
        duration_minutes=appointment.duration_minutes,
        mode=appointment.mode,
        status=appointment.status,
        reason=appointment.reason,
        fee=appointment.fee,
        is_follow_up=appointment.is_follow_up,
    )


def lab_order_out(db: Session, order: LabOrder) -> LabOrderOut:
    return LabOrderOut(
        id=order.id,
        patient_id=order.patient_id,
        patient_name=_patient_name(db, order.patient_id),
        lab_id=order.lab_id,
        lab_name=_name_of(db, Lab, order.lab_id),
        doctor_id=order.doctor_id,
        doctor_name=_doctor_name(db, order.doctor_id),
        prescription_id=order.prescription_id,
        status=order.status,
        scheduled_at=order.scheduled_at,
        home_collection=order.home_collection,
        collection_address=order.collection_address,
        subtotal=order.subtotal,
        discount=order.discount,
        total_amount=order.total_amount,
        notes=order.notes,
        created_at=order.created_at,
        items=order.items,
    )


def lab_report_out(db: Session, report: LabReport) -> LabReportOut:
    return LabReportOut(
        id=report.id,
        patient_id=report.patient_id,
        lab_id=report.lab_id,
        lab_name=_name_of(db, Lab, report.lab_id),
        lab_order_id=report.lab_order_id,
        title=report.title,
        issued_at=report.issued_at,
        summary=report.summary,
        file_url=report.file_url,
        shared_with_doctor_id=report.shared_with_doctor_id,
        doctor_reviewed_at=report.doctor_reviewed_at,
        doctor_remarks=report.doctor_remarks,
        is_legacy=report.is_legacy,
        values=report.values,
    )


def medicine_order_out(db: Session, order: MedicineOrder) -> MedicineOrderOut:
    return MedicineOrderOut(
        id=order.id,
        patient_id=order.patient_id,
        patient_name=_patient_name(db, order.patient_id),
        pharmacy_id=order.pharmacy_id,
        pharmacy_name=_name_of(db, Pharmacy, order.pharmacy_id),
        prescription_id=order.prescription_id,
        status=order.status,
        delivery=order.delivery,
        delivery_address=order.delivery_address,
        subtotal=order.subtotal,
        discount=order.discount,
        delivery_fee=order.delivery_fee,
        total_amount=order.total_amount,
        ready_at=order.ready_at,
        rejection_reason=order.rejection_reason,
        created_at=order.created_at,
        items=order.items,
    )


PAYEE_MODELS = {"doctor": DoctorProfile, "hospital": Hospital, "lab": Lab, "pharmacy": Pharmacy}


def payment_out(db: Session, payment: Payment) -> PaymentOut:
    payee_name = None
    if payment.payee_kind == "doctor":
        payee_name = _doctor_name(db, payment.payee_id)
    elif payment.payee_kind in PAYEE_MODELS:
        payee_name = _name_of(db, PAYEE_MODELS[payment.payee_kind], payment.payee_id)

    return PaymentOut(
        id=payment.id,
        patient_id=payment.patient_id,
        purpose=payment.purpose,
        ref_table=payment.ref_table,
        ref_id=payment.ref_id,
        payee_kind=payment.payee_kind,
        payee_id=payment.payee_id,
        payee_name=payee_name,
        amount=payment.amount,
        commission_rate=payment.commission_rate,
        commission_amount=payment.commission_amount,
        payout_amount=payment.payout_amount,
        status=payment.status,
        method=payment.method,
        gateway_ref=payment.gateway_ref,
        paid_at=payment.paid_at,
        description=payment.description,
        claim_id=payment.claim_id,
        created_at=payment.created_at,
    )


def policy_out(db: Session, policy: PatientPolicy) -> PatientPolicyOut:
    return PatientPolicyOut(
        id=policy.id,
        patient_id=policy.patient_id,
        insurer_id=policy.insurer_id,
        insurer_name=_name_of(db, Insurer, policy.insurer_id),
        plan_id=policy.plan_id,
        plan_name=_name_of(db, InsurancePlan, policy.plan_id),
        policy_number=policy.policy_number,
        holder_name=policy.holder_name,
        cover_amount=policy.cover_amount,
        used_amount=policy.used_amount,
        remaining_amount=policy.remaining_amount,
        used_percent=policy.used_percent,
        annual_premium=policy.annual_premium,
        starts_on=policy.starts_on,
        ends_on=policy.ends_on,
        is_active=policy.is_active,
    )


def claim_out(db: Session, claim: InsuranceClaim) -> InsuranceClaimOut:
    policy = db.get(PatientPolicy, claim.patient_policy_id)
    return InsuranceClaimOut(
        id=claim.id,
        patient_id=claim.patient_id,
        patient_name=_patient_name(db, claim.patient_id),
        patient_policy_id=claim.patient_policy_id,
        policy_number=policy.policy_number if policy else None,
        insurer_name=_name_of(db, Insurer, policy.insurer_id) if policy else None,
        claim_number=claim.claim_number,
        status=claim.status,
        treatment_type=claim.treatment_type,
        hospital_id=claim.hospital_id,
        hospital_name=_name_of(db, Hospital, claim.hospital_id),
        encounter_id=claim.encounter_id,
        amount_claimed=claim.amount_claimed,
        amount_approved=claim.amount_approved,
        incident_date=claim.incident_date,
        submitted_at=claim.submitted_at,
        decided_at=claim.decided_at,
        settled_at=claim.settled_at,
        reviewer_note=claim.reviewer_note,
        rejection_reason=claim.rejection_reason,
        description=claim.description,
        created_at=claim.created_at,
        documents=claim.documents,
    )


def plan_out(
    db: Session,
    plan: InsurancePlan,
    *,
    match_score: float | None = None,
    match_reason: str | None = None,
    insurer_name: str | None = None,
) -> InsurancePlanOut:
    return InsurancePlanOut(
        id=plan.id,
        insurer_id=plan.insurer_id,
        insurer_name=insurer_name or _name_of(db, Insurer, plan.insurer_id),
        name=plan.name,
        cover_amount=plan.cover_amount,
        annual_premium=plan.annual_premium,
        room_rent_limit=plan.room_rent_limit,
        waiting_period_months=plan.waiting_period_months,
        covers_pre_existing=plan.covers_pre_existing,
        covers_daycare=plan.covers_daycare,
        covers_opd=plan.covers_opd,
        network_hospital_count=plan.network_hospital_count,
        highlights=plan.highlights,
        match_score=match_score,
        match_reason=match_reason,
    )


def lab_out(
    db: Session,
    lab: Lab,
    *,
    distance_km: float | None = None,
    match_score: float | None = None,
    match_reason: str | None = None,
    quoted_total: float | None = None,
    include_tests: bool = False,
) -> LabOut:
    return LabOut(
        id=lab.id,
        name=lab.name,
        address=lab.address,
        city=lab.city,
        phone=lab.phone,
        accreditation=lab.accreditation,
        home_collection=lab.home_collection,
        home_collection_fee=lab.home_collection_fee,
        opens_at=lab.opens_at,
        closes_at=lab.closes_at,
        about=lab.about,
        rating_avg=lab.rating_avg,
        rating_count=lab.rating_count,
        is_verified=lab.is_verified,
        distance_km=distance_km,
        match_score=match_score,
        match_reason=match_reason,
        quoted_total=quoted_total,
        tests=lab.tests if include_tests else [],
    )


def pharmacy_out(
    pharmacy: Pharmacy,
    *,
    distance_km: float | None = None,
    match_score: float | None = None,
    match_reason: str | None = None,
    quoted_total: float | None = None,
    unavailable_items: list[str] | None = None,
) -> PharmacyOut:
    return PharmacyOut(
        id=pharmacy.id,
        name=pharmacy.name,
        address=pharmacy.address,
        city=pharmacy.city,
        phone=pharmacy.phone,
        delivers=pharmacy.delivers,
        delivery_fee=pharmacy.delivery_fee,
        avg_delivery_minutes=pharmacy.avg_delivery_minutes,
        is_24x7=pharmacy.is_24x7,
        rating_avg=pharmacy.rating_avg,
        rating_count=pharmacy.rating_count,
        is_verified=pharmacy.is_verified,
        distance_km=distance_km,
        match_score=match_score,
        match_reason=match_reason,
        quoted_total=quoted_total,
        unavailable_items=unavailable_items or [],
    )


def post_out(db: Session, post: Post) -> PostOut:
    author = db.get(User, post.author_user_id)
    doctor = None
    if author:
        doctor = db.query(DoctorProfile).filter(DoctorProfile.user_id == author.id).first()
    return PostOut(
        id=post.id,
        author_user_id=post.author_user_id,
        author_name=author.full_name if author else None,
        author_specialization=doctor.specialization if doctor else None,
        title=post.title,
        excerpt=post.excerpt,
        body=post.body,
        tags=post.tags,
        audience=post.audience,
        cover_image_url=post.cover_image_url,
        read_minutes=post.read_minutes,
        like_count=post.like_count,
        published_at=post.published_at,
    )

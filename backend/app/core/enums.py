from enum import StrEnum


class Role(StrEnum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    HOSPITAL = "hospital"
    LAB = "lab"
    PHARMACY = "pharmacy"
    INSURER = "insurer"
    ADMIN = "admin"


class ConditionCategory(StrEnum):
    ACUTE = "acute"
    CHRONIC = "chronic"
    INFECTIOUS = "infectious"
    INJURY = "injury"
    OTHER = "other"


class ConditionStatus(StrEnum):
    ACTIVE = "active"
    MANAGED = "managed"
    RESOLVED = "resolved"


class EncounterType(StrEnum):
    CONSULTATION = "consultation"
    FOLLOW_UP = "follow_up"
    ADMISSION = "admission"
    SURGERY = "surgery"
    EMERGENCY = "emergency"
    TELECONSULT = "teleconsult"


class PrescriptionStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class LabOrderStatus(StrEnum):
    ORDERED = "ordered"
    BOOKED = "booked"
    SAMPLE_COLLECTED = "sample_collected"
    PROCESSING = "processing"
    READY = "ready"
    CANCELLED = "cancelled"


class MedicineOrderStatus(StrEnum):
    PLACED = "placed"
    ACCEPTED = "accepted"
    READY = "ready"
    OUT_FOR_DELIVERY = "out_for_delivery"
    FULFILLED = "fulfilled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class AppointmentStatus(StrEnum):
    REQUESTED = "requested"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class AppointmentMode(StrEnum):
    IN_PERSON = "in_person"
    VIDEO = "video"


class ClaimStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    PARTIALLY_APPROVED = "partially_approved"
    REJECTED = "rejected"
    SETTLED = "settled"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentPurpose(StrEnum):
    APPOINTMENT = "appointment"
    LAB_ORDER = "lab_order"
    MEDICINE_ORDER = "medicine_order"
    PREMIUM = "premium"
    HOSPITAL_BILL = "hospital_bill"


class ReviewTarget(StrEnum):
    DOCTOR = "doctor"
    HOSPITAL = "hospital"
    LAB = "lab"
    PHARMACY = "pharmacy"
    INSURER = "insurer"


class DocumentKind(StrEnum):
    PRESCRIPTION = "prescription"
    LAB_REPORT = "lab_report"
    BILL = "bill"
    INSURANCE = "insurance"
    DISCHARGE_SUMMARY = "discharge_summary"
    IMAGING = "imaging"
    OTHER = "other"


class TimelineKind(StrEnum):
    CONSULTATION = "consultation"
    PRESCRIPTION = "prescription"
    LAB_REPORT = "lab_report"
    ADMISSION = "admission"
    SURGERY = "surgery"
    DIAGNOSIS = "diagnosis"
    VACCINATION = "vaccination"
    DOCUMENT = "document"
    EMERGENCY = "emergency"


class ReminderKind(StrEnum):
    MEDICINE = "medicine"
    WATER = "water"
    DIET = "diet"
    SLEEP = "sleep"
    EXERCISE = "exercise"
    APPOINTMENT = "appointment"
    VITALS = "vitals"


class ReminderSource(StrEnum):
    SELF = "self"
    DOCTOR = "doctor"
    ML = "ml"


class VitalType(StrEnum):
    BP_SYSTOLIC = "bp_systolic"
    BP_DIASTOLIC = "bp_diastolic"
    GLUCOSE_FASTING = "glucose_fasting"
    HBA1C = "hba1c"
    HEART_RATE = "heart_rate"
    WEIGHT = "weight"
    HEIGHT = "height"
    STEPS = "steps"
    SLEEP_HOURS = "sleep_hours"
    CALORIES_BURNT = "calories_burnt"
    WATER_ML = "water_ml"
    SPO2 = "spo2"


class ThreadKind(StrEnum):
    PATIENT_DOCTOR = "patient_doctor"
    DOCTOR_DOCTOR = "doctor_doctor"


class RecommendationKind(StrEnum):
    DOCTOR = "doctor"
    HOSPITAL = "hospital"
    LAB = "lab"
    PHARMACY = "pharmacy"
    INSURANCE = "insurance"
    DIET = "diet"
    WORKOUT = "workout"
    LIFESTYLE = "lifestyle"


class EmergencyStatus(StrEnum):
    REQUESTED = "requested"
    AMBULANCE_DISPATCHED = "ambulance_dispatched"
    EN_ROUTE = "en_route"
    ARRIVED = "arrived"
    CLOSED = "closed"
    CANCELLED = "cancelled"

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class DoctorOut(ORMModel):
    id: int
    user_id: int
    full_name: str
    avatar_url: str | None = None
    specialization: str
    qualifications: str | None = None
    registration_no: str | None = None
    years_experience: int
    consultation_fee: float
    languages: str | None = None
    bio: str | None = None
    city: str | None = None
    hospital_id: int | None = None
    hospital_name: str | None = None
    accepts_teleconsult: bool
    rating_avg: float
    rating_count: int
    is_verified: bool
    procedures_performed: int = 0
    complex_case_success_rate: float | None = None
    # Populated on recommendation responses only.
    distance_km: float | None = None
    match_score: float | None = None
    match_reason: str | None = None


class DoctorUpdate(BaseModel):
    specialization: str | None = None
    qualifications: str | None = None
    years_experience: int | None = None
    consultation_fee: float | None = None
    languages: str | None = None
    bio: str | None = None
    city: str | None = None
    hospital_id: int | None = None
    accepts_teleconsult: bool | None = None


class HospitalOut(ORMModel):
    id: int
    name: str
    kind: str | None = None
    address: str | None = None
    city: str | None = None
    phone: str | None = None
    specializations: str | None = None
    services: str | None = None
    bed_count: int
    icu_bed_count: int
    doctor_count: int
    employee_count: int
    has_emergency: bool
    has_ambulance: bool
    avg_consultation_fee: float
    about: str | None = None
    accreditation: str | None = None
    surgery_success_rate: float | None = None
    complex_cases_handled: int = 0
    rating_avg: float
    rating_count: int
    is_verified: bool
    distance_km: float | None = None
    match_score: float | None = None
    match_reason: str | None = None


class LabTestOut(ORMModel):
    id: int
    lab_id: int
    name: str
    code: str | None = None
    category: str | None = None
    price: float
    discount_percent: float
    effective_price: float
    turnaround_hours: int
    fasting_required: bool
    description: str | None = None


class LabOut(ORMModel):
    id: int
    name: str
    address: str | None = None
    city: str | None = None
    phone: str | None = None
    accreditation: str | None = None
    home_collection: bool
    home_collection_fee: float
    opens_at: str | None = None
    closes_at: str | None = None
    about: str | None = None
    rating_avg: float
    rating_count: int
    is_verified: bool
    distance_km: float | None = None
    match_score: float | None = None
    match_reason: str | None = None
    quoted_total: float | None = None
    tests: list[LabTestOut] = []


class PharmacyItemOut(ORMModel):
    id: int
    pharmacy_id: int
    medicine_name: str
    strength: str | None = None
    form: str | None = None
    manufacturer: str | None = None
    mrp: float
    selling_price: float
    stock_qty: int
    in_stock: bool
    requires_prescription: bool


class PharmacyOut(ORMModel):
    id: int
    name: str
    address: str | None = None
    city: str | None = None
    phone: str | None = None
    delivers: bool
    delivery_fee: float
    avg_delivery_minutes: int
    is_24x7: bool
    rating_avg: float
    rating_count: int
    is_verified: bool
    distance_km: float | None = None
    match_score: float | None = None
    match_reason: str | None = None
    quoted_total: float | None = None
    unavailable_items: list[str] = []


class InsurancePlanOut(ORMModel):
    id: int
    insurer_id: int
    insurer_name: str | None = None
    name: str
    cover_amount: float
    annual_premium: float
    room_rent_limit: float | None = None
    waiting_period_months: int
    covers_pre_existing: bool
    covers_daycare: bool
    covers_opd: bool
    network_hospital_count: int
    highlights: str | None = None
    match_score: float | None = None
    match_reason: str | None = None


class InsurerOut(ORMModel):
    id: int
    name: str
    irdai_reg_no: str | None = None
    support_phone: str | None = None
    claim_settlement_ratio: float
    avg_settlement_days: int
    rating_avg: float
    rating_count: int
    about: str | None = None


class ReviewOut(ORMModel):
    id: int
    author_user_id: int
    author_name: str | None = None
    target_kind: str
    target_id: int
    rating: int
    title: str | None = None
    comment: str | None = None
    is_verified_visit: bool
    provider_response: str | None = None
    created_at: datetime


class ReviewCreate(BaseModel):
    target_kind: str
    target_id: int
    rating: int
    title: str | None = None
    comment: str | None = None
    encounter_id: int | None = None


class RatingBreakdown(BaseModel):
    average: float
    count: int
    stars: dict[int, int]

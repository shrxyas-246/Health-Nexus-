from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class AppointmentOut(ORMModel):
    id: int
    patient_id: int
    patient_name: str | None = None
    doctor_id: int
    doctor_name: str | None = None
    doctor_specialization: str | None = None
    hospital_id: int | None = None
    hospital_name: str | None = None
    scheduled_at: datetime
    duration_minutes: int
    mode: str
    status: str
    reason: str | None = None
    fee: float
    is_follow_up: bool


class AppointmentCreate(BaseModel):
    doctor_id: int
    scheduled_at: datetime
    mode: str = "in_person"
    reason: str | None = None
    hospital_id: int | None = None
    is_follow_up: bool = False


class AppointmentStatusUpdate(BaseModel):
    status: str
    cancelled_reason: str | None = None


class LabOrderItemOut(ORMModel):
    id: int
    lab_test_id: int | None = None
    test_request_id: int | None = None
    test_name: str
    price: float


class LabOrderOut(ORMModel):
    id: int
    patient_id: int
    patient_name: str | None = None
    lab_id: int
    lab_name: str | None = None
    doctor_id: int | None = None
    doctor_name: str | None = None
    prescription_id: int | None = None
    status: str
    scheduled_at: datetime | None = None
    home_collection: bool
    collection_address: str | None = None
    subtotal: float
    discount: float
    total_amount: float
    notes: str | None = None
    created_at: datetime
    items: list[LabOrderItemOut] = []


class LabOrderCreate(BaseModel):
    lab_id: int
    # Either book against doctor-requested tests, or pick from the lab's catalogue.
    test_request_ids: list[int] = Field(default_factory=list)
    lab_test_ids: list[int] = Field(default_factory=list)
    scheduled_at: datetime | None = None
    home_collection: bool = False
    collection_address: str | None = None
    notes: str | None = None


class LabOrderStatusUpdate(BaseModel):
    status: str
    scheduled_at: datetime | None = None


class LabReportValueOut(ORMModel):
    id: int
    analyte: str
    value: float | None = None
    text_value: str | None = None
    unit: str | None = None
    ref_low: float | None = None
    ref_high: float | None = None
    flag: str | None = None


class LabReportOut(ORMModel):
    id: int
    patient_id: int
    lab_id: int | None = None
    lab_name: str | None = None
    lab_order_id: int | None = None
    title: str
    issued_at: datetime
    summary: str | None = None
    file_url: str | None = None
    shared_with_doctor_id: int | None = None
    doctor_reviewed_at: datetime | None = None
    doctor_remarks: str | None = None
    is_legacy: bool
    values: list[LabReportValueOut] = []


class LabReportValueCreate(BaseModel):
    analyte: str
    value: float | None = None
    text_value: str | None = None
    unit: str | None = None
    ref_low: float | None = None
    ref_high: float | None = None


class LabReportCreate(BaseModel):
    title: str
    lab_order_id: int | None = None
    lab_id: int | None = None
    issued_at: datetime | None = None
    summary: str | None = None
    file_url: str | None = None
    share_with_doctor_id: int | None = None
    is_legacy: bool = False
    values: list[LabReportValueCreate] = Field(default_factory=list)


class DoctorRemarkCreate(BaseModel):
    remarks: str
    request_follow_up: bool = False
    follow_up_at: datetime | None = None


class MedicineOrderItemOut(ORMModel):
    id: int
    medicine_name: str
    strength: str | None = None
    quantity: int
    unit_price: float
    line_total: float
    substituted_with: str | None = None


class MedicineOrderOut(ORMModel):
    id: int
    patient_id: int
    patient_name: str | None = None
    pharmacy_id: int
    pharmacy_name: str | None = None
    prescription_id: int | None = None
    status: str
    delivery: bool
    delivery_address: str | None = None
    subtotal: float
    discount: float
    delivery_fee: float
    total_amount: float
    ready_at: datetime | None = None
    rejection_reason: str | None = None
    created_at: datetime
    items: list[MedicineOrderItemOut] = []


class MedicineOrderCreate(BaseModel):
    pharmacy_id: int
    prescription_id: int | None = None
    delivery: bool = False
    delivery_address: str | None = None
    # Omit to forward every medicine on the prescription.
    prescription_item_ids: list[int] = Field(default_factory=list)


class MedicineOrderStatusUpdate(BaseModel):
    status: str
    rejection_reason: str | None = None
    ready_at: datetime | None = None


class EmergencyRequestCreate(BaseModel):
    latitude: float | None = None
    longitude: float | None = None
    address_hint: str | None = None
    complaint: str | None = None


class EmergencyRequestOut(ORMModel):
    id: int
    patient_id: int
    hospital_id: int | None = None
    hospital_name: str | None = None
    hospital_phone: str | None = None
    status: str
    latitude: float | None = None
    longitude: float | None = None
    address_hint: str | None = None
    complaint: str | None = None
    ambulance_eta_minutes: int | None = None
    ambulance_ref: str | None = None
    record_pushed_at: datetime | None = None
    paperwork_deferred: bool
    created_at: datetime

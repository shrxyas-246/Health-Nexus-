from datetime import date

from pydantic import BaseModel, EmailStr, Field

from app.core.enums import Role
from app.schemas.common import ORMModel


class UserOut(ORMModel):
    id: int
    email: EmailStr
    phone: str | None = None
    full_name: str
    role: str
    avatar_url: str | None = None
    is_active: bool


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PatientRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str
    phone: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    blood_group: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    city: str | None = None


class DoctorRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str
    phone: str | None = None
    registration_no: str
    specialization: str
    qualifications: str | None = None
    years_experience: int = 0
    consultation_fee: float = 0
    city: str | None = None
    hospital_id: int | None = None
    bio: str | None = None


class ProviderRegisterRequest(BaseModel):
    """Shared signup for hospital / lab / pharmacy / insurer operator accounts."""

    email: EmailStr
    password: str = Field(min_length=8)
    role: Role
    organisation_name: str
    contact_name: str
    phone: str | None = None
    city: str | None = None
    address: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)

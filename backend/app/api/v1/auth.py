import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.enums import Role
from app.core.security import create_access_token, hash_password, verify_password
from app.models import (
    DoctorProfile,
    Hospital,
    Insurer,
    Lab,
    PatientProfile,
    Pharmacy,
    User,
)
from app.schemas.auth import (
    ChangePasswordRequest,
    DoctorRegisterRequest,
    LoginRequest,
    PatientRegisterRequest,
    ProviderRegisterRequest,
    Token,
    UserOut,
)
from app.schemas.common import Message

router = APIRouter(prefix="/auth", tags=["auth"])


def _new_medical_id() -> str:
    return f"HNX-{secrets.randbelow(900000) + 100000}"


def _ensure_email_free(db, email: str) -> None:
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")


def _issue(db, user: User) -> Token:
    token = create_access_token(subject=user.id, role=user.role)
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.post("/register/patient", response_model=Token, status_code=status.HTTP_201_CREATED)
def register_patient(payload: PatientRegisterRequest, db: DbSession) -> Token:
    _ensure_email_free(db, payload.email)

    user = User(
        email=payload.email,
        phone=payload.phone,
        hashed_password=hash_password(payload.password),
        role=Role.PATIENT,
        full_name=payload.full_name,
    )
    db.add(user)
    db.flush()

    # Medical IDs are user-visible, so retry rather than risk a collision.
    medical_id = _new_medical_id()
    while db.scalar(select(PatientProfile.id).where(PatientProfile.medical_id == medical_id)):
        medical_id = _new_medical_id()

    db.add(
        PatientProfile(
            user_id=user.id,
            medical_id=medical_id,
            date_of_birth=payload.date_of_birth,
            gender=payload.gender,
            blood_group=payload.blood_group,
            height_cm=payload.height_cm,
            weight_kg=payload.weight_kg,
            city=payload.city,
        )
    )
    db.commit()
    db.refresh(user)
    return _issue(db, user)


@router.post("/register/doctor", response_model=Token, status_code=status.HTTP_201_CREATED)
def register_doctor(payload: DoctorRegisterRequest, db: DbSession) -> Token:
    _ensure_email_free(db, payload.email)
    if db.scalar(select(DoctorProfile.id).where(DoctorProfile.registration_no == payload.registration_no)):
        raise HTTPException(status_code=409, detail="This registration number is already in use")

    user = User(
        email=payload.email,
        phone=payload.phone,
        hashed_password=hash_password(payload.password),
        role=Role.DOCTOR,
        full_name=payload.full_name,
    )
    db.add(user)
    db.flush()

    db.add(
        DoctorProfile(
            user_id=user.id,
            registration_no=payload.registration_no,
            specialization=payload.specialization,
            qualifications=payload.qualifications,
            years_experience=payload.years_experience,
            consultation_fee=payload.consultation_fee,
            city=payload.city,
            hospital_id=payload.hospital_id,
            bio=payload.bio,
        )
    )
    db.commit()
    db.refresh(user)
    return _issue(db, user)


PROVIDER_MODELS = {Role.HOSPITAL: Hospital, Role.LAB: Lab, Role.PHARMACY: Pharmacy, Role.INSURER: Insurer}


@router.post("/register/provider", response_model=Token, status_code=status.HTTP_201_CREATED)
def register_provider(payload: ProviderRegisterRequest, db: DbSession) -> Token:
    """Signup for hospital, lab, pharmacy and insurer operator accounts."""
    if payload.role not in PROVIDER_MODELS:
        raise HTTPException(
            status_code=400,
            detail="role must be one of: hospital, lab, pharmacy, insurer",
        )
    _ensure_email_free(db, payload.email)

    user = User(
        email=payload.email,
        phone=payload.phone,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        full_name=payload.contact_name,
    )
    db.add(user)
    db.flush()

    model = PROVIDER_MODELS[payload.role]
    org = model(name=payload.organisation_name, owner_user_id=user.id)
    # Insurers have no physical address columns; the rest do.
    if payload.role != Role.INSURER:
        org.address = payload.address
        org.city = payload.city
        org.phone = payload.phone
    db.add(org)
    db.commit()
    db.refresh(user)
    return _issue(db, user)


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: DbSession) -> Token:
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated")
    return _issue(db, user)


@router.post("/token", response_model=Token, include_in_schema=False)
def login_form(db: DbSession, form: OAuth2PasswordRequestForm = Depends()) -> Token:
    """OAuth2 password flow, so the Swagger UI Authorize button works."""
    return login(LoginRequest(email=form.username, password=form.password), db)


@router.get("/me", response_model=UserOut)
def read_me(user: CurrentUser) -> User:
    return user


@router.post("/change-password", response_model=Message)
def change_password(payload: ChangePasswordRequest, user: CurrentUser, db: DbSession) -> Message:
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return Message(detail="Password updated")

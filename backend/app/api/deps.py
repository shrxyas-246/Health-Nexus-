from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import Role
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import (
    Appointment,
    CareTeamLink,
    DoctorProfile,
    Encounter,
    PatientProfile,
    User,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login", auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession, token: Annotated[str | None, Depends(oauth2_scheme)]
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_error
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        raise credentials_error

    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise credentials_error
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role) -> Callable[[User], User]:
    allowed = {str(r) for r in roles}

    def dependency(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This endpoint requires one of: {', '.join(sorted(allowed))}",
            )
        return user

    return dependency


def get_current_patient(db: DbSession, user: CurrentUser) -> PatientProfile:
    profile = db.scalar(select(PatientProfile).where(PatientProfile.user_id == user.id))
    if not profile:
        raise HTTPException(status_code=403, detail="No patient profile for this account")
    return profile


def get_current_doctor(db: DbSession, user: CurrentUser) -> DoctorProfile:
    profile = db.scalar(select(DoctorProfile).where(DoctorProfile.user_id == user.id))
    if not profile:
        raise HTTPException(status_code=403, detail="No doctor profile for this account")
    return profile


CurrentPatient = Annotated[PatientProfile, Depends(get_current_patient)]
CurrentDoctor = Annotated[DoctorProfile, Depends(get_current_doctor)]


def doctor_can_access_patient(db: Session, doctor_id: int, patient_id: int) -> bool:
    """A doctor sees a record only through a real care relationship.

    Standing care-team membership, a past or present encounter, or a booked
    appointment all qualify. Everything else is refused.
    """
    on_care_team = db.scalar(
        select(CareTeamLink.id).where(
            CareTeamLink.doctor_id == doctor_id,
            CareTeamLink.patient_id == patient_id,
            CareTeamLink.active.is_(True),
        )
    )
    if on_care_team:
        return True
    seen_before = db.scalar(
        select(Encounter.id).where(
            Encounter.doctor_id == doctor_id, Encounter.patient_id == patient_id
        )
    )
    if seen_before:
        return True
    has_appointment = db.scalar(
        select(Appointment.id).where(
            Appointment.doctor_id == doctor_id, Appointment.patient_id == patient_id
        )
    )
    return bool(has_appointment)


def resolve_patient_access(db: Session, user: User, patient_id: int) -> PatientProfile:
    """Load a patient record, enforcing who is allowed to see it.

    Patients reach only their own record; doctors need a care relationship;
    admins are unrestricted.
    """
    patient = db.get(PatientProfile, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if user.role == Role.ADMIN:
        return patient

    if user.role == Role.PATIENT:
        if patient.user_id != user.id:
            raise HTTPException(status_code=403, detail="You can only access your own record")
        return patient

    if user.role == Role.DOCTOR:
        doctor = db.scalar(select(DoctorProfile).where(DoctorProfile.user_id == user.id))
        if doctor and doctor_can_access_patient(db, doctor.id, patient.id):
            return patient
        raise HTTPException(
            status_code=403, detail="No care relationship with this patient"
        )

    raise HTTPException(status_code=403, detail="Not permitted to access patient records")


def get_accessible_patient(db: DbSession, user: CurrentUser, patient_id: int) -> PatientProfile:
    """Path-parameter dependency for every `/patients/{patient_id}/...` route."""
    return resolve_patient_access(db, user, patient_id)


AccessiblePatient = Annotated[PatientProfile, Depends(get_accessible_patient)]

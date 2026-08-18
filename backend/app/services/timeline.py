from datetime import datetime

from sqlalchemy.orm import Session

from app.core.enums import TimelineKind
from app.models import TimelineEvent


def record_event(
    db: Session,
    *,
    patient_id: int,
    kind: TimelineKind | str,
    occurred_at: datetime,
    title: str,
    summary: str | None = None,
    doctor_id: int | None = None,
    hospital_id: int | None = None,
    lab_id: int | None = None,
    condition_id: int | None = None,
    ref_table: str | None = None,
    ref_id: int | None = None,
    is_legacy: bool = False,
    editable_by_patient: bool = False,
) -> TimelineEvent:
    """Append to a patient's timeline.

    App-generated records are written here automatically and are read-only for
    the patient; entries the patient backfills themselves stay editable.
    """
    event = TimelineEvent(
        patient_id=patient_id,
        kind=str(kind),
        occurred_at=occurred_at,
        title=title,
        summary=summary,
        doctor_id=doctor_id,
        hospital_id=hospital_id,
        lab_id=lab_id,
        condition_id=condition_id,
        ref_table=ref_table,
        ref_id=ref_id,
        is_legacy=is_legacy,
        editable_by_patient=editable_by_patient,
    )
    db.add(event)
    db.flush()
    return event


def remove_events_for(db: Session, ref_table: str, ref_id: int) -> None:
    """Drop generated events when their source row is deleted."""
    db.query(TimelineEvent).filter(
        TimelineEvent.ref_table == ref_table, TimelineEvent.ref_id == ref_id
    ).delete(synchronize_session=False)

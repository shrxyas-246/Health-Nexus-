from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import ReviewTarget
from app.models import DoctorProfile, Hospital, Insurer, Lab, Pharmacy, Review

TARGET_MODELS = {
    ReviewTarget.DOCTOR: DoctorProfile,
    ReviewTarget.HOSPITAL: Hospital,
    ReviewTarget.LAB: Lab,
    ReviewTarget.PHARMACY: Pharmacy,
    ReviewTarget.INSURER: Insurer,
}


def resolve_target(db: Session, target_kind: str, target_id: int):
    model = TARGET_MODELS.get(target_kind)
    if model is None:
        return None
    return db.get(model, target_id)


def recompute_rating(db: Session, target_kind: str, target_id: int) -> tuple[float, int]:
    """Refresh the cached average on the provider row after a review changes."""
    avg, count = db.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(
            Review.target_kind == target_kind, Review.target_id == target_id
        )
    ).one()

    avg = round(float(avg), 2) if avg is not None else 0.0
    count = int(count or 0)

    target = resolve_target(db, target_kind, target_id)
    if target is not None:
        target.rating_avg = avg
        target.rating_count = count
        db.flush()
    return avg, count


def star_breakdown(db: Session, target_kind: str, target_id: int) -> dict[int, int]:
    rows = db.execute(
        select(Review.rating, func.count(Review.id))
        .where(Review.target_kind == target_kind, Review.target_id == target_id)
        .group_by(Review.rating)
    ).all()
    counts = {star: 0 for star in range(1, 6)}
    for rating, count in rows:
        counts[int(rating)] = int(count)
    return counts

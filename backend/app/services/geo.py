from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0


def haversine_km(
    lat1: float | None, lon1: float | None, lat2: float | None, lon2: float | None
) -> float | None:
    """Great-circle distance in km, or None when either point is unknown."""
    if None in (lat1, lon1, lat2, lon2):
        return None
    p1, p2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlambda / 2) ** 2
    return round(2 * EARTH_RADIUS_KM * asin(sqrt(a)), 2)

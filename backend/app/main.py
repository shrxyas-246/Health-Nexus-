from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import (
    appointments,
    auth,
    billing,
    doctors,
    encounters,
    hospitals,
    insurance,
    labs,
    patients,
    pharmacy,
    premium,
    prescriptions,
    social,
    wellness,
)
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine

import app.models  # noqa: F401  (register every table on Base.metadata)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    description=(
        "Health Nexus — the connected healthcare ecosystem API. "
        "Patients, doctors, hospitals, labs, pharmacies and insurers on one platform."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def init_db() -> None:
    # Dev convenience; production migrations run through Alembic instead.
    Base.metadata.create_all(bind=engine)


@app.get("/health", tags=["meta"])
def healthcheck() -> dict:
    return {"status": "ok", "service": settings.PROJECT_NAME}


for router in (
    auth.router,
    patients.router,
    doctors.router,
    encounters.router,
    prescriptions.router,
    appointments.router,
    labs.router,
    pharmacy.router,
    hospitals.router,
    insurance.router,
    billing.router,
    social.router,
    wellness.router,
    premium.router,
):
    app.include_router(router, prefix=settings.API_V1_PREFIX)

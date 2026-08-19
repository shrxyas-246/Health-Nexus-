from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Everything is overridable via environment or .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    PROJECT_NAME: str = "Health Nexus API"
    API_V1_PREFIX: str = "/api/v1"

    # SQLite keeps local development zero-setup; point at Postgres for anything shared.
    # e.g. postgresql+psycopg://user:pass@localhost:5432/health_nexus
    DATABASE_URL: str = "sqlite:///./health_nexus.db"

    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    ALGORITHM: str = "HS256"

    # Comma-separated list of allowed browser origins.
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Platform commission taken on every payment routed through the app.
    COMMISSION_RATE: float = 0.05

    # Base URL of the ML service in ml/ — the five recommenders, the guidance
    # assistant and the daily wellness plan. When unset (or unreachable), the
    # recommendation endpoints fall back to the deterministic ranking in
    # services/recommendations.py and the chatbot to the FAQ rules in
    # api/v1/wellness.py, so the product still works end to end.
    ML_SERVICE_URL: str | None = None

    UPLOAD_DIR: str = "./uploads"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

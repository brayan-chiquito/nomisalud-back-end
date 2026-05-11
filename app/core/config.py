from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    APP_NAME: str = "NomiSalud API"
    APP_VERSION: str = "0.1.0"
    APP_DESCRIPTION: str = "API backend para NomiSalud"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "nomisalud"
    POSTGRES_PASSWORD: str = "nomisalud_password"
    POSTGRES_DB: str = "nomisalud_db"

    # Security
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Carga de incapacidades (multipart)
    UPLOAD_STORAGE_DIR: str = "var/uploads"
    MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024  # 10 MiB
    INCAPACIDADES_PAGE_SIZE: int = 20

    # Google Gemini (extracción IA)
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_EXTRACTION_MAX_ATTEMPTS: int = 4
    GEMINI_EXTRACTION_BACKOFF_BASE_SECONDS: float = 1.0
    GEMINI_HTTP_TIMEOUT_SECONDS: float = 120.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def database_url_sync(self) -> str:
        """URL síncrona usada por Alembic."""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

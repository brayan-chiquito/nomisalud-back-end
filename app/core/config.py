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

    # Tesseract OCR (SCRUM-165 / SCRUM-166)
    TESSERACT_CMD: str | None = None
    TESSERACT_LANG: str = "spa+eng"
    OCR_CONTRAST_FACTOR: float = 2.0
    OCR_PDF_RENDER_DPI: int = 200
    OCR_MIN_CHARS_PDF_NATIVO: int = 40

    # APScheduler — revisión diaria de vencimientos (SCRUM-180)
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_TIMEZONE: str = "America/Bogota"
    SCHEDULER_CRON_HOUR: int = 7
    SCHEDULER_CRON_MINUTE: int = 0

    # SMTP / alertas por correo (SCRUM-181)
    MAIL_ENABLED: bool = False
    MAIL_SERVER: str = ""
    MAIL_PORT: int = 587
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = ""
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    MAIL_VALIDATE_CERTS: bool = True
    MAIL_ALERT_RECIPIENTS: str = ""

    # Deduplicación de alertas (SCRUM-182)
    ALERTAS_DEDUP_DIAS: int = 7

    # Listado de pagos (SCRUM-186)
    PAGOS_PAGE_SIZE: int = 20

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
    def mail_alert_recipients_list(self) -> list[str]:
        """Destinatarios RRHH para alertas (lista desde CSV en env)."""
        if not self.MAIL_ALERT_RECIPIENTS.strip():
            return []
        return [
            correo.strip()
            for correo in self.MAIL_ALERT_RECIPIENTS.split(",")
            if correo.strip()
        ]

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

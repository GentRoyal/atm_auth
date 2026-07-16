"""
config.py  –  Application settings loaded from .env
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


ENV_FILE = Path(__file__).with_name(".env")


class Settings(BaseSettings):
    # Database
    DATABASE_PROVIDER: str = "supabase"
    SUPABASE_DATABASE_URL: str | None = None
    SUPABASE_DATABASE_URL_SYNC: str | None = None
    POSTGRES_DATABASE_URL: str | None = None
    POSTGRES_DATABASE_URL_SYNC: str | None = None
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/atm_auth_system"
    DATABASE_URL_SYNC: str | None = None
    DB_POOL_MIN_SIZE: int = 1
    DB_POOL_MAX_SIZE: int = 3

    # Security
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    SESSION_EXPIRE_MINUTES: int = 10

    # SMS
    SMS_PROVIDER: str = "dev"
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""
    TERMII_API_KEY: str = ""
    TERMII_SENDER_ID: str = ""
    TERMII_CHANNEL: str = "generic"
    TERMII_BASE_URL: str = "https://api.ng.termii.com"
    SMSTO_API_KEY: str = ""
    SMSTO_SENDER_ID: str = ""
    SMSTO_BASE_URL: str = "https://api.sms.to"

    # URLs
    BASE_URL: str = "http://localhost:8000"
    PUBLIC_BASE_URL: str | None = None
    MOBILE_FACE_URL: str = "http://localhost:8000/mobile"

    # Thresholds
    VOICE_SIMILARITY_THRESHOLD: float = 0.00 #0.65
    FACE_SIMILARITY_THRESHOLD: float = 1.75 #0.55

    # Authentication toggles
    ENABLE_VOICE_AUTH: bool = False

    # CORS
    CORS_ORIGINS: str = "http://localhost:8000"

    @property
    def database_provider(self) -> str:
        provider = self.DATABASE_PROVIDER.strip().lower()
        aliases = {
            "postgres": "postgresql",
            "postgresql": "postgresql",
            "local": "postgresql",
            "supabase": "supabase",
        }
        if provider not in aliases:
            allowed = ", ".join(sorted(set(aliases.values())))
            raise ValueError(f"DATABASE_PROVIDER must be one of: {allowed}")
        return aliases[provider]

    @staticmethod
    def _env_value(value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @property
    def active_database_url(self) -> str:
        if self.database_provider == "supabase":
            return self._env_value(self.SUPABASE_DATABASE_URL) or self.DATABASE_URL
        return self._env_value(self.POSTGRES_DATABASE_URL) or self.DATABASE_URL

    @property
    def active_database_url_sync(self) -> str | None:
        if self.database_provider == "supabase":
            return (
                self._env_value(self.SUPABASE_DATABASE_URL_SYNC)
                or self._env_value(self.DATABASE_URL_SYNC)
            )
        return (
            self._env_value(self.POSTGRES_DATABASE_URL_SYNC)
            or self._env_value(self.DATABASE_URL_SYNC)
        )

    @property
    def cors_origins_list(self) -> list[str]:
        origins = [o.strip().rstrip("/") for o in self.CORS_ORIGINS.split(",") if o.strip()]
        if self.PUBLIC_BASE_URL:
            origins.append(self.PUBLIC_BASE_URL.rstrip("/"))
        return list(dict.fromkeys(origins))

    @property
    def face_link_base_url(self) -> str:
        return (self.PUBLIC_BASE_URL or self.BASE_URL).rstrip("/")

    class Config:
        env_file = str(ENV_FILE)
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()



"""
config.py  –  Application settings loaded from .env
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


ENV_FILE = Path(__file__).with_name(".env")


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/atm_auth_system"
    DATABASE_URL_SYNC: str | None = None

    # Security
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    SESSION_EXPIRE_MINUTES: int = 10

    # SMS
    SMS_PROVIDER: str = "dev"
    AT_USERNAME: str = "sandbox"
    AT_API_KEY: str = ""
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""

    # URLs
    BASE_URL: str = "http://localhost:8000"
    PUBLIC_BASE_URL: str | None = None
    MOBILE_FACE_URL: str = "http://localhost:8000/mobile"

    # Thresholds
    VOICE_SIMILARITY_THRESHOLD: float = 0.00 #0.65
    FACE_SIMILARITY_THRESHOLD: float = 0.55

    # Authentication toggles
    ENABLE_VOICE_AUTH: bool = False

    # CORS
    CORS_ORIGINS: str = "http://localhost:8000"

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

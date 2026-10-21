"""Application configuration.

All settings come from environment variables (or backend/.env in development).
Nothing secret is hardcoded here — production refuses to start with the
placeholder JWT secret.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_DEFAULT_SECRET = "change-me-in-env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    APP_NAME: str = "KnowBot"
    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    LOG_LEVEL: str = "INFO"
    FRONTEND_URL: str = "http://localhost:5173"
    CORS_ORIGINS: str = "http://localhost:5173"

    # --- Database / Redis ---
    DATABASE_URL: str = "postgresql+psycopg2://knowbot:knowbot@localhost:5432/knowbot"
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Auth ---
    JWT_SECRET_KEY: str = _INSECURE_DEFAULT_SECRET
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    PASSWORD_RESET_EXPIRE_MINUTES: int = 30
    INVITATION_EXPIRE_DAYS: int = 7

    # --- AI ---
    # "openai" for real usage; "fake" is a deterministic offline provider used by
    # the automated tests (and for local runs before an API key is configured).
    AI_PROVIDER: Literal["openai", "gemini", "fake"] = "openai"
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "models/gemini-embedding-001"
    EMBEDDING_DIM: int = 3072
    CHAT_MODEL: str = "models/gemini-3.8-flash"
    CHAT_TEMPERATURE: float = 0.0
    CHAT_MAX_TOKENS: int = 800

    # --- RAG ---
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    RETRIEVAL_TOP_K: int = 5
    # Chunks below this cosine similarity are treated as irrelevant. If nothing
    # passes, we answer "not found" without calling the LLM at all.
    RETRIEVAL_MIN_SIMILARITY: float = 0.2
    SEMANTIC_CACHE_THRESHOLD: float = 0.92
    SEMANTIC_CACHE_TTL_SECONDS: int = 24 * 60 * 60
    SEMANTIC_CACHE_MAX_ENTRIES: int = 500
    PROCESSING_MAX_ATTEMPTS: int = 3

    # --- Uploads / storage ---
    MAX_UPLOAD_SIZE_MB: int = 10
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    UPLOAD_DIR: str = "uploads"
    S3_BUCKET: str = ""
    AWS_REGION: str = "ap-south-1"

    # --- Rate limits (requests per window) ---
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_LOGIN: str = "10/60"          # 10 per minute per IP
    RATE_LIMIT_REFRESH: str = "60/60"        # page reloads refresh; token itself is unguessable
    RATE_LIMIT_REGISTER: str = "5/3600"
    RATE_LIMIT_CHAT: str = "20/60"
    RATE_LIMIT_UPLOAD: str = "10/60"
    RATE_LIMIT_API_KEYS: str = "20/60"
    RATE_LIMIT_PASSWORD_RESET: str = "5/3600"

    # --- Email ---
    EMAIL_PROVIDER: Literal["console", "smtp","resend"] = "console"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "KnowBot <no-reply@knowbot.local>"
    RESEND_API_KEY: str = ""

    NOT_FOUND_MESSAGE: str = Field(
        default="I couldn't find this information in your company's documents."
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @model_validator(mode="after")
    def _validate_production(self) -> "Settings":
        if self.ENVIRONMENT == "production":
            if self.JWT_SECRET_KEY == _INSECURE_DEFAULT_SECRET or len(self.JWT_SECRET_KEY) < 32:
                raise ValueError("JWT_SECRET_KEY must be set to a strong value (32+ chars) in production")
            if self.AI_PROVIDER not in ("openai", "gemini"):
                raise ValueError("AI_PROVIDER must be 'openai' in production")
        if self.CHUNK_OVERLAP >= self.CHUNK_SIZE:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

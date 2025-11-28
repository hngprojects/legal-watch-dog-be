import os
from pathlib import Path

from cryptography.fernet import Fernet
from decouple import Config, RepositoryEnv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "main.py").exists())
BASE_DIR = PROJECT_ROOT

# Determine which env file to load
env_file = os.getenv("ENV_FILE", ".env")
env_path = PROJECT_ROOT / env_file

# Only use RepositoryEnv if the env file exists
if env_path.exists():
    config = Config(RepositoryEnv(env_path))
else:
    # fallback: read directly from os.environ using decouple's AutoConfig
    from decouple import AutoConfig

    config = AutoConfig(search_path=None)


class Settings(BaseSettings):
    # App general
    DEBUG: bool = config("DEBUG", default=False, cast=bool)
    APP_NAME: str = config("APP_NAME", default="LEGAL WATCH DOG")
    APP_VERSION: str = config("APP_VERSION", default="1.0.0")
    ENVIRONMENT: str = config("ENVIRONMENT", default="dev")
    APP_PORT: int = config("APP_PORT", default=8000, cast=int)
    SECRET_KEY: str = config("SECRET_KEY", default="your-secret-key-for-sessions")
    LEGAL_WATCH_DOG_BASE_URL: str = config("LEGAL_WATCH_DOG_BASE_URL", default="minamoto.emerj.net")
    APP_URL: str = config("APP_URL", default="https://minamoto.emerj.net")
    DEV_URL: str = config("DEV_URL", default="http://localhost:3000")

    # Database
    DB_TYPE: str = config("DB_TYPE", default="postgresql")
    DB_HOST: str = config("DB_HOST", default="localhost")
    DB_PORT: int = config("DB_PORT", default=5432, cast=int)
    DB_USER: str = config("DB_USER", default="user")
    DB_PASS: str = config("DB_PASS", default="password")
    DB_NAME: str = config("DB_NAME", default="dbname")
    DATABASE_URL: str = config(
        "DATABASE_URL", default="postgresql://user:password@localhost/dbname"
    )

    # Redis
    REDIS_URL: str = config("REDIS_URL", default="redis://localhost:6379/0")
    REDIS_RESEND_TTL: int = config("REDIS_RESEND_TTL", default=300, cast=int)
    REDIS_REGISTER_TTL: int = config("REDIS_REGISTER_TTL", default=86400, cast=int)

    # JWT Authentication
    JWT_SECRET: str = config("JWT_SECRET", default="your-super-secret-jwt-key-change-in-production")
    JWT_ALGORITHM: str = config("JWT_ALGORITHM", default="HS256")
    JWT_EXPIRY_HOURS: int = config("JWT_EXPIRY_HOURS", default=24, cast=int)

    # Encryption
    ENCRYPTION_KEY: str = config("ENCRYPTION_KEY", default="YOUR_GENERATED_KEY_HERE")

    # Waitlist Email
    MAIL_USERNAME: str = config("MAIL_USERNAME", default="test_user")
    MAIL_PASSWORD: str = config("MAIL_PASSWORD", default="test_pass")
    EMAIL: str = config("EMAIL", default="test@example.com")
    SMTP_SERVER: str = config("SMTP_SERVER", default="smtp.test.com")
    SMTP_PORT: int = config("SMTP_PORT", default=1025, cast=int)

    # Email Verification
    ALLOW_TEST_EMAIL_PROVIDERS: bool = config("ALLOW_TEST_EMAIL_PROVIDERS", default=True, cast=bool)
    TEST_EMAIL_PROVIDERS: str = config("TEST_EMAIL_PROVIDERS", default="gmail.com")

    # Invitation
    INVITATION_TOKEN_EXPIRE_MINUTES: int = config(
        "INVITATION_TOKEN_EXPIRE_MINUTES", default=1440, cast=int
    )

    # MinIO
    # Scraping
    SCRAPE_MAX_RETRIES: int = config("SCRAPE_MAX_RETRIES", default=5, cast=int)
    SCRAPE_BASE_DELAY: int = config("SCRAPE_BASE_DELAY", default=60, cast=int)
    SCRAPE_MAX_DELAY: int = config("SCRAPE_MAX_DELAY", default=3600, cast=int)
    SCRAPE_DISPATCH_LOCK_TIMEOUT: int = config("SCRAPE_DISPATCH_LOCK_TIMEOUT", default=60, cast=int)
    SCRAPE_BATCH_SIZE: int = config("SCRAPE_BATCH_SIZE", default=1000, cast=int)

    MINIO_ENDPOINT: str = config("MINIO_ENDPOINT", default="localhost:9001")
    MINIO_ACCESS_KEY: str = config("MINIO_ACCESS_KEY", default="lwd")
    MINIO_SECRET_KEY: str = config("MINIO_SECRET_KEY", default="lwd12345")
    MINIO_SECURE: bool = config("MINIO_SECURE", default=False, cast=bool)
    MINIO_USE_SSL: bool = False

    # gemini AI Service
    GEMINI_API_KEY: str = config("GEMINI_API_KEY", default="your-gemini-api-key")
    MODEL_NAME: str = "gemini-2.5-flash"

    # LLM Configuration
    LLM_API_KEY: str = config("LLM_API_KEY", default="your-llm-api-key")
    LLM_MODEL: str = config("LLM_MODEL", default="gemini-2.0-flash")
    LLM_API_URL: str = config("LLM_API_URL", default="")
    LLM_PROVIDER: str = config("LLM_PROVIDER", default="gemini")
    LLM_TEMPERATURE: float = config("LLM_TEMPERATURE", default=0.1, cast=float)
    LLM_MAX_TOKENS: int = config("LLM_MAX_TOKENS", default=1000, cast=int)
    LLM_SYSTEM_PROMPT: str = config(
        "LLM_SYSTEM_PROMPT", default="You are a data extraction specialist..."
    )

    MICROSOFT_REDIRECT_URI: str = config(
        "MICROSOFT_REDIRECT_URI", default="https://minamoto.emerj.net"
    )
    MICROSOFT_TENANT_ID: str = config("MICROSOFT_TENANT_ID", default="tenant-id")
    MICROSOFT_CLIENT_SECRET: str = config("MICROSOFT_CLIENT_SECRET", default="client-secret")
    MICROSOFT_CLIENT_ID: str = config("MICROSOFT_CLIENT_ID", default="client-id")
    MICROSOFT_USERINFO_ENDPOINT: str = config("MICROSOFT_USERINFO_ENDPOINT", default="user-info")

    MICROSOFT_SCOPES: list[str] = Field(
        default_factory=lambda: ["https://graph.microsoft.com/User.Read"]
    )

    MICROSOFT_OAUTH_REDIRECT_NEW_USER_URL: str = config(
        "MICROSOFT_OAUTH_REDIRECT_NEW_USER_URL", default="https://minamoto.emerj.net/dashboard"
    )
    MICROSOFT_OAUTH_REDIRECT_EXISTING_USER_URL: str = config(
        "MICROSOFT_OAUTH_REDIRECT_EXISTING_USER_URL", default="https://minamoto.emerj.net/dashboard"
    )
    MICROSOFT_OAUTH_STATE_TTL: int = config("MICROSOFT_OAUTH_STATE_TTL", default=900, cast=int)

    ADMIN_EMAIL: str = config("ADMIN_EMAIL", default="user@organization.com")

    APPLE_TEAM_ID: str = config("APPLE_TEAM_ID", default="your-apple-developer-team-id")
    APPLE_CLIENT_ID: str = config("APPLE_CLIENT_ID", default="your-apple-developer-client-id")
    APPLE_KEY_ID: str = config("APPLE_KEY_ID", default="your-apple-developer-key-identifier")
    APPLE_PRIVATE_KEY: str = config(
        "APPLE_PRIVATE_KEY", default="your-app-private-key-apple-developer"
    )
    APPLE_CLIENT_SECRET_LIFETIME: int = config(
        "APPLE_CLIENT_SECRET_LIFETIME", default=21600, cast=int
    )
    APPLE_REDIRECT_URI: str = config(
        "APPLE_REDIRECT_URI", default="http://localhost:8000/auth/apple/callback"
    )

    model_config = SettingsConfigDict(extra="allow")


settings = Settings()


# Lazy load encryption cipher suite to avoid import-time initialization
def get_cipher_suite():
    return Fernet(settings.ENCRYPTION_KEY)


# For backward compatibility, provide cipher_suite as a module-level variable
# This will be initialized on first access
cipher_suite = None

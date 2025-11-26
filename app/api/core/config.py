import os
from pathlib import Path

from cryptography.fernet import Fernet
from decouple import Config, RepositoryEnv
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

    # MinIO

    MINIO_ENDPOINT: str = config("MINIO_ENDPOINT", default="localhost:9000")
    MINIO_ACCESS_KEY: str = config("MINIO_ACCESS_KEY", default="minioadmin")
    MINIO_SECRET_KEY: str = config("MINIO_SECRET_KEY", default="minioadmin")
    MINIO_SECURE: bool = config("MINIO_SECURE", default=False, cast=bool)
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

    model_config = SettingsConfigDict(extra="allow")

    # Stripe API keys and product price IDs for billing
    STRIPE_SECRET_KEY: str = config("STRIPE_SECRET_KEY", default="sk_test_...")
    STRIPE_PUBLISHABLE_KEY: str = config("STRIPE_PUBLISHABLE_KEY", default="pk_test_...")
    STRIPE_WEBHOOK_SECRET: str = config("STRIPE_WEBHOOK_SECRET", default="whsec_...")
    STRIPE_MONTHLY_PRICE_ID: str = config("STRIPE_MONTHLY_PRICE_ID", default="prod_monthly_id")
    STRIPE_YEARLY_PRICE_ID: str = config("STRIPE_YEARLY_PRICE_ID", default="prod_yearly_id")

    
    # Billing Configuration
    TRIAL_DURATION_DAYS: int = 14
    BILLING_GRACE_PERIOD_DAYS: int = 3
    

    # Frontend URL (for Stripe redirects)
    @property
    def FRONTEND_URL(self) -> str:
        return os.getenv("FRONTEND_URL") or (self.DEV_URL if self.DEBUG else self.APP_URL)


    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="allow",
    )

settings = Settings()


# Lazy load encryption cipher suite to avoid import-time initialization
def get_cipher_suite():
    return Fernet(settings.ENCRYPTION_KEY)

# For backward compatibility, provide cipher_suite as a module-level variable
# This will be initialized on first access
cipher_suite = None
 
    
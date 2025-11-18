from pathlib import Path

from decouple import config
from pydantic_settings import BaseSettings

# Base directory for relative paths
BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):

    # App general
    DEBUG: bool = config("DEBUG", default=False, cast=bool)
    APP_NAME: str = config("APP_NAME", default="LEGAL WATCH DOG")
    APP_VERSION: str = config("APP_VERSION", default="1.0.0")
    ENVIRONMENT: str = config("ENVIRONMENT", default="dev")
    APP_PORT: int = config("APP_PORT", default=8000, cast=int)
    SECRET_KEY: str = config("SECRET_KEY", default="your-secret-key-for-sessions")
    LEGAL_WATCH_DOG_BASE_URL: str = config("LEGAL_WATCH_DOG_BASE_URL", default="backend.im")

    # Database
    DB_TYPE: str = config("DB_TYPE", default="postgresql")
    DB_HOST: str = config("DB_HOST", default="localhost")
    DB_PORT: int = config("DB_PORT", default=5432, cast=int)
    DB_USER: str = config("DB_USER", default="user")
    DB_PASS: str = config("DB_PASS", default="password")
    DB_NAME: str = config("DB_NAME", default="dbname")
    DATABASE_URL: str = config("DATABASE_URL", default="postgresql://user:password@localhost/dbname")

    # JWT Settings
    JWT_SECRET_KEY: str = config("JWT_SECRET_KEY", default=config("SECRET_KEY", default="your-secret-key-for-jwt"))
    JWT_ALGORITHM: str = config("JWT_ALGORITHM", default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = config("ACCESS_TOKEN_EXPIRE_MINUTES", default=60, cast=int)
    REFRESH_TOKEN_EXPIRE_DAYS: int = config("REFRESH_TOKEN_EXPIRE_DAYS", default=30, cast=int)

    # Cookie Settings for HttpOnly Cookies
    COOKIE_NAME_ACCESS: str = config("COOKIE_NAME_ACCESS", default="access_token")
    COOKIE_NAME_REFRESH: str = config("COOKIE_NAME_REFRESH", default="refresh_token")
    COOKIE_DOMAIN: str = config("COOKIE_DOMAIN", default=None)
    COOKIE_SECURE: bool = config("COOKIE_SECURE", default=True, cast=bool)  # Set to True in production (HTTPS only)
    COOKIE_SAMESITE: str = config("COOKIE_SAMESITE", default="lax")  # 'lax', 'strict', or 'none'

    @property
    def COOKIE_MAX_AGE_ACCESS(self) -> int:
        """Convert access token expiry to seconds for cookie max_age"""
        return self.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    @property
    def COOKIE_MAX_AGE_REFRESH(self) -> int:
        """Convert refresh token expiry to seconds for cookie max_age"""
        return self.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

    # Redis Settings
    REDIS_HOST: str = config("REDIS_HOST", default="localhost")
    REDIS_PORT: int = config("REDIS_PORT", default=6379, cast=int)
    REDIS_DB: int = config("REDIS_DB", default=0, cast=int)
    REDIS_PASSWORD: str = config("REDIS_PASSWORD", default="")
    REDIS_URL: str = config("REDIS_URL", default="")

    #Waitlist Email
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    EMAIL: str
    SMTP_SERVER: str 
    SMTP_PORT: int

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()

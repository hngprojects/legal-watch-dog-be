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

    #Waitlist Email
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    EMAIL: str
    SMTP_SERVER: str 
    SMTP_PORT: int

    ACCESS_TOKEN_EXPIRE_MINUTES: int = config("ACCESS_TOKEN_EXPIRE_MINUTES", default=60, cast=int)
    ALGORITHM: str = config("ALGORITHM", default="HS256")
    REFRESH_TOKEN_EXPIRE_DAYS: int = config("REFRESH_TOKEN_EXPIRE_DAYS", default=7, cast=int)

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()

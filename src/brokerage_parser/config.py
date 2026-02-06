from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # App & Security
    ENV: str = "development"
    API_KEY_SALT: str = Field(..., description="Salt for hashing API keys")
    MAX_FILE_SIZE: int = 20 * 1024 * 1024  # 20MB

    # Storage
    STORAGE_BACKEND: str = "s3"  # or local
    S3_BUCKET: str = "parsefin-data"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    AWS_ENDPOINT_URL: Optional[str] = None  # For MinIO

    # Database & Redis
    DATABASE_URL: str
    REDIS_URL: str

    # Database Pooling
    SQLALCHEMY_POOL_SIZE: int = 10
    SQLALCHEMY_MAX_OVERFLOW: int = 20
    SQLALCHEMY_POOL_TIMEOUT: int = 30
    SQLALCHEMY_POOL_RECYCLE: int = 3600

    # Celery & Resources
    CELERY_TASK_TIME_LIMIT: int = 300  # 5 mins
    CELERY_TASK_SOFT_TIME_LIMIT: int = 270 # 4.5 mins

    # LLM Configuration (Legacy/Existing)
    LLM_ENABLED: bool = False
    LLM_BASE_URL: str = "http://localhost:11434/v1"
    LLM_MODEL: str = "llama3"
    LLM_API_KEY: str = "ollama"

    # Logging
    LOG_LEVEL: str = "INFO"

    # Multi-Tenancy
    LEGACY_TENANT_ID: str = "00000000-0000-0000-0000-000000000001"
    LEGACY_ORG_ID: str = "00000000-0000-0000-0000-000000000000"
    ADMIN_API_KEYS: list[str] = []
    ENABLE_TENANT_ISOLATION: bool = True
    REQUIRE_AUDIT_REASON: bool = True
    AUDIT_LOG_RETENTION_DAYS: int = 2555 # 7 years

    model_config = {"env_file": ".env", "extra": "ignore"}

settings = Settings()

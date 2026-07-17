import os
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # App Settings
    app_name: str = "Anchor API"
    environment: str = os.getenv("ENVIRONMENT", "production")
    
    # SQLAlchemy Settings (for Auth/Merchants/Core models)
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///retention_core.db")
    
    @field_validator("database_url", mode="before")
    @classmethod
    def clean_db_url(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v
    pool_size: int = 5
    max_overflow: int = 10
    
    # Auth Settings
    secret_key: str = os.getenv("SECRET_KEY", "fallback-secret-key-for-dev")
    access_token_expire_minutes: int = 1440
    
    # Storage Paths
    data_root: str = "data"
    
    # LLM & Generation Settings
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")   
    # ML Models
    emotion_model_device: int = int(os.getenv("EMOTION_MODEL_DEVICE", "-1"))
    
    # Redis & Celery
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    model_config = SettingsConfigDict(env_file=".env.development", env_file_encoding="utf-8", extra="ignore")

settings = Settings()

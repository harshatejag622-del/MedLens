import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "MedLens Clinical Intelligence"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    # Security
    SECRET_KEY: str = "medlens_production_grade_secret_key_2026_clinical_intelligence"
    API_V1_STR: str = "/api"
    
    # Database
    DATABASE_URL: str = "sqlite:///./medlens.db"
    
    # Document Storage
    STORAGE_DIR: str = "./storage/documents"
    MAX_UPLOAD_SIZE_MB: int = 25
    ALLOWED_EXTENSIONS: list = ["pdf", "txt", "png", "jpg", "jpeg"]
    
    # AI Provider configuration: 'local' (deterministic NLP) or 'gemini'
    AI_PROVIDER: str = "local"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-1.5-flash"
    
    # Demo Mode (Disable to prevent automatic synthetic demo seeding in production)
    DEMO_MODE: bool = True
    
    # CORS Configuration
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"]

settings = Settings()

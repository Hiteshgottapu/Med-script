"""
MedScript Application Configuration
====================================
Environment-based configuration management for MedScript.
Supports Development, Testing, and Production configurations.
"""

import os
import secrets
from datetime import timedelta
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


class BaseConfig:
    """Base configuration common to all environments."""
    SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
    
    # Session Configuration
    SESSION_TYPE = "filesystem"
    SESSION_FILE_DIR = os.path.join(BASE_DIR, "flask_session")
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_USE_SIGNER = True
    
    # Supabase Configuration
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
    
    # Google AI / Gemini Configuration
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.7-flash")
    
    # Medical Diagnostic Credentials (Optional)
    INFERMEDICA_APP_ID = os.getenv("INFERMEDICA_APP_ID", "")
    INFERMEDICA_APP_KEY = os.getenv("INFERMEDICA_APP_KEY", "")
    
    # Twilio Notification Credentials (Optional)
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")
    
    # Email SMTP Credentials (Optional)
    EMAIL_USER = os.getenv("EMAIL_USER", "hiteshgottapu@gmail.com")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    
    # File Upload Paths
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    PRESCRIPTION_UPLOAD_DIR = os.path.join(UPLOAD_FOLDER, "prescriptions")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "pdf"}
    
    # Commerce & Cache Configuration
    COMMERCE_DB_PATH = os.path.join(BASE_DIR, "medscript_commerce.db")
    MEDICINE_CACHE_TTL = 3600  # 1 hour
    
    # Security Headers
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "SAMEORIGIN",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains"
    }


class DevelopmentConfig(BaseConfig):
    """Development environment configuration."""
    DEBUG = True
    TESTING = False
    LOG_LEVEL = "DEBUG"


class TestingConfig(BaseConfig):
    """Testing environment configuration with isolated test database."""
    DEBUG = False
    TESTING = True
    LOG_LEVEL = "INFO"
    SECRET_KEY = "test-secret-key-for-medscript"
    COMMERCE_DB_PATH = os.path.join(BASE_DIR, "test_medscript_commerce.db")
    SESSION_FILE_DIR = os.path.join(BASE_DIR, "test_flask_session")


class ProductionConfig(BaseConfig):
    """Production environment configuration with strict validations."""
    DEBUG = False
    TESTING = False
    LOG_LEVEL = "WARNING"
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig
}


def get_config(config_name=None):
    """Retrieve configuration class based on environment."""
    if not config_name:
        env = os.getenv("FLASK_ENV", "development").lower()
        return config_by_name.get(env, DevelopmentConfig)
    return config_by_name.get(config_name.lower(), DevelopmentConfig)

"""
Application configuration.
Loads secrets from environment variables with sensible development defaults.
"""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # --- Core Flask ---
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production-2026")
    
    # Handle DB URL for production (Postgres) and local (SQLite)
    _db_url = os.environ.get("DATABASE_URL")
    if _db_url and _db_url.startswith("postgres://"):
        # SQLAlchemy 1.4+ requires 'postgresql://' instead of 'postgres://' 
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
        
    SQLALCHEMY_DATABASE_URI = _db_url or f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'college_id.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- HMAC Token Signing ---
    HMAC_SECRET = os.environ.get("HMAC_SECRET", "hmac-secret-key-change-in-production")


    # --- File Uploads ---
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2 MB max upload
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

    # --- Cloudinary (persistent cloud photo storage) ---
    CLOUDINARY_URL = os.environ.get("CLOUDINARY_URL", "")

    # --- Flask-Mail (console backend for development) ---
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@itbhu.ac.in")
    # Set to True to suppress actual email sending and print to console
    MAIL_SUPPRESS_SEND = os.environ.get("MAIL_SUPPRESS_SEND", "true").lower() == "true"

    # --- Rate Limiting ---
    RATELIMIT_STORAGE_URI = "memory://"
    RATELIMIT_DEFAULT = "200 per day;50 per hour"

    # --- App Settings ---
    COLLEGE_NAME = "Indian Institute of Technology, Varanasi"
    COLLEGE_TAGLINE = "Excellence in Innovation"
    BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:5000")
    OTP_EXPIRY_MINUTES = 10
    ID_VALIDITY_YEARS = 1

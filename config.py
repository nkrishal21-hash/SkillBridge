"""
config.py — SkillBridge Application Configuration
All sensitive values are read from environment variables (see .env.example).
Never hard-code credentials in this file.
"""

import os
from dotenv import load_dotenv

# Load variables from .env file (development only; on Render, vars are set in dashboard)
load_dotenv()


class Config:
    """Base configuration shared by all environments."""

    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-fallback-key-change-in-prod")
    WTF_CSRF_ENABLED = True

    # ── Database ──────────────────────────────────────────────────────────────
    # Reads DATABASE_URL from .env.  Local dev: mysql+pymysql://root:@localhost/skillbridge
    # Aiven demo:  mysql+pymysql://avnadmin:PASSWORD@HOST:PORT/skillbridge?ssl_ca=...
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "mysql+pymysql://root:@localhost:3306/skillbridge"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 280,       # recycle connections before MySQL's 5-min timeout
        "pool_pre_ping": True,     # verify connection health before use
    }

    # ── Flask-Mail (Gmail SMTP) ───────────────────────────────────────────────
    MAIL_SERVER = "smtp.gmail.com"
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")   # Gmail App Password
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_USERNAME", "noreply@skillbridge.com")

    # ── Google OAuth (Authlib) ────────────────────────────────────────────────
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")

    # ── Cloudinary (all file uploads — avoids ephemeral Render disk) ──────────
    CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET")

    # ── eSewa Sandbox ─────────────────────────────────────────────────────────
    ESEWA_MERCHANT_CODE = os.environ.get("ESEWA_MERCHANT_CODE", "EPAYTEST")
    ESEWA_SECRET_KEY = os.environ.get("ESEWA_SECRET_KEY", "8gBm/:&EnhH.1/q")
    ESEWA_GATEWAY_URL = os.environ.get(
        "ESEWA_GATEWAY_URL",
        "https://rc-epay.esewa.com.np/api/epay/main/v2/form"
    )

    # ── Khalti Sandbox ────────────────────────────────────────────────────────
    KHALTI_SECRET_KEY = os.environ.get(
        "KHALTI_SECRET_KEY",
        "test_secret_key_dc74e0fd11ba4b25b72b774c21e2b57f"
    )
    KHALTI_PUBLIC_KEY = os.environ.get(
        "KHALTI_PUBLIC_KEY",
        "test_public_key_dc74e0fd11ba4b25b72b774c21e2b57f"
    )
    KHALTI_GATEWAY_URL = os.environ.get(
        "KHALTI_GATEWAY_URL",
        "https://a.khalti.com/api/v2/epayment/initiate/"
    )

    # ── Platform Commission ───────────────────────────────────────────────────
    # Percentage of each payment kept by the platform (default 20%).
    # Teachers receive the remaining 80%.  Override via PLATFORM_COMMISSION_PERCENT env var.
    PLATFORM_COMMISSION_PERCENT = int(os.environ.get("PLATFORM_COMMISSION_PERCENT", 20))

    # ── Flask-SocketIO ────────────────────────────────────────────────────────
    # async_mode='threading' is used so the app works on Render's free tier
    # where raw WebSockets are unreliable.  The JS client is configured to use
    # polling transport (see Phase 6 implementation).
    SOCKETIO_ASYNC_MODE = "threading"

    # ── File Upload Limits ────────────────────────────────────────────────────
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500 MB absolute cap (videos)
    ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif"}
    ALLOWED_VIDEO_EXTENSIONS = {"mp4"}
    ALLOWED_DOC_EXTENSIONS = {"pdf"}
    MAX_IMAGE_SIZE = 16 * 1024 * 1024       # 16 MB
    MAX_VIDEO_SIZE = 500 * 1024 * 1024      # 500 MB


class DevelopmentConfig(Config):
    """Local development — debug on, local MySQL."""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Render deployment — debug off, Aiven MySQL via env var."""
    DEBUG = False
    TESTING = False
    WTF_CSRF_SSL_STRICT = True


# Map name → class so app factory can select by FLASK_ENV
config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}

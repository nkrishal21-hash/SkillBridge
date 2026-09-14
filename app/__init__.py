"""
app/__init__.py — SkillBridge Application Factory
Creates and configures the Flask application, registers all extensions
and Blueprints, and exposes the SocketIO instance for run.py.
"""

import os
import cloudinary
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_mail import Mail
from flask_wtf import CSRFProtect
from flask_socketio import SocketIO
from authlib.integrations.flask_client import OAuth

from config import config_map

# ── Extension instances (created here, initialized in create_app) ─────────────
db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()
mail = Mail()
csrf = CSRFProtect()
socketio = SocketIO()
oauth = OAuth()


def create_app(config_name: str = None) -> Flask:
    """
    Application factory — call this to get a configured Flask app.
    config_name defaults to FLASK_ENV environment variable ('development').
    """
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # ── Load config ────────────────────────────────────────────────────────────
    env = config_name or os.environ.get("FLASK_ENV", "development")
    app.config.from_object(config_map.get(env, config_map["default"]))

    # ── Initialize extensions ──────────────────────────────────────────────────
    db.init_app(app)
    bcrypt.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    oauth.init_app(app)

    # Flask-Login setup
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"          # redirect unauthenticated users here
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    # Flask-SocketIO — threading mode for Render free-tier polling compatibility
    socketio.init_app(
        app,
        async_mode=app.config.get("SOCKETIO_ASYNC_MODE", "threading"),
        cors_allowed_origins="*",
        logger=False,
        engineio_logger=False,
    )

    # ── Cloudinary configuration ───────────────────────────────────────────────
    cloudinary.config(
        cloud_name=app.config.get("CLOUDINARY_CLOUD_NAME"),
        api_key=app.config.get("CLOUDINARY_API_KEY"),
        api_secret=app.config.get("CLOUDINARY_API_SECRET"),
        secure=True,
    )

    # ── Register Google OAuth provider ────────────────────────────────────────
    oauth.register(
        name="google",
        client_id=app.config.get("GOOGLE_CLIENT_ID"),
        client_secret=app.config.get("GOOGLE_CLIENT_SECRET"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

    # ── User loader for Flask-Login ────────────────────────────────────────────
    from app.models import User  # imported here to avoid circular imports

    @login_manager.user_loader
    def load_user(user_id: str):
        return User.query.get(int(user_id))

    # ── Register Blueprints ────────────────────────────────────────────────────
    from app.auth.routes import auth_bp
    from app.learner.routes import learner_bp
    from app.teacher.routes import teacher_bp
    from app.admin.routes import admin_bp
    from app.courses.routes import courses_bp
    from app.booking.routes import booking_bp
    from app.chat.routes import chat_bp
    from app.payments.routes import payments_bp
    from app.certificates.routes import certificates_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(learner_bp, url_prefix="/learner")
    app.register_blueprint(teacher_bp, url_prefix="/teacher")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(courses_bp, url_prefix="/courses")
    app.register_blueprint(booking_bp, url_prefix="/booking")
    app.register_blueprint(chat_bp, url_prefix="/chat")
    app.register_blueprint(payments_bp, url_prefix="/payments")
    app.register_blueprint(certificates_bp, url_prefix="/certificates")

    # ── Main / landing page route (placeholder until Phase 3 UI) ──────────────
    from flask import render_template

    @app.route("/")
    def index():
        return render_template("index.html")

    # ── Custom error pages ─────────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    return app

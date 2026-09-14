"""
app/auth/utils.py — Authentication Utilities & Access Control Decorators
Provides role-based access decorators, password reset token generation,
and email notification helpers.
"""

from functools import wraps
from flask import current_app, flash, redirect, url_for, request
from flask_login import current_user
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from app import mail
from app.models import User


# ─────────────────────────────────────────────────────────────────────────────
# Role-Based Route Protection Decorators
# ─────────────────────────────────────────────────────────────────────────────

def role_required(*roles):
    """
    Decorator requiring the logged-in user to have one of the specified roles.
    If unauthenticated, redirects to login.
    If authenticated with wrong role, flashes error and redirects to user's dashboard.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Please sign in to access this page.", "warning")
                return redirect(url_for("auth.login", next=request.url))

            if current_user.role not in roles:
                flash("You do not have permission to access that page.", "danger")
                # Redirect to appropriate role dashboard
                if current_user.role == "learner":
                    return redirect(url_for("learner.dashboard"))
                elif current_user.role == "teacher":
                    return redirect(url_for("teacher.dashboard"))
                elif current_user.role == "admin":
                    return redirect(url_for("admin.dashboard"))
                return redirect(url_for("index"))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def learner_required(f):
    """Decorator restricting route access to learners only."""
    return role_required("learner")(f)


def teacher_required(f):
    """Decorator restricting route access to teachers only."""
    return role_required("teacher")(f)


def admin_required(f):
    """Decorator restricting route access to administrators only."""
    return role_required("admin")(f)


# ─────────────────────────────────────────────────────────────────────────────
# Password Reset Token Helpers (itsdangerous)
# ─────────────────────────────────────────────────────────────────────────────

RESET_SALT = "skillbridge-password-reset-salt"


def get_serializer() -> URLSafeTimedSerializer:
    """Instantiate a timed serializer using app's secret key."""
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def generate_reset_token(user: User) -> str:
    """Generate a secure, time-sensitive URL-safe reset token for user."""
    s = get_serializer()
    return s.dumps({"user_id": user.id}, salt=RESET_SALT)


def verify_reset_token(token: str, max_age_seconds: int = 1800) -> User:
    """
    Verify the reset token. Returns User instance if valid, None if invalid/expired.
    Default expiry is 30 minutes (1800 seconds).
    """
    s = get_serializer()
    try:
        data = s.loads(token, salt=RESET_SALT, max_age=max_age_seconds)
        user_id = data.get("user_id")
        if not user_id:
            return None
        return User.query.get(user_id)
    except (SignatureExpired, BadSignature):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Password Reset Email Sender
# ─────────────────────────────────────────────────────────────────────────────

def send_password_reset_email(user: User, token: str) -> bool:
    """
    Send a password reset email via Flask-Mail.
    Returns True if sent successfully, False if SMTP fails or is unconfigured.
    In local dev mode, the link is always logged to the console so reset works without mail setup.
    """
    reset_url = url_for("auth.reset_password", token=token, _external=True)

    # Always log the reset URL in dev mode for easy local testing
    print(f"\n[SkillBridge Auth] Password Reset Link for {user.email}:")
    print(f"  {reset_url}\n")

    mail_user = current_app.config.get("MAIL_USERNAME")
    if not mail_user or "your-gmail" in str(mail_user):
        # SMTP not configured with real credentials; log and return
        return False

    try:
        msg = Message(
            subject="SkillBridge — Password Reset Request",
            sender=current_app.config.get("MAIL_DEFAULT_SENDER", mail_user),
            recipients=[user.email],
        )
        msg.html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 560px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 12px; background: #ffffff;">
            <div style="text-align: center; margin-bottom: 24px;">
                <h2 style="color: #4f46e5; margin: 0; font-size: 24px; font-weight: 700;">SkillBridge</h2>
                <p style="color: #64748b; font-size: 14px; margin-top: 4px;">Peer-to-Peer Learning Platform</p>
            </div>
            <p style="color: #1e293b; font-size: 16px;">Hello <strong>{user.full_name}</strong>,</p>
            <p style="color: #475569; font-size: 15px; line-height: 1.6;">
                We received a request to reset your SkillBridge account password. Click the button below to choose a new password. This link will expire in 30 minutes.
            </p>
            <div style="text-align: center; margin: 32px 0;">
                <a href="{reset_url}" style="background-color: #4f46e5; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 15px; display: inline-block;">
                    Reset Password
                </a>
            </div>
            <p style="color: #94a3b8; font-size: 13px; line-height: 1.5;">
                If you did not request a password reset, you can safely ignore this email. Your password will remain unchanged.
            </p>
            <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 24px 0;">
            <p style="color: #94a3b8; font-size: 12px; text-align: center;">
                SkillBridge &bull; Peer-to-Peer Learning &bull; Kathmandu, Nepal
            </p>
        </div>
        """
        mail.send(msg)
        return True
    except Exception as exc:
        print(f"[SkillBridge Auth] Could not send email via SMTP: {exc}")
        return False

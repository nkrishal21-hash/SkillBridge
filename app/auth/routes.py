"""
app/auth/routes.py — Authentication Blueprint Routes
Handles user registration, login/logout, Google OAuth, and password reset flows.
"""

from urllib.parse import urlparse
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    current_app,
)
from flask_login import login_user, logout_user, login_required, current_user
from app import db, oauth
from app.models import User, TeacherProfile
from app.auth.forms import (
    RegisterForm,
    LoginForm,
    ForgotPasswordForm,
    ResetPasswordForm,
)
from app.auth.utils import (
    generate_reset_token,
    verify_reset_token,
    send_password_reset_email,
)

auth_bp = Blueprint("auth", __name__)


def is_safe_redirect_url(target: str) -> bool:
    """Validate that the redirect target is local to prevent open-redirect vulnerabilities."""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(target)
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc or not test_url.netloc


def redirect_for_role(user: User):
    """Determine the default landing dashboard URL based on the user's role."""
    if user.role == "admin":
        return redirect(url_for("admin.dashboard"))
    elif user.role == "teacher":
        return redirect(url_for("teacher.dashboard"))
    return redirect(url_for("learner.dashboard"))


# ─────────────────────────────────────────────────────────────────────────────
# Register Route
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Learner and Teacher registration flow."""
    if current_user.is_authenticated:
        return redirect_for_role(current_user)

    form = RegisterForm()
    # Pre-select role if specified in query string e.g. /auth/register?role=teacher
    initial_role = request.args.get("role", "learner").lower()
    if request.method == "GET" and initial_role in ("learner", "teacher"):
        form.role.data = initial_role

    if form.validate_on_submit():
        role = form.role.data
        user = User(
            full_name=form.full_name.data.strip(),
            email=form.email.data.strip().lower(),
            role=role,
        )
        user.set_password(form.password.data)

        # If registered as teacher, build associated TeacherProfile
        if role == "teacher":
            teacher_profile = TeacherProfile(
                user=user,
                headline=form.headline.data.strip() if form.headline.data else None,
                skills=form.skills.data.strip() if form.skills.data else None,
                hourly_rate=form.hourly_rate.data if form.hourly_rate.data else None,
            )
            db.session.add(teacher_profile)

        db.session.add(user)
        db.session.commit()

        flash("Account created successfully! You can now sign in with your credentials.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


# ─────────────────────────────────────────────────────────────────────────────
# Login Route
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """User authentication with rate-limiting / lockout protection."""
    if current_user.is_authenticated:
        return redirect_for_role(current_user)

    form = LoginForm()

    if form.validate_on_submit():
        email_clean = form.email.data.strip().lower()
        user = User.query.filter(User.email.ilike(email_clean)).first()

        if user:
            # Check if account is locked
            if user.is_locked:
                minutes_remaining = 15
                if user.locked_until:
                    from datetime import datetime
                    diff = user.locked_until - datetime.utcnow()
                    minutes_remaining = max(1, int(diff.total_seconds() / 60) + 1)
                flash(
                    f"This account is temporarily locked due to too many failed attempts. "
                    f"Please try again in {minutes_remaining} minutes or reset your password.",
                    "danger",
                )
                return render_template("auth/login.html", form=form)

            # Check password
            if user.check_password(form.password.data):
                if not user.is_active:
                    flash("Your account has been deactivated. Please contact support.", "danger")
                    return render_template("auth/login.html", form=form)

                user.reset_failed_login()
                db.session.commit()

                login_user(user, remember=form.remember_me.data)
                flash(f"Welcome back, {user.full_name}!", "success")

                next_url = request.args.get("next")
                if next_url and is_safe_redirect_url(next_url):
                    return redirect(next_url)

                return redirect_for_role(user)
            else:
                # Increment failed attempts
                is_now_locked = user.increment_failed_login(max_attempts=5, lock_minutes=15)
                db.session.commit()

                if is_now_locked:
                    flash(
                        "Too many incorrect attempts. Your account has been temporarily locked for 15 minutes.",
                        "danger",
                    )
                else:
                    remaining = max(0, 5 - (user.failed_login_attempts or 0))
                    flash(
                        f"Invalid email or password. {remaining} attempt(s) remaining before temporary lockout.",
                        "danger",
                    )
        else:
            flash("Invalid email or password.", "danger")

    return render_template("auth/login.html", form=form)


# ─────────────────────────────────────────────────────────────────────────────
# Logout Route
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route("/logout")
@login_required
def logout():
    """End current session."""
    logout_user()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for("index"))


# ─────────────────────────────────────────────────────────────────────────────
# Google OAuth Routes
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route("/google")
def google_login():
    """Initiate Google OAuth 2.0 authorization redirect."""
    client_id = current_app.config.get("GOOGLE_CLIENT_ID")
    if not client_id or "your-google" in str(client_id):
        flash(
            "Google Sign-In is not configured yet. Please sign in using your email and password.",
            "warning",
        )
        return redirect(url_for("auth.login"))

    redirect_uri = url_for("auth.google_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route("/google/callback")
def google_callback():
    """Process Google OAuth callback, create or link user account."""
    client_id = current_app.config.get("GOOGLE_CLIENT_ID")
    if not client_id or "your-google" in str(client_id):
        flash("Google Sign-In is not configured.", "warning")
        return redirect(url_for("auth.login"))

    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get("userinfo") or oauth.google.userinfo()
    except Exception as exc:
        current_app.logger.warning(f"Google OAuth error: {exc}")
        flash("Failed to sign in with Google. Please try again or use your password.", "danger")
        return redirect(url_for("auth.login"))

    if not user_info or not user_info.get("email"):
        flash("Could not retrieve your profile information from Google.", "danger")
        return redirect(url_for("auth.login"))

    google_id = str(user_info.get("sub"))
    email = user_info.get("email").strip().lower()
    name = user_info.get("name") or email.split("@")[0]
    picture = user_info.get("picture")

    # Check if user already exists
    user = User.query.filter((User.google_id == google_id) | (User.email == email)).first()

    if user:
        if not user.google_id:
            user.google_id = google_id
        if picture and not user.profile_photo:
            user.profile_photo = picture
        user.is_email_verified = True
        db.session.commit()
    else:
        # Create new learner account via Google OAuth
        user = User(
            full_name=name,
            email=email,
            role="learner",
            google_id=google_id,
            profile_photo=picture,
            is_email_verified=True,
        )
        db.session.add(user)
        db.session.commit()

    login_user(user, remember=True)
    flash(f"Welcome, {user.full_name}! Signed in via Google.", "success")
    return redirect_for_role(user)


# ─────────────────────────────────────────────────────────────────────────────
# Password Reset Routes
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Request a password reset link."""
    if current_user.is_authenticated:
        return redirect_for_role(current_user)

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        email_clean = form.email.data.strip().lower()
        user = User.query.filter(User.email.ilike(email_clean)).first()

        if user:
            token = generate_reset_token(user)
            sent = send_password_reset_email(user, token)
            if not sent:
                # SMTP not set up in local dev — flash direct helper link for convenience
                reset_url = url_for("auth.reset_password", token=token)
                flash(
                    f"[Dev Mode] Password reset link generated! "
                    f"Since mail server is not configured, click here to reset: {reset_url}",
                    "info",
                )
            else:
                flash(
                    "If an account with that email exists, a password reset link has been sent.",
                    "info",
                )
        else:
            # Generic message to prevent account enumeration
            flash(
                "If an account with that email exists, a password reset link has been sent.",
                "info",
            )

        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    """Set a new password using a validated reset token."""
    if current_user.is_authenticated:
        return redirect_for_role(current_user)

    user = verify_reset_token(token)
    if not user:
        flash("The password reset link is invalid or has expired (valid for 30 minutes).", "danger")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        user.reset_failed_login()
        db.session.commit()

        flash("Your password has been reset successfully! You can now sign in with your new password.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form)

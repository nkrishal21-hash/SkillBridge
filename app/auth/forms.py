"""
app/auth/forms.py — Authentication Forms
WTForms-based form classes with input validation and CSRF protection.
"""

from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    BooleanField,
    SelectField,
    DecimalField,
    TextAreaField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    EqualTo,
    ValidationError,
    Optional,
    NumberRange,
)
from app.models import User


class RegisterForm(FlaskForm):
    """
    User registration form supporting both Learner and Teacher account creation.
    Role-specific fields (e.g. skills, hourly rate) are conditionally filled for teachers.
    """
    full_name = StringField(
        "Full Name",
        validators=[
            DataRequired(message="Full name is required."),
            Length(min=2, max=120, message="Name must be between 2 and 120 characters."),
        ],
        render_kw={"placeholder": "e.g. Alex Sharma"},
    )
    email = StringField(
        "Email Address",
        validators=[
            DataRequired(message="Email address is required."),
            Email(message="Please enter a valid email address."),
            Length(max=150),
        ],
        render_kw={"placeholder": "alex@example.com"},
    )
    role = SelectField(
        "I want to join as",
        choices=[("learner", "Learner (I want to learn skills)"), ("teacher", "Teacher / Mentor (I want to teach)")],
        default="learner",
        validators=[DataRequired()],
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password is required."),
            Length(min=6, message="Password must be at least 6 characters."),
        ],
        render_kw={"placeholder": "At least 6 characters"},
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(message="Please confirm your password."),
            EqualTo("password", message="Passwords must match."),
        ],
        render_kw={"placeholder": "Re-enter your password"},
    )

    # Initial optional teacher profile fields
    headline = StringField(
        "Professional Headline",
        validators=[Optional(), Length(max=200)],
        render_kw={"placeholder": "e.g. Senior Python & Machine Learning Engineer"},
    )
    skills = StringField(
        "Top Skills (comma-separated)",
        validators=[Optional(), Length(max=300)],
        render_kw={"placeholder": "e.g. Python, Flask, Data Science, SQL"},
    )
    hourly_rate = DecimalField(
        "Hourly Rate (NPR)",
        places=2,
        validators=[Optional(), NumberRange(min=0, message="Rate cannot be negative.")],
        render_kw={"placeholder": "e.g. 800"},
    )

    submit = SubmitField("Create Account")

    def validate_email(self, field):
        """Ensure email is uniquely registered in database."""
        email_clean = field.data.strip().lower()
        if User.query.filter(User.email.ilike(email_clean)).first():
            raise ValidationError("An account with this email address already exists. Please log in.")


class LoginForm(FlaskForm):
    """Standard email/password login form."""
    email = StringField(
        "Email Address",
        validators=[
            DataRequired(message="Email address is required."),
            Email(message="Please enter a valid email address."),
        ],
        render_kw={"placeholder": "you@example.com", "autocomplete": "email"},
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(message="Password is required.")],
        render_kw={"placeholder": "Your account password", "autocomplete": "current-password"},
    )
    remember_me = BooleanField("Remember me for 30 days")
    submit = SubmitField("Sign In")


class ForgotPasswordForm(FlaskForm):
    """Form to initiate password reset via token link."""
    email = StringField(
        "Your Account Email",
        validators=[
            DataRequired(message="Email address is required."),
            Email(message="Please enter a valid email address."),
        ],
        render_kw={"placeholder": "you@example.com"},
    )
    submit = SubmitField("Send Reset Link")


class ResetPasswordForm(FlaskForm):
    """Form to set a new password given a verified reset token."""
    password = PasswordField(
        "New Password",
        validators=[
            DataRequired(message="New password is required."),
            Length(min=6, message="Password must be at least 6 characters."),
        ],
        render_kw={"placeholder": "At least 6 characters"},
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[
            DataRequired(message="Please confirm your new password."),
            EqualTo("password", message="Passwords must match."),
        ],
        render_kw={"placeholder": "Re-enter new password"},
    )
    submit = SubmitField("Update Password")

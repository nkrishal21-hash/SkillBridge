"""
app/teacher/routes.py — Teacher Blueprint Routes
Provides teacher dashboard, course creation, profile management, and sessions.
"""

from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.auth.utils import teacher_required

teacher_bp = Blueprint("teacher", __name__)


@teacher_bp.route("/dashboard")
@login_required
@teacher_required
def dashboard():
    """Teacher dashboard showing courses, booking requests, and earnings."""
    profile = current_user.teacher_profile
    return render_template("teacher/dashboard.html", user=current_user, profile=profile)

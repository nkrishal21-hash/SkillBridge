"""
app/learner/routes.py — Learner Blueprint Routes
Provides dashboard and learner-specific features.
"""

from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.auth.utils import learner_required

learner_bp = Blueprint("learner", __name__)


@learner_bp.route("/dashboard")
@login_required
@learner_required
def dashboard():
    """Learner dashboard showing enrolled courses, upcoming bookings, and certificates."""
    return render_template("learner/dashboard.html", user=current_user)

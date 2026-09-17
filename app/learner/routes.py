"""
app/learner/routes.py — Learner Blueprint Routes
Provides dashboard and learner-specific features.
"""

from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.auth.utils import learner_required
from app.models import Booking

learner_bp = Blueprint("learner", __name__)


@learner_bp.route("/dashboard")
@login_required
@learner_required
def dashboard():
    """Learner dashboard showing enrolled courses, upcoming bookings, and certificates."""
    upcoming_bookings = (
        current_user.bookings_as_learner
        .filter(Booking.status.in_(["pending", "approved"]))
        .order_by(Booking.session_date.asc(), Booking.start_time.asc())
        .limit(5)
        .all()
    )
    return render_template(
        "learner/dashboard.html",
        user=current_user,
        upcoming_bookings=upcoming_bookings,
    )

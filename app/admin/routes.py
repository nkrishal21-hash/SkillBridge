"""
app/admin/routes.py — Admin Blueprint Routes
Provides platform overview, user management, and teacher verification.
"""

from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.auth.utils import admin_required
from app.models import User, Course, Booking, Payment

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/dashboard")
@login_required
@admin_required
def dashboard():
    """Admin dashboard with high-level platform statistics."""
    stats = {
        "total_users": User.query.count(),
        "total_courses": Course.query.count(),
        "total_bookings": Booking.query.count(),
        "total_payments": Payment.query.count(),
    }
    return render_template("admin/dashboard.html", user=current_user, stats=stats)

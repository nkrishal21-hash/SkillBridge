"""
app/learner/routes.py — Learner Blueprint Routes
Provides learner dashboard, mentorship bookings, certificates earned,
recent notifications, and mentor favorites management.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from app import db
from app.auth.utils import learner_required
from app.models import Booking, TeacherProfile, Favorite, Certificate, Notification

learner_bp = Blueprint("learner", __name__)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Learner Dashboard Hub
# ─────────────────────────────────────────────────────────────────────────────
@learner_bp.route("/dashboard")
@login_required
@learner_required
def dashboard():
    """
    Comprehensive learner portal showing enrolled courses with progress bars,
    upcoming mentorship sessions, earned certificates, recent notifications,
    and favorited mentors.
    """
    upcoming_bookings = (
        current_user.bookings_as_learner
        .filter(Booking.status.in_(["pending", "approved"]))
        .order_by(Booking.session_date.asc(), Booking.start_time.asc())
        .limit(5)
        .all()
    )

    certificates = (
        current_user.certificates
        .order_by(Certificate.issued_at.desc())
        .all()
    )

    recent_notifications = (
        current_user.notifications
        .order_by(Notification.created_at.desc())
        .limit(5)
        .all()
    )

    favorites = (
        current_user.favorites
        .order_by(Favorite.saved_at.desc())
        .all()
    )

    return render_template(
        "learner/dashboard.html",
        user=current_user,
        upcoming_bookings=upcoming_bookings,
        certificates=certificates,
        recent_notifications=recent_notifications,
        favorites=favorites,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Toggle Favorite Mentor (Save / Unsave)
# ─────────────────────────────────────────────────────────────────────────────
@learner_bp.route("/favorites/<int:teacher_profile_id>/toggle", methods=["POST"])
@login_required
@learner_required
def toggle_favorite(teacher_profile_id: int):
    """
    Toggle saving/unfavoriting a teacher profile for the current learner.
    Catches IntegrityError gracefully to prevent 500s.
    """
    profile = TeacherProfile.query.get_or_404(teacher_profile_id)

    # Disallow favoriting yourself
    if profile.user_id == current_user.id:
        flash("You cannot add yourself to your favorites.", "warning")
        return redirect(request.referrer or url_for("teacher.public_profile", teacher_id=profile.id))

    fav = Favorite.query.filter_by(
        learner_id=current_user.id,
        teacher_id=profile.id
    ).first()

    teacher_name = profile.user.full_name if profile.user else "Mentor"

    if fav:
        db.session.delete(fav)
        db.session.commit()
        flash(f"Removed {teacher_name} from your saved mentors.", "info")
    else:
        new_fav = Favorite(learner_id=current_user.id, teacher_id=profile.id)
        try:
            db.session.add(new_fav)
            db.session.commit()
            flash(f"Added {teacher_name} to your saved favorites! ❤️", "success")
        except IntegrityError:
            db.session.rollback()
            flash(f"{teacher_name} is already in your saved favorites.", "info")

    return redirect(request.referrer or url_for("teacher.public_profile", teacher_id=profile.id))

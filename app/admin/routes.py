"""
app/admin/routes.py — Admin Blueprint Routes
Full platform administration: statistics, teacher verification queue,
course approval queue, payment audit, and user listing.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from sqlalchemy import func

from app import db
from app.auth.utils import admin_required
from app.models import (
    User, TeacherProfile, Course, Booking, Payment,
    Certificate, Notification,
)
from app.notifications.utils import notify

admin_bp = Blueprint("admin", __name__)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Admin Dashboard — Overview
# ─────────────────────────────────────────────────────────────────────────────
@admin_bp.route("/dashboard")
@login_required
@admin_required
def dashboard():
    """Admin dashboard with high-level platform statistics and queue summaries."""
    stats = {
        "total_users": User.query.count(),
        "total_teachers": User.query.filter_by(role="teacher").count(),
        "total_learners": User.query.filter_by(role="learner").count(),
        "total_courses": Course.query.count(),
        "published_courses": Course.query.filter_by(is_published=True).count(),
        "total_bookings": Booking.query.count(),
        "total_payments": Payment.query.count(),
        "total_certificates": Certificate.query.count(),
    }

    # Queue pending counts
    pending_teachers = TeacherProfile.query.filter_by(is_verified=False).filter(
        TeacherProfile.headline.isnot(None),
        TeacherProfile.skills.isnot(None),
        TeacherProfile.hourly_rate.isnot(None),
    ).count()

    pending_courses = Course.query.filter_by(is_published=True, is_approved=False).count()

    # Revenue snapshot
    total_revenue = db.session.query(
        func.coalesce(func.sum(Payment.amount), 0.0)
    ).filter_by(status="success").scalar() or 0.0

    recent_payments = (
        Payment.query
        .filter_by(status="success")
        .order_by(Payment.completed_at.desc(), Payment.id.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "admin/dashboard.html",
        user=current_user,
        stats=stats,
        pending_teachers=pending_teachers,
        pending_courses=pending_courses,
        total_revenue=float(total_revenue),
        recent_payments=recent_payments,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Teacher Verification Queue
# ─────────────────────────────────────────────────────────────────────────────
@admin_bp.route("/teachers")
@login_required
@admin_required
def teacher_list():
    """List all teacher profiles for verification management."""
    filter_status = request.args.get("filter", "pending").strip().lower()

    if filter_status == "verified":
        profiles = TeacherProfile.query.filter_by(is_verified=True).order_by(
            TeacherProfile.verified_at.desc()
        ).all()
    else:
        # Show profiles that have enough info to be reviewed
        profiles = TeacherProfile.query.filter_by(is_verified=False).order_by(
            TeacherProfile.created_at.desc()
        ).all()

    return render_template(
        "admin/teachers.html",
        user=current_user,
        profiles=profiles,
        filter_status=filter_status,
    )


@admin_bp.route("/teachers/<int:profile_id>/verify", methods=["POST"])
@login_required
@admin_required
def verify_teacher(profile_id: int):
    """Grant verified status to a teacher profile."""
    from datetime import datetime

    profile = TeacherProfile.query.get_or_404(profile_id)

    if profile.is_verified:
        flash(f"{profile.user.full_name} is already verified.", "info")
        return redirect(url_for("admin.teacher_list"))

    profile.is_verified = True
    profile.verified_at = datetime.utcnow()
    db.session.commit()

    # Notify the teacher
    notify(
        user_id=profile.user_id,
        title="🎉 Your Instructor Profile Is Now Verified!",
        body=(
            "Congratulations! SkillBridge has verified your instructor profile. "
            "You now appear in learner search results with the ✓ Verified badge."
        ),
        notif_type="admin",
        link=url_for("teacher.dashboard"),
    )

    flash(f"✅ {profile.user.full_name}'s profile has been verified.", "success")
    return redirect(url_for("admin.teacher_list"))


@admin_bp.route("/teachers/<int:profile_id>/unverify", methods=["POST"])
@login_required
@admin_required
def unverify_teacher(profile_id: int):
    """Revoke verified status from a teacher profile."""
    profile = TeacherProfile.query.get_or_404(profile_id)

    if not profile.is_verified:
        flash(f"{profile.user.full_name} is not currently verified.", "info")
        return redirect(url_for("admin.teacher_list", filter="verified"))

    profile.is_verified = False
    profile.verified_at = None
    db.session.commit()

    flash(f"⚠️ Verification revoked for {profile.user.full_name}.", "warning")
    return redirect(url_for("admin.teacher_list", filter="verified"))


# ─────────────────────────────────────────────────────────────────────────────
# 3. Course Approval Queue
# ─────────────────────────────────────────────────────────────────────────────
@admin_bp.route("/courses")
@login_required
@admin_required
def course_list():
    """List all submitted (published) courses awaiting admin approval."""
    filter_status = request.args.get("filter", "pending").strip().lower()

    if filter_status == "approved":
        courses = Course.query.filter_by(is_published=True, is_approved=True).order_by(
            Course.approved_at.desc()
        ).all()
    elif filter_status == "all":
        courses = Course.query.order_by(Course.created_at.desc()).all()
    else:
        # pending: published but not approved
        courses = Course.query.filter_by(is_published=True, is_approved=False).order_by(
            Course.created_at.desc()
        ).all()

    return render_template(
        "admin/courses.html",
        user=current_user,
        courses=courses,
        filter_status=filter_status,
    )


@admin_bp.route("/courses/<int:course_id>/approve", methods=["POST"])
@login_required
@admin_required
def approve_course(course_id: int):
    """Approve a published course for the public catalog."""
    from datetime import datetime

    course = Course.query.get_or_404(course_id)

    if course.is_approved:
        flash(f"'{course.title}' is already approved.", "info")
        return redirect(url_for("admin.course_list"))

    course.is_approved = True
    course.approved_at = datetime.utcnow()
    db.session.commit()

    # Notify the course's teacher
    if course.teacher and course.teacher.user_id:
        notify(
            user_id=course.teacher.user_id,
            title=f"✅ Your course '{course.title}' has been approved!",
            body="Your course passed admin review and is now officially listed in the SkillBridge catalog.",
            notif_type="course",
            link=url_for("courses.course_detail", course_id=course.id),
        )

    flash(f"✅ Course '{course.title}' has been approved and is now listed.", "success")
    return redirect(url_for("admin.course_list"))


@admin_bp.route("/courses/<int:course_id>/unapprove", methods=["POST"])
@login_required
@admin_required
def unapprove_course(course_id: int):
    """Remove approval from a course (e.g. for policy violation)."""
    course = Course.query.get_or_404(course_id)

    if not course.is_approved:
        flash(f"'{course.title}' is not currently approved.", "info")
        return redirect(url_for("admin.course_list", filter="approved"))

    course.is_approved = False
    course.approved_at = None
    db.session.commit()

    flash(f"⚠️ Approval revoked for course '{course.title}'.", "warning")
    return redirect(url_for("admin.course_list", filter="approved"))


# ─────────────────────────────────────────────────────────────────────────────
# 4. Payment Audit Log
# ─────────────────────────────────────────────────────────────────────────────
@admin_bp.route("/payments")
@login_required
@admin_required
def payment_list():
    """Paginated audit log of all platform payment records."""
    page = request.args.get("page", 1, type=int)
    filter_status = request.args.get("filter", "all").strip().lower()

    query = Payment.query

    if filter_status in ("success", "initiated", "failed", "refunded"):
        query = query.filter_by(status=filter_status)

    pagination = query.order_by(
        Payment.initiated_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)

    # Revenue totals
    revenue_total = db.session.query(
        func.coalesce(func.sum(Payment.amount), 0.0)
    ).filter_by(status="success").scalar() or 0.0

    return render_template(
        "admin/payments.html",
        user=current_user,
        pagination=pagination,
        payments=pagination.items,
        filter_status=filter_status,
        revenue_total=float(revenue_total),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. User Listing
# ─────────────────────────────────────────────────────────────────────────────
@admin_bp.route("/users")
@login_required
@admin_required
def user_list():
    """List all registered platform users with role and status."""
    page = request.args.get("page", 1, type=int)
    role_filter = request.args.get("role", "all").strip().lower()

    query = User.query

    if role_filter in ("learner", "teacher", "admin"):
        query = query.filter_by(role=role_filter)

    pagination = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    return render_template(
        "admin/users.html",
        user=current_user,
        pagination=pagination,
        users=pagination.items,
        role_filter=role_filter,
    )

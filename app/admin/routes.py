"""
app/admin/routes.py — Admin Blueprint Routes
Full platform administration: statistics, teacher verification queue,
course approval queue, payment audit, and user listing.
"""

from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from sqlalchemy import func

from app import db
from app.auth.utils import admin_required
from app.models import (
    User, TeacherProfile, Course, Booking, Payment,
    Certificate, Notification, Report,
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
    pending_reports = Report.query.filter_by(status="pending").count()

    # Revenue snapshot
    total_revenue = db.session.query(
        func.coalesce(func.sum(Payment.amount), 0.0)
    ).filter_by(status="success").scalar() or 0.0

    # Pending payouts snapshot
    total_pending_payouts = db.session.query(
        func.coalesce(func.sum(Payment.teacher_payout_amount), 0.0)
    ).filter(
        Payment.status == "success",
        Payment.payout_status == "pending",
    ).scalar() or 0.0

    pending_payout_count = Payment.query.filter(
        Payment.status == "success",
        Payment.payout_status == "pending",
    ).count()

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
        pending_reports=pending_reports,
        total_revenue=float(total_revenue),
        total_pending_payouts=float(total_pending_payouts),
        pending_payout_count=pending_payout_count,
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


@admin_bp.route("/users/<int:user_id>/ban", methods=["POST"])
@login_required
@admin_required
def ban_user(user_id: int):
    """Suspend a user account, preventing login and hiding them from search."""
    user = User.query.get_or_404(user_id)

    if user.role == "admin":
        flash("You cannot suspend an administrator account.", "danger")
        return redirect(request.referrer or url_for("admin.user_list"))

    if not user.is_active:
        flash(f"User '{user.full_name}' is already suspended.", "info")
        return redirect(request.referrer or url_for("admin.user_list"))

    user.is_active = False
    db.session.commit()

    flash(f"🚫 User '{user.full_name}' has been banned and suspended.", "warning")
    return redirect(request.referrer or url_for("admin.user_list"))


@admin_bp.route("/users/<int:user_id>/unban", methods=["POST"])
@login_required
@admin_required
def unban_user(user_id: int):
    """Restore a suspended user account."""
    user = User.query.get_or_404(user_id)

    if user.is_active:
        flash(f"User '{user.full_name}' is already active.", "info")
        return redirect(request.referrer or url_for("admin.user_list"))

    user.is_active = True
    db.session.commit()

    flash(f"✅ User '{user.full_name}' has been unbanned and restored.", "success")
    return redirect(request.referrer or url_for("admin.user_list"))


# ─────────────────────────────────────────────────────────────────────────────
# 6. Incident Reports Queue & Moderation
# ─────────────────────────────────────────────────────────────────────────────
@admin_bp.route("/reports")
@login_required
@admin_required
def report_list():
    """Paginated queue of incident reports with status filtering."""
    page = request.args.get("page", 1, type=int)
    filter_status = request.args.get("filter", "pending").strip().lower()

    query = Report.query

    if filter_status in ("pending", "reviewed", "resolved", "dismissed"):
        query = query.filter_by(status=filter_status)

    pagination = query.order_by(Report.created_at.desc()).paginate(
        page=page, per_page=15, error_out=False
    )

    # Queue counts
    pending_count = Report.query.filter_by(status="pending").count()
    reviewed_count = Report.query.filter_by(status="reviewed").count()
    resolved_count = Report.query.filter_by(status="resolved").count()
    dismissed_count = Report.query.filter_by(status="dismissed").count()
    total_count = Report.query.count()

    # Pre-fetch associated payments for refund eligibility checking
    report_items = pagination.items
    booking_ids = [r.booking_id for r in report_items if r.booking_id]
    eligible_payments = {}
    if booking_ids:
        payments = Payment.query.filter(
            Payment.payment_for == "booking",
            Payment.booking_id_ref.in_(booking_ids),
            Payment.status == "success",
        ).all()
        for p in payments:
            eligible_payments[p.booking_id_ref] = p

    return render_template(
        "admin/reports.html",
        user=current_user,
        pagination=pagination,
        reports=report_items,
        filter_status=filter_status,
        pending_count=pending_count,
        reviewed_count=reviewed_count,
        resolved_count=resolved_count,
        dismissed_count=dismissed_count,
        total_count=total_count,
        eligible_payments=eligible_payments,
    )


@admin_bp.route("/reports/<int:report_id>/dismiss", methods=["POST"])
@login_required
@admin_required
def dismiss_report(report_id: int):
    """Dismiss an incident report with optional administrative notes."""
    report = Report.query.get_or_404(report_id)
    admin_notes = request.form.get("admin_notes", "").strip()

    report.status = "dismissed"
    report.resolved_at = datetime.utcnow()
    if admin_notes:
        report.admin_notes = f"{report.admin_notes}\n{admin_notes}" if report.admin_notes else admin_notes

    db.session.commit()
    flash(f"Report #{report.id} has been dismissed.", "info")
    return redirect(request.referrer or url_for("admin.report_list", filter="dismissed"))


@admin_bp.route("/reports/<int:report_id>/resolve", methods=["POST"])
@login_required
@admin_required
def resolve_report(report_id: int):
    """Mark an incident report as resolved with optional notes."""
    report = Report.query.get_or_404(report_id)
    admin_notes = request.form.get("admin_notes", "").strip()

    report.status = "resolved"
    report.resolved_at = datetime.utcnow()
    if admin_notes:
        report.admin_notes = f"{report.admin_notes}\n{admin_notes}" if report.admin_notes else admin_notes

    db.session.commit()
    flash(f"✅ Report #{report.id} has been marked as resolved.", "success")
    return redirect(request.referrer or url_for("admin.report_list", filter="resolved"))


@admin_bp.route("/reports/<int:report_id>/refund", methods=["POST"])
@login_required
@admin_required
def refund_report(report_id: int):
    """
    Issue an internal booking refund for a report.
    Flips Payment status to 'refunded', updates Report to 'resolved', and notifies learner.
    If the teacher payout was already released, a prominent warning is shown requiring
    offline reconciliation.
    """
    report = Report.query.get_or_404(report_id)

    if not report.booking_id:
        flash("This report is not tied to a booking.", "warning")
        return redirect(request.referrer or url_for("admin.report_list"))

    payment = Payment.query.filter_by(
        payment_for="booking",
        booking_id_ref=report.booking_id,
        status="success",
    ).first()

    if not payment:
        flash("Nothing to refund for this booking. No successful payment found.", "warning")
        return redirect(request.referrer or url_for("admin.report_list"))

    # ── Payout conflict guard ─────────────────────────────────────────────────
    if payment.payout_status == "released":
        flash(
            f"⚠️ WARNING: Teacher payout for Payment #{payment.id} (NPR {payment.teacher_payout_amount}) "
            f"was already released on {payment.payout_released_at.strftime('%Y-%m-%d') if payment.payout_released_at else 'unknown date'}. "
            f"The internal refund has been recorded, but the teacher's payout was already disbursed manually. "
            f"Offline reconciliation with the teacher is required.",
            "warning"
        )

    payment.status = "refunded"
    report.status = "resolved"
    report.resolved_at = datetime.utcnow()
    payout_note = (
        f" (Payout already released — offline reconciliation required.)"
        if payment.payout_status == "released" else ""
    )
    refund_note = f"Refund issued internally for Payment #{payment.id} (NPR {payment.amount}).{payout_note}"
    report.admin_notes = f"{report.admin_notes}\n{refund_note}" if report.admin_notes else refund_note
    db.session.commit()

    # Notify learner
    notify(
        user_id=payment.learner_id,
        title=f"💳 Mentorship Booking Refund (NPR {payment.amount})",
        body=f"Your booking #{report.booking_id} session payment has been marked as refunded following administrative review.",
        notif_type="payment",
        link=url_for("booking.detail", booking_id=report.booking_id),
    )

    flash(f"✅ Payment #{payment.id} (NPR {payment.amount}) marked as refunded. Report #{report.id} marked as resolved.", "success")
    return redirect(request.referrer or url_for("admin.report_list", filter="resolved"))


# ─────────────────────────────────────────────────────────────────────────────
# 10. Payout Management
# ─────────────────────────────────────────────────────────────────────────────
@admin_bp.route("/payouts")
@login_required
@admin_required
def payout_list():
    """Admin payout management queue — lists teacher payouts with filter tabs."""
    filter_status = request.args.get("filter", "pending").strip().lower()

    base_q = Payment.query.filter(Payment.status == "success")

    if filter_status == "pending":
        payments = base_q.filter(Payment.payout_status == "pending").order_by(Payment.completed_at.desc()).all()
    elif filter_status == "released":
        payments = base_q.filter(Payment.payout_status == "released").order_by(Payment.payout_released_at.desc()).all()
    else:  # 'all'
        payments = base_q.order_by(Payment.completed_at.desc()).all()

    # Per-teacher subtotals for pending payouts
    teacher_subtotals_raw = db.session.query(
        Payment.teacher_payout_amount,
        Payment.payment_for,
        Payment.course_id,
        Payment.booking_id_ref,
    ).filter(
        Payment.status == "success",
        Payment.payout_status == "pending",
    ).all()

    # Overall summary stats
    total_pending_payout = db.session.query(
        func.coalesce(func.sum(Payment.teacher_payout_amount), 0.0)
    ).filter(
        Payment.status == "success",
        Payment.payout_status == "pending",
    ).scalar() or 0.0

    total_released_payout = db.session.query(
        func.coalesce(func.sum(Payment.teacher_payout_amount), 0.0)
    ).filter(
        Payment.status == "success",
        Payment.payout_status == "released",
    ).scalar() or 0.0

    teachers_awaiting = db.session.query(
        func.count(func.distinct(
            func.coalesce(
                func.nullif(Payment.course_id, None),
                Payment.booking_id_ref
            )
        ))
    ).filter(
        Payment.status == "success",
        Payment.payout_status == "pending",
    ).scalar() or 0

    return render_template(
        "admin/payouts.html",
        payments=payments,
        filter_status=filter_status,
        total_pending_payout=float(total_pending_payout),
        total_released_payout=float(total_released_payout),
        teachers_awaiting=teachers_awaiting,
    )


@admin_bp.route("/payouts/<int:payment_id>/release", methods=["POST"])
@login_required
@admin_required
def release_payout(payment_id: int):
    """Release a single teacher payout — records that manual payment was made."""
    payment = Payment.query.get_or_404(payment_id)

    if payment.status != "success":
        flash("Only successful payments can have payouts released.", "warning")
        return redirect(request.referrer or url_for("admin.payout_list"))

    if payment.payout_status == "released":
        flash(f"Payout for Payment #{payment.id} was already released.", "info")
        return redirect(request.referrer or url_for("admin.payout_list", filter="released"))

    payment.payout_status = "released"
    payment.payout_released_at = datetime.utcnow()
    db.session.commit()

    # Notify the teacher
    teacher_user = payment.teacher_user
    if teacher_user:
        notify(
            user_id=teacher_user.id,
            title=f"💰 Payout Released: NPR {payment.teacher_payout_amount}",
            body=(
                f"Your earnings of NPR {payment.teacher_payout_amount} for '{payment.item_title}' "
                f"have been marked as paid out by the admin team."
            ),
            notif_type="payment",
            link=url_for("teacher.dashboard"),
        )

    flash(
        f"✅ Payout of NPR {payment.teacher_payout_amount} for Payment #{payment.id} marked as released."
        f" Teacher has been notified.",
        "success"
    )
    return redirect(request.referrer or url_for("admin.payout_list", filter="released"))


@admin_bp.route("/payouts/teacher/<int:teacher_profile_id>/release-all", methods=["POST"])
@login_required
@admin_required
def release_all_payouts(teacher_profile_id: int):
    """Bulk-release all pending payouts for a specific teacher."""
    profile = TeacherProfile.query.get_or_404(teacher_profile_id)

    # Collect all pending success payments for this teacher
    # (both course payments and booking payments)
    teacher_course_ids = [c.id for c in profile.courses]
    teacher_booking_ids_q = db.session.query(Booking.id).filter(Booking.teacher_id == profile.user_id)

    pending_payments = Payment.query.filter(
        Payment.status == "success",
        Payment.payout_status == "pending",
        db.or_(
            db.and_(Payment.payment_for == "course", Payment.course_id.in_(teacher_course_ids)),
            db.and_(Payment.payment_for == "booking", Payment.booking_id_ref.in_(teacher_booking_ids_q)),
        )
    ).all()

    if not pending_payments:
        flash(f"No pending payouts found for teacher '{profile.user.full_name if profile.user else '(unknown)'}'", "info")
        return redirect(request.referrer or url_for("admin.payout_list"))

    total_released = sum(float(p.teacher_payout_amount or 0) for p in pending_payments)
    now = datetime.utcnow()
    for p in pending_payments:
        p.payout_status = "released"
        p.payout_released_at = now
    db.session.commit()

    # Notify teacher once
    if profile.user:
        notify(
            user_id=profile.user.id,
            title=f"💰 Bulk Payout Released: NPR {total_released:.2f}",
            body=(
                f"Your total pending earnings of NPR {total_released:.2f} "
                f"across {len(pending_payments)} payment(s) have been marked as paid out."
            ),
            notif_type="payment",
            link=url_for("teacher.dashboard"),
        )

    flash(
        f"✅ Released {len(pending_payments)} payout(s) totalling NPR {total_released:.2f} for "
        f"'{profile.user.full_name if profile.user else 'teacher'}'. Teacher has been notified.",
        "success"
    )
    return redirect(request.referrer or url_for("admin.payout_list", filter="released"))

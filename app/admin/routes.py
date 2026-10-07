"""
app/admin/routes.py — Admin Blueprint Routes
Full platform administration: statistics, teacher verification queue,
course approval queue, payment audit, and user listing.
"""

from datetime import datetime
from decimal import Decimal
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from sqlalchemy import func, or_, and_

from app import db
from app.auth.utils import admin_required
from app.models import (
    User, TeacherProfile, TeacherDocument, Course, Booking, Payment,
    Certificate, Notification, Report, RefundRequest,
    ReportEvidence, ReportResponse, Message, Favorite, Enrollment, Review,
)
from app.notifications.utils import notify
from app.reports.forms import REPORT_REASON_DICT
from app.refunds.service import (
    process_refund,
    get_payment_hold_reason,
    _get_booking_for_payment,
)

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
    pending_refunds = RefundRequest.query.filter_by(status="pending").count()

    # Revenue snapshot:
    #   success rows   → full payment.amount (platform keeps platform_fee_amount, teacher gets teacher_payout_amount)
    #   refunded rows  → only the retained platform_fee_amount counts as platform revenue
    success_rev = db.session.query(
        func.coalesce(func.sum(Payment.platform_fee_amount), 0.0)
    ).filter(Payment.status == "success").scalar() or 0.0

    retained_rev = db.session.query(
        func.coalesce(func.sum(Payment.platform_fee_amount), 0.0)
    ).filter(Payment.status == "refunded").scalar() or 0.0

    total_revenue = float(success_rev) + float(retained_rev)

    # Refunded figures for transparency
    total_refunded = db.session.query(
        func.coalesce(func.sum(Payment.refund_amount), 0.0)
    ).filter(Payment.status == "refunded").scalar() or 0.0

    total_retained = float(retained_rev)  # alias for template clarity

    # Pending payouts snapshot (success-only; refunded rows have teacher_payout_amount=0)
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
        pending_refunds=pending_refunds,
        total_revenue=total_revenue,
        total_refunded=float(total_refunded),
        total_retained=total_retained,
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
        title="Your Instructor Profile Is Now Verified!",
        body=(
            "Congratulations! SkillBridge has verified your instructor profile. "
            "You now appear in learner search results with the Verified badge."
        ),
        notif_type="admin",
        link=url_for("teacher.dashboard"),
    )

    flash(f"{profile.user.full_name}'s profile has been verified.", "success")
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

    flash(f"Verification revoked for {profile.user.full_name}.", "warning")
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
            title=f"Your course '{course.title}' has been approved!",
            body="Your course passed admin review and is now officially listed in the SkillBridge catalog.",
            notif_type="course",
            link=url_for("courses.course_detail", course_id=course.id),
        )

    flash(f"Course '{course.title}' has been approved and is now listed.", "success")
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

    flash(f"Approval revoked for course '{course.title}'.", "warning")
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

    # Revenue totals (same accounting as dashboard):
    #   success → sum of platform_fee_amount earned
    #   refunded → sum of platform_fee_amount retained
    success_rev = db.session.query(
        func.coalesce(func.sum(Payment.platform_fee_amount), 0.0)
    ).filter(Payment.status == "success").scalar() or 0.0

    retained_rev = db.session.query(
        func.coalesce(func.sum(Payment.platform_fee_amount), 0.0)
    ).filter(Payment.status == "refunded").scalar() or 0.0

    revenue_total = float(success_rev) + float(retained_rev)

    refunds_total = db.session.query(
        func.coalesce(func.sum(Payment.refund_amount), 0.0)
    ).filter(Payment.status == "refunded").scalar() or 0.0

    return render_template(
        "admin/payments.html",
        user=current_user,
        pagination=pagination,
        payments=pagination.items,
        filter_status=filter_status,
        revenue_total=revenue_total,
        refunds_total=float(refunds_total),
        retained_rev=float(retained_rev),
    )


@admin_bp.route("/payments/<int:payment_id>/refund", methods=["GET", "POST"])
@login_required
@admin_required
def payment_refund_direct(payment_id: int):
    """
    Direct refund action for a payment record without a prior student request.
    GET: displays payment/booking context and amount-entry form.
    POST: processes refund via central process_refund() service.
    """
    payment = Payment.query.get_or_404(payment_id)
    booking = _get_booking_for_payment(payment)

    misconduct_blocked = False
    if booking:
        upheld = Report.query.filter_by(
            reported_id=payment.learner_id,
            booking_id=booking.id,
            status="resolved",
        ).first()
        if upheld:
            misconduct_blocked = True

    if request.method == "POST":
        if payment.status != "success":
            flash(f"Payment #{payment.id} cannot be refunded (status is '{payment.status}').", "danger")
            return redirect(url_for("admin.payment_list"))

        raw_amount = request.form.get("refund_amount", "").strip()
        admin_notes = request.form.get("admin_notes", "").strip()

        try:
            amount = Decimal(raw_amount)
        except Exception:
            flash("Please enter a valid numeric refund amount.", "danger")
            return redirect(url_for("admin.payment_refund_direct", payment_id=payment.id))

        result = process_refund(payment, amount, current_user, admin_notes)
        if not result["success"]:
            flash(result["error"], "danger")
            return redirect(url_for("admin.payment_refund_direct", payment_id=payment.id))

        # If there was an open refund request for this booking, mark it decided
        if booking:
            open_rr = RefundRequest.query.filter_by(booking_id=booking.id, status="pending").first()
            if open_rr:
                open_rr.status = "approved" if amount == Decimal(str(payment.amount)) else "partially_approved"
                open_rr.approved_amount = amount
                open_rr.admin_notes = admin_notes or None
                open_rr.decided_by = current_user.id
                open_rr.decided_at = datetime.utcnow()
                db.session.commit()

        if result.get("warning"):
            flash(result["warning"], "warning")

        flash(f"Refund of NPR {amount:.2f} processed for Payment #{payment.id}. Both parties have been notified.", "success")
        return redirect(url_for("admin.payment_list"))

    return render_template(
        "admin/refund_direct.html",
        payment=payment,
        booking=booking,
        report=None,
        misconduct_blocked=misconduct_blocked,
    )


def get_active_user_ids(user_ids: list[int]) -> set[int]:
    """Precompute active user IDs for a list of user IDs in efficient batch queries."""
    if not user_ids:
        return set()
    active_ids = set()
    for row in db.session.query(Payment.learner_id).filter(Payment.learner_id.in_(user_ids)).distinct():
        active_ids.add(row[0])
    for row in db.session.query(Booking.learner_id).filter(Booking.learner_id.in_(user_ids)).distinct():
        active_ids.add(row[0])
    for row in db.session.query(Booking.teacher_id).filter(Booking.teacher_id.in_(user_ids)).distinct():
        active_ids.add(row[0])
    for row in db.session.query(Enrollment.learner_id).filter(Enrollment.learner_id.in_(user_ids)).distinct():
        active_ids.add(row[0])
    for row in db.session.query(Review.learner_id).filter(Review.learner_id.in_(user_ids)).distinct():
        active_ids.add(row[0])
    for row in db.session.query(TeacherProfile.user_id).join(Course, Course.teacher_id == TeacherProfile.id).filter(TeacherProfile.user_id.in_(user_ids)).distinct():
        active_ids.add(row[0])
    for row in db.session.query(TeacherProfile.user_id).join(Review, Review.teacher_id == TeacherProfile.id).filter(TeacherProfile.user_id.in_(user_ids)).distinct():
        active_ids.add(row[0])
    for row in db.session.query(TeacherProfile.user_id).join(Course, Course.teacher_id == TeacherProfile.id).join(Payment, Payment.course_id == Course.id).filter(TeacherProfile.user_id.in_(user_ids)).distinct():
        active_ids.add(row[0])
    for row in db.session.query(Booking.teacher_id).join(Payment, Payment.booking_id_ref == Booking.id).filter(Booking.teacher_id.in_(user_ids)).distinct():
        active_ids.add(row[0])
    for row in db.session.query(Report.reporter_id).filter(Report.reporter_id.in_(user_ids)).distinct():
        active_ids.add(row[0])
    for row in db.session.query(Report.reported_id).filter(Report.reported_id.in_(user_ids)).distinct():
        active_ids.add(row[0])
    return active_ids


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

    active_user_ids = get_active_user_ids([u.id for u in pagination.items])

    return render_template(
        "admin/users.html",
        user=current_user,
        pagination=pagination,
        users=pagination.items,
        role_filter=role_filter,
        active_user_ids=active_user_ids,
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

    flash(f"User '{user.full_name}' has been banned and suspended.", "warning")
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

    flash(f"User '{user.full_name}' has been unbanned and restored.", "success")
    return redirect(request.referrer or url_for("admin.user_list"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id: int):
    """
    Safely delete or anonymize a user account with real safety rails:
    1. Admins can NEVER be deleted.
    2. Users cannot delete their own account via this endpoint.
    3. If the user has real platform activity (payments, bookings, enrollments,
       courses, or reviews):
       - Refuse hard delete and perform SOFT DELETE / ANONYMIZE:
         scrub full_name, replace email with unique placeholder,
         clear profile_photo, set is_active=False, clear password_hash/tokens.
         Keep historical payment/booking/review rows intact for financial/audit integrity.
    4. If the user has ZERO activity (genuinely empty/test/spam account):
       - Allow real hard delete of the User row (and empty TeacherProfile) via ORM.
    """
    user = User.query.get_or_404(user_id)

    # Safety Rail 1: Never allow deleting own account
    if user.id == current_user.id:
        flash("You cannot delete your own administrator account.", "danger")
        return redirect(request.referrer or url_for("admin.user_list"))

    # Safety Rail 2: Never allow deleting an admin account
    if user.role == "admin":
        flash("You cannot delete an administrator account.", "danger")
        return redirect(request.referrer or url_for("admin.user_list"))

    # Check if already anonymized
    if user.is_anonymized:
        flash(f"User account #{user.id} has already been anonymized and deactivated.", "info")
        return redirect(request.referrer or url_for("admin.user_list"))

    user_name = user.full_name

    # Safety Rail 3: Check whether this user has any real activity
    if user.has_activity():
        # Soft delete / Anonymize: scrub personally identifying fields
        user.full_name = "Deleted User"
        user.email = f"deleted_user_{user.id}@skillbridge.local"
        user.profile_photo = None
        user.is_active = False
        user.password_hash = None
        user.google_id = None
        user.reset_token = None
        user.reset_token_expiry = None
        user.email_verify_token = None
        user.is_email_verified = False

        if user.teacher_profile:
            user.teacher_profile.linkedin_url = None
            user.teacher_profile.website_url = None

        db.session.commit()

        flash(
            f"User account '{user_name}' (ID #{user.id}) has active history (bookings, payments, courses, or reviews). "
            f"To preserve financial and audit integrity, the account was safely anonymized: "
            f"personal details scrubbed, login disabled, and historical records preserved.",
            "warning",
        )
    else:
        # Hard delete: genuinely empty test/spam account with zero activity
        if user.teacher_profile:
            TeacherDocument.query.filter_by(teacher_profile_id=user.teacher_profile.id).delete(synchronize_session=False)
        Message.query.filter(or_(Message.sender_id == user.id, Message.receiver_id == user.id)).delete(synchronize_session=False)
        Notification.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        Favorite.query.filter_by(learner_id=user.id).delete(synchronize_session=False)

        db.session.delete(user)
        db.session.commit()

        flash(
            f"User '{user_name}' (ID #{user.id}) had zero activity history and was permanently deleted from the database.",
            "success",
        )

    return redirect(request.referrer or url_for("admin.user_list"))


# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# 6. Report Admin — Unified Case Management & Moderation
# ─────────────────────────────────────────────────────────────────────────────
@admin_bp.route("/reports")
@login_required
@admin_required
def report_list():
    """
    Paginated queue of unified Report Admin cases with comprehensive filtering.
    Fixes the query-parameter mismatch by accepting both 'status' and 'filter'.
    """
    page = request.args.get("page", 1, type=int)
    # Fix query param bug: accept both 'filter' and 'status'
    filter_status = (request.args.get("status") or request.args.get("filter") or "pending").strip().lower()

    query = Report.query

    if filter_status == "pending":
        query = query.filter(Report.status == "pending")
    elif filter_status == "reviewed":
        query = query.filter(Report.status == "reviewed")
    elif filter_status == "resolved":
        query = query.filter(Report.status == "resolved")
    elif filter_status == "dismissed":
        query = query.filter(Report.status == "dismissed")
    elif filter_status == "refund_requested":
        query = query.filter(or_(Report.refund_requested.is_(True), Report.refund_request_id.isnot(None)))
    elif filter_status == "no_refund":
        query = query.filter(and_(Report.refund_requested.is_(False), Report.refund_request_id.is_(None)))
    elif filter_status == "learner_reports":
        query = query.join(User, Report.reporter_id == User.id).filter(User.role == "learner")
    elif filter_status == "teacher_reports":
        query = query.join(User, Report.reporter_id == User.id).filter(User.role == "teacher")
    # 'all' shows all reports

    pagination = query.order_by(Report.created_at.desc(), Report.id.desc()).paginate(
        page=page, per_page=15, error_out=False
    )

    # Queue counts for filter badges
    pending_count = Report.query.filter_by(status="pending").count()
    reviewed_count = Report.query.filter_by(status="reviewed").count()
    resolved_count = Report.query.filter_by(status="resolved").count()
    dismissed_count = Report.query.filter_by(status="dismissed").count()
    refund_requested_count = Report.query.filter(
        or_(Report.refund_requested.is_(True), Report.refund_request_id.isnot(None))
    ).count()
    total_count = Report.query.count()

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
        status_filter=filter_status,  # backwards-compatible with template
        pending_count=pending_count,
        reviewed_count=reviewed_count,
        resolved_count=resolved_count,
        dismissed_count=dismissed_count,
        refund_requested_count=refund_requested_count,
        total_count=total_count,
        eligible_payments=eligible_payments,
        report_reason_dict=REPORT_REASON_DICT,
    )


@admin_bp.route("/reports/<int:report_id>")
@login_required
@admin_required
def report_detail(report_id: int):
    """
    Unified case review page for a Report Admin case.
    Shows Case overview, Reporter, Reported User, Session, Payment info,
    submitted evidence, participant responses, and Admin decision controls.
    """
    report = Report.query.get_or_404(report_id)
    booking = report.booking
    reporter = report.reporter
    reported = report.reported

    # Associated payment
    payment = None
    if booking:
        payment = booking.payment or Payment.query.filter_by(
            payment_for="booking",
            booking_id_ref=booking.id,
        ).order_by(Payment.id.desc()).first()

    # Associated refund request (if any)
    refund_req = report.refund_request
    if not refund_req and booking:
        refund_req = RefundRequest.query.filter_by(booking_id=booking.id).order_by(RefundRequest.id.desc()).first()

    # Evidence items & responses
    evidence_items = report.evidence_items
    responses = report.responses

    # Disciplinary / trust & safety strike counts
    learner_id = booking.learner_id if booking else (reporter.id if reporter and reporter.role == "learner" else (reported.id if reported else None))
    teacher_id = booking.teacher_id if booking else (reporter.id if reporter and reporter.role == "teacher" else (reported.id if reported else None))

    learner_reports_against = Report.query.filter_by(reported_id=learner_id).count() if learner_id else 0
    learner_upheld_reports = Report.query.filter_by(reported_id=learner_id, status="resolved").count() if learner_id else 0
    teacher_reports_against = Report.query.filter_by(reported_id=teacher_id).count() if teacher_id else 0
    teacher_upheld_reports = Report.query.filter_by(reported_id=teacher_id, status="resolved").count() if teacher_id else 0

    reason_label = REPORT_REASON_DICT.get(report.reason, report.reason.replace("_", " ").title())

    return render_template(
        "admin/report_detail.html",
        report=report,
        booking=booking,
        reporter=reporter,
        reported=reported,
        payment=payment,
        refund_req=refund_req,
        evidence_items=evidence_items,
        responses=responses,
        learner_reports_against=learner_reports_against,
        learner_upheld_reports=learner_upheld_reports,
        teacher_reports_against=teacher_reports_against,
        teacher_upheld_reports=teacher_upheld_reports,
        reason_label=reason_label,
    )


@admin_bp.route("/reports/<int:report_id>/mark-reviewed", methods=["POST"])
@login_required
@admin_required
def mark_report_reviewed(report_id: int):
    """Mark a Report Admin case as under review."""
    report = Report.query.get_or_404(report_id)
    report.status = "reviewed"
    db.session.commit()
    flash(f"Report #{report.id} marked as Under Review.", "info")
    return redirect(url_for("admin.report_detail", report_id=report.id))


@admin_bp.route("/reports/<int:report_id>/request-response", methods=["POST"])
@login_required
@admin_required
def request_report_response(report_id: int):
    """
    Request a formal response and evidence from the reported user (teacher or learner).
    Sets response_requested flag, changes status to reviewed, and dispatches notification.
    """
    report = Report.query.get_or_404(report_id)
    report.response_requested = True
    report.response_requested_at = datetime.utcnow()
    if report.status == "pending":
        report.status = "reviewed"
    db.session.commit()

    target_user = report.reported
    if target_user:
        notify(
            user_id=target_user.id,
            title=f"Action Required: Response Requested for Booking #{report.booking_id}",
            body=(
                f"An administrator is investigating Report #{report.id} regarding your session "
                f"and has requested your formal explanation and supporting evidence."
            ),
            notif_type="system",
            link=url_for("booking.detail", booking_id=report.booking_id) if report.booking_id else url_for("learner.dashboard"),
        )

    flash(f"Formal response requested from {target_user.full_name if target_user else 'user'}.", "success")
    return redirect(url_for("admin.report_detail", report_id=report.id))


@admin_bp.route("/reports/<int:report_id>/dismiss", methods=["POST"])
@login_required
@admin_required
def dismiss_report(report_id: int):
    """Dismiss a report case with administrative notes and notify reporter."""
    report = Report.query.get_or_404(report_id)
    admin_notes = request.form.get("admin_notes", "").strip()

    report.status = "dismissed"
    report.resolved_at = datetime.utcnow()
    if admin_notes:
        report.admin_notes = f"{report.admin_notes}\n{admin_notes}" if report.admin_notes else admin_notes

    db.session.commit()

    if report.reporter_id:
        notify(
            user_id=report.reporter_id,
            title=f"Report Admin Case #{report.id} Dismissed",
            body=(
                f"Your report regarding Booking #{report.booking_id} has been reviewed and "
                f"dismissed by administration."
                f"{(' Note: ' + admin_notes) if admin_notes else ''}"
            ),
            notif_type="system",
            link=url_for("booking.detail", booking_id=report.booking_id) if report.booking_id else url_for("learner.dashboard"),
        )

    flash(f"Report #{report.id} has been dismissed.", "info")
    return redirect(request.referrer or url_for("admin.report_detail", report_id=report.id))


@admin_bp.route("/reports/<int:report_id>/resolve", methods=["POST"])
@login_required
@admin_required
def resolve_report(report_id: int):
    """
    Mark a report case as resolved (separate from refund decision).
    Appends admin notes and notifies the reporter.
    """
    report = Report.query.get_or_404(report_id)
    admin_notes = request.form.get("admin_notes", "").strip()

    report.status = "resolved"
    report.resolved_at = datetime.utcnow()
    if admin_notes:
        report.admin_notes = f"{report.admin_notes}\n{admin_notes}" if report.admin_notes else admin_notes

    db.session.commit()

    if report.reporter_id:
        notify(
            user_id=report.reporter_id,
            title=f"Report Admin Case #{report.id} Resolved",
            body=(
                f"Your report regarding Booking #{report.booking_id} has been resolved by administration."
                f"{(' Resolution Note: ' + admin_notes) if admin_notes else ''}"
            ),
            notif_type="system",
            link=url_for("booking.detail", booking_id=report.booking_id) if report.booking_id else url_for("learner.dashboard"),
        )

    flash(f"Report #{report.id} marked as resolved.", "success")
    return redirect(request.referrer or url_for("admin.report_detail", report_id=report.id))


@admin_bp.route("/reports/<int:report_id>/refund-approve", methods=["POST"])
@login_required
@admin_required
def report_refund_approve(report_id: int):
    """
    Approve refund for a Report Admin case using central process_refund().
    Applies entered refund amount (full or partial), updates linked RefundRequest,
    marks report as resolved, and triggers refund notifications.
    """
    report = Report.query.get_or_404(report_id)

    if not report.booking_id:
        flash("This report is not tied to a booking.", "warning")
        return redirect(url_for("admin.report_detail", report_id=report.id))

    payment = Payment.query.filter_by(
        payment_for="booking",
        booking_id_ref=report.booking_id,
        status="success",
    ).first()

    if not payment:
        flash("Nothing to refund for this booking. No successful payment found.", "warning")
        return redirect(url_for("admin.report_detail", report_id=report.id))

    raw_amount = request.form.get("refund_amount", "").strip()
    admin_notes = request.form.get("admin_notes", "").strip()

    try:
        amount = Decimal(raw_amount) if raw_amount else Decimal(str(payment.amount))
    except Exception:
        flash("Invalid refund amount entered.", "danger")
        return redirect(url_for("admin.report_detail", report_id=report.id))

    note_text = f"Report Admin #{report.id} ({report.reason}): {admin_notes}".strip()
    result = process_refund(payment, amount, current_user, note_text)

    if not result["success"]:
        flash(result["error"], "danger")
        return redirect(url_for("admin.report_detail", report_id=report.id))

    is_full = (amount == Decimal(str(payment.amount)))

    # Synchronize linked RefundRequest if one exists
    refund_req = report.refund_request or RefundRequest.query.filter_by(
        booking_id=report.booking_id,
        status="pending",
    ).first()

    if refund_req:
        refund_req.status = "approved" if is_full else "partially_approved"
        refund_req.approved_amount = amount
        refund_req.admin_notes = admin_notes or None
        refund_req.decided_by = current_user.id
        refund_req.decided_at = datetime.utcnow()

    # Mark report as resolved with refund note
    report.status = "resolved"
    report.resolved_at = datetime.utcnow()
    report_note = f"Refunded NPR {amount:.2f} via Payment #{payment.id}. Note: {admin_notes}".strip()
    report.admin_notes = f"{report.admin_notes}\n{report_note}" if report.admin_notes else report_note
    db.session.commit()

    if result.get("warning"):
        flash(result["warning"], "warning")

    status_str = "fully approved" if is_full else f"partially approved (NPR {amount:.2f})"
    flash(f"Refund {status_str} for Report #{report.id}. Both parties have been notified.", "success")
    return redirect(url_for("admin.report_detail", report_id=report.id))


@admin_bp.route("/reports/<int:report_id>/refund-reject", methods=["POST"])
@login_required
@admin_required
def report_refund_reject(report_id: int):
    """
    Reject refund request within a Report Admin case.
    Preserves payment as success, updates RefundRequest to rejected,
    notifies the student, and appends admin notes to the case.
    """
    report = Report.query.get_or_404(report_id)
    admin_notes = request.form.get("admin_notes", "").strip()

    refund_req = report.refund_request or (
        RefundRequest.query.filter_by(booking_id=report.booking_id, status="pending").first()
        if report.booking_id
        else None
    )

    if refund_req:
        refund_req.status = "rejected"
        refund_req.admin_notes = admin_notes or None
        refund_req.decided_by = current_user.id
        refund_req.decided_at = datetime.utcnow()

        topic = report.booking.topic if report.booking else "Mentorship Session"
        notify(
            user_id=refund_req.learner_id,
            title=f"Refund Request Rejected: Booking #{report.booking_id}",
            body=(
                f"Your refund request for session '{topic}' has been rejected by an administrator.\n\n"
                f"Reason: {admin_notes or 'Request did not meet refund criteria.'}"
            ),
            notif_type="payment",
            link=url_for("booking.detail", booking_id=report.booking_id) if report.booking_id else url_for("learner.dashboard"),
        )

    reject_note = f"Refund rejected: {admin_notes}".strip()
    report.admin_notes = f"{report.admin_notes}\n{reject_note}" if report.admin_notes else reject_note
    db.session.commit()

    flash(f"Refund request for Report #{report.id} rejected. Learner has been notified.", "info")
    return redirect(url_for("admin.report_detail", report_id=report.id))


@admin_bp.route("/reports/<int:report_id>/refund", methods=["GET", "POST"])
@login_required
@admin_required
def refund_report(report_id: int):
    """
    Legacy direct refund route for backwards compatibility.
    Redirects to the unified report_detail case review page.
    """
    if request.method == "POST":
        return report_refund_approve(report_id)
    return redirect(url_for("admin.report_detail", report_id=report_id))


# ─────────────────────────────────────────────────────────────────────────────
# 10. Payout Management
# ─────────────────────────────────────────────────────────────────────────────
@admin_bp.route("/payouts")
@login_required
@admin_required
def payout_list():
    """Admin payout management queue — lists teacher payouts with filter tabs and pagination."""
    page = request.args.get("page", 1, type=int)
    filter_status = request.args.get("filter", "pending").strip().lower()
    teacher_id = request.args.get("teacher_id", type=int)

    base_q = Payment.query.filter(Payment.status == "success")

    if filter_status == "pending":
        query = base_q.filter(Payment.payout_status == "pending")
    elif filter_status == "released":
        query = base_q.filter(Payment.payout_status == "released")
    else:  # 'all'
        query = base_q

    # Optional teacher profile filter
    selected_teacher_profile = None
    if teacher_id:
        selected_teacher_profile = TeacherProfile.query.get(teacher_id)
        if selected_teacher_profile:
            t_course_ids = [c.id for c in selected_teacher_profile.courses]
            t_booking_ids_q = db.session.query(Booking.id).filter(Booking.teacher_id == selected_teacher_profile.user_id)
            conds = []
            if t_course_ids:
                conds.append(db.and_(Payment.payment_for == "course", Payment.course_id.in_(t_course_ids)))
            conds.append(db.and_(Payment.payment_for == "booking", Payment.booking_id_ref.in_(t_booking_ids_q)))
            query = query.filter(db.or_(*conds))

    if filter_status == "released":
        query = query.order_by(Payment.payout_released_at.desc(), Payment.id.desc())
    else:
        query = query.order_by(Payment.completed_at.desc(), Payment.id.desc())

    pagination = query.paginate(page=page, per_page=20, error_out=False)
    payments = pagination.items

    from app.refunds.service import get_payment_hold_reason
    for p in payments:
        p.hold_reason = get_payment_hold_reason(p)

    # ── Per-teacher pending subtotals calculation ────────────────────────────
    pending_payments_all = Payment.query.filter(
        Payment.status == "success",
        Payment.payout_status == "pending",
    ).all()

    teacher_subtotals_map = {}
    for p in pending_payments_all:
        tu = p.teacher_user
        tp = p.teacher_profile
        if not tu:
            continue
        key = tp.id if tp else tu.id
        if key not in teacher_subtotals_map:
            teacher_subtotals_map[key] = {
                "profile_id": tp.id if tp else None,
                "user_id": tu.id,
                "name": tu.full_name,
                "email": tu.email,
                "total_pending": Decimal("0.00"),
                "count": 0,
            }
        # Keep payments on hold out of pending payout subtotals
        if get_payment_hold_reason(p):
            continue
        payout_amt = Decimal(str(p.teacher_payout_amount or 0))
        teacher_subtotals_map[key]["total_pending"] += payout_amt
        teacher_subtotals_map[key]["count"] += 1

    teacher_subtotals = sorted(
        [t for t in teacher_subtotals_map.values() if t["count"] > 0],
        key=lambda x: x["total_pending"],
        reverse=True,
    )

    # Overall summary stats (only releasable pending payouts)
    total_pending_payout = sum(
        Decimal(str(p.teacher_payout_amount or 0))
        for p in pending_payments_all
        if not get_payment_hold_reason(p)
    )

    total_released_payout = db.session.query(
        func.coalesce(func.sum(Payment.teacher_payout_amount), 0.0)
    ).filter(
        Payment.status == "success",
        Payment.payout_status == "released",
    ).scalar() or 0.0

    return render_template(
        "admin/payouts.html",
        payments=payments,
        pagination=pagination,
        filter_status=filter_status,
        teacher_filter_id=teacher_id,
        selected_teacher=selected_teacher_profile,
        teacher_subtotals=teacher_subtotals,
        total_pending_payout=float(total_pending_payout),
        total_released_payout=float(total_released_payout),
        teachers_awaiting=len(teacher_subtotals),
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

    from app.refunds.service import get_payment_hold_reason
    hold_reason = get_payment_hold_reason(payment)
    if hold_reason:
        flash(f"Cannot release payout for Payment #{payment.id}: Payment is on hold ({hold_reason}).", "danger")
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
            title=f"Payout Released: NPR {payment.teacher_payout_amount}",
            body=(
                f"Your earnings of NPR {payment.teacher_payout_amount} for '{payment.item_title}' "
                f"have been marked as paid out by the admin team."
            ),
            notif_type="payment",
            link=url_for("teacher.dashboard"),
        )

    flash(
        f"Payout of NPR {payment.teacher_payout_amount} for Payment #{payment.id} marked as released."
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
    teacher_course_ids = [c.id for c in profile.courses]
    teacher_booking_ids_q = db.session.query(Booking.id).filter(Booking.teacher_id == profile.user_id)

    conds = []
    if teacher_course_ids:
        conds.append(db.and_(Payment.payment_for == "course", Payment.course_id.in_(teacher_course_ids)))
    conds.append(db.and_(Payment.payment_for == "booking", Payment.booking_id_ref.in_(teacher_booking_ids_q)))

    pending_payments = Payment.query.filter(
        Payment.status == "success",
        Payment.payout_status == "pending",
        db.or_(*conds)
    ).all()

    from app.refunds.service import get_payment_hold_reason
    releasable_payments = [p for p in pending_payments if not get_payment_hold_reason(p)]
    held_count = len(pending_payments) - len(releasable_payments)

    if not releasable_payments:
        msg = f"No releasable payouts found for teacher '{profile.user.full_name if profile.user else '(unknown)'}'."
        if held_count > 0:
            msg += f" {held_count} pending payment(s) are on hold and cannot be released."
        flash(msg, "info")
        return redirect(request.referrer or url_for("admin.payout_list"))

    total_released = sum(float(p.teacher_payout_amount or 0) for p in releasable_payments)
    now = datetime.utcnow()
    for p in releasable_payments:
        p.payout_status = "released"
        p.payout_released_at = now
    db.session.commit()

    # Notify teacher once
    if profile.user:
        notify(
            user_id=profile.user.id,
            title=f"Bulk Payout Released: NPR {total_released:.2f}",
            body=(
                f"Your total pending earnings of NPR {total_released:.2f} "
                f"across {len(releasable_payments)} payment(s) have been marked as paid out."
            ),
            notif_type="payment",
            link=url_for("teacher.dashboard"),
        )

    flash_msg = (
        f"Released {len(releasable_payments)} payout(s) totalling NPR {total_released:.2f} for "
        f"'{profile.user.full_name if profile.user else 'teacher'}'. Teacher has been notified."
    )
    if held_count > 0:
        flash_msg += f" Note: {held_count} payment(s) are on hold and were not released."
    flash(flash_msg, "success")
    return redirect(request.referrer or url_for("admin.payout_list", filter="released"))


# ─────────────────────────────────────────────────────────────────────────────
# 11. Refund Management Console
# ─────────────────────────────────────────────────────────────────────────────
@admin_bp.route("/refunds")
@login_required
@admin_required
def refund_list():
    """Admin refund request queue with status filters and pagination."""
    page = request.args.get("page", 1, type=int)
    filter_status = request.args.get("filter", "pending").strip().lower()

    base_q = RefundRequest.query

    if filter_status == "pending":
        query = base_q.filter(RefundRequest.status == "pending")
    elif filter_status == "approved":
        query = base_q.filter(RefundRequest.status == "approved")
    elif filter_status == "partially_approved":
        query = base_q.filter(RefundRequest.status == "partially_approved")
    elif filter_status == "rejected":
        query = base_q.filter(RefundRequest.status == "rejected")
    else:  # 'all'
        query = base_q

    query = query.order_by(RefundRequest.created_at.desc(), RefundRequest.id.desc())
    pagination = query.paginate(page=page, per_page=20, error_out=False)
    refund_requests = pagination.items

    pending_count = RefundRequest.query.filter_by(status="pending").count()
    approved_count = RefundRequest.query.filter(RefundRequest.status.in_(["approved", "partially_approved"])).count()
    rejected_count = RefundRequest.query.filter_by(status="rejected").count()

    return render_template(
        "admin/refunds.html",
        refund_requests=refund_requests,
        pagination=pagination,
        filter_status=filter_status,
        pending_count=pending_count,
        approved_count=approved_count,
        rejected_count=rejected_count,
    )


@admin_bp.route("/refunds/<int:request_id>")
@login_required
@admin_required
def refund_review(request_id: int):
    """
    Case review page for a student refund request.
    Displays booking, payment, both parties' reports, and user strike history.
    Provides full or partial approval and rejection forms.
    """
    refund_req = RefundRequest.query.get_or_404(request_id)
    booking = refund_req.booking
    learner = refund_req.learner
    teacher = booking.teacher if booking else None
    payment = booking.payment or (Payment.query.filter_by(booking_id_ref=booking.id).order_by(Payment.id.desc()).first() if booking else None)

    learner_report = Report.query.filter_by(booking_id=booking.id, reporter_id=learner.id).first() if booking and learner else None
    teacher_report = Report.query.filter_by(booking_id=booking.id, reporter_id=teacher.id).first() if booking and teacher else None

    learner_reports_against = Report.query.filter_by(reported_id=learner.id).count() if learner else 0
    learner_upheld_reports = Report.query.filter_by(reported_id=learner.id, status="resolved").count() if learner else 0
    teacher_reports_against = Report.query.filter_by(reported_id=teacher.id).count() if teacher else 0
    teacher_upheld_reports = Report.query.filter_by(reported_id=teacher.id, status="resolved").count() if teacher else 0

    from app.booking.forms import REFUND_REASON_CHOICES
    reason_label = dict(REFUND_REASON_CHOICES).get(refund_req.reason_type, refund_req.reason_type)

    return render_template(
        "admin/refund_review.html",
        refund_req=refund_req,
        booking=booking,
        learner=learner,
        teacher=teacher,
        payment=payment,
        learner_report=learner_report,
        teacher_report=teacher_report,
        learner_reports_against=learner_reports_against,
        learner_upheld_reports=learner_upheld_reports,
        teacher_reports_against=teacher_reports_against,
        teacher_upheld_reports=teacher_upheld_reports,
        reason_label=reason_label,
    )


@admin_bp.route("/refunds/<int:request_id>/approve", methods=["POST"])
@login_required
@admin_required
def refund_approve(request_id: int):
    """Approve a refund request (full or partial) with an administrator note."""
    refund_req = RefundRequest.query.get_or_404(request_id)
    booking = refund_req.booking
    payment = booking.payment or (Payment.query.filter_by(booking_id_ref=booking.id).order_by(Payment.id.desc()).first() if booking else None)

    if not payment:
        flash("No payment found for this booking.", "danger")
        return redirect(url_for("admin.refund_review", request_id=refund_req.id))

    raw_amount = request.form.get("refund_amount", "").strip()
    admin_notes = request.form.get("admin_notes", "").strip()

    try:
        amount = Decimal(raw_amount)
    except Exception:
        flash("Invalid refund amount entered.", "danger")
        return redirect(url_for("admin.refund_review", request_id=refund_req.id))

    result = process_refund(payment, amount, current_user, admin_notes)
    if not result["success"]:
        flash(result["error"], "danger")
        return redirect(url_for("admin.refund_review", request_id=refund_req.id))

    is_full = (amount == Decimal(str(payment.amount)))
    refund_req.status = "approved" if is_full else "partially_approved"
    refund_req.approved_amount = amount
    refund_req.admin_notes = admin_notes or None
    refund_req.decided_by = current_user.id
    refund_req.decided_at = datetime.utcnow()

    # Synchronize linked Report if one exists
    linked_report = Report.query.filter_by(refund_request_id=refund_req.id).first()
    if not linked_report and booking:
        linked_report = Report.query.filter_by(booking_id=booking.id, refund_requested=True).first()
    if linked_report:
        linked_report.status = "resolved"
        linked_report.resolved_at = datetime.utcnow()
        report_note = f"Refunded NPR {amount:.2f} via Payment #{payment.id}. Note: {admin_notes}".strip()
        linked_report.admin_notes = f"{linked_report.admin_notes}\n{report_note}" if linked_report.admin_notes else report_note

    db.session.commit()

    if result.get("warning"):
        flash(result["warning"], "warning")

    status_str = "fully approved" if is_full else f"partially approved (NPR {amount:.2f})"
    flash(f"Refund Request #{refund_req.id} {status_str}. Learner and teacher have been notified.", "success")
    return redirect(url_for("admin.refund_list"))


@admin_bp.route("/refunds/<int:request_id>/reject", methods=["POST"])
@login_required
@admin_required
def refund_reject(request_id: int):
    """Reject a refund request with an explanation note and notify the student."""
    refund_req = RefundRequest.query.get_or_404(request_id)
    booking = refund_req.booking
    admin_notes = request.form.get("admin_notes", "").strip()

    refund_req.status = "rejected"
    refund_req.admin_notes = admin_notes or None
    refund_req.decided_by = current_user.id
    refund_req.decided_at = datetime.utcnow()

    # Synchronize linked Report if one exists
    linked_report = Report.query.filter_by(refund_request_id=refund_req.id).first()
    if not linked_report and booking:
        linked_report = Report.query.filter_by(booking_id=booking.id, refund_requested=True).first()
    if linked_report:
        reject_note = f"Refund rejected: {admin_notes}".strip()
        linked_report.admin_notes = f"{linked_report.admin_notes}\n{reject_note}" if linked_report.admin_notes else reject_note

    db.session.commit()

    topic = booking.topic if booking else "Mentorship Session"
    notify(
        user_id=refund_req.learner_id,
        title=f"Refund Request Rejected: Booking #{refund_req.booking_id}",
        body=(
            f"Your refund request for session '{topic}' has been rejected by an administrator.\n\n"
            f"Reason: {admin_notes or 'Request did not meet refund criteria.'}"
        ),
        notif_type="payment",
        link=url_for("booking.detail", booking_id=refund_req.booking_id) if booking else url_for("learner.dashboard"),
    )

    flash(f"Refund Request #{refund_req.id} marked as rejected. Learner has been notified.", "info")
    return redirect(url_for("admin.refund_list"))


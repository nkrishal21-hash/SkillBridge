"""
app/reports/routes.py — Incident Reporting Routes
"""

from datetime import datetime
from flask import redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app import db
from app.models import User, Booking, Report
from app.reports.forms import ReportForm
from app.notifications.utils import notify
from app.reports import reports_bp


@reports_bp.route("/booking/<int:booking_id>", methods=["POST"])
@login_required
def report_booking(booking_id: int):
    """
    Submit an incident report for an approved or completed mentorship booking.
    Learner reports teacher, or teacher reports learner.
    """
    booking = Booking.query.get_or_404(booking_id)

    # Participant check
    is_learner = (current_user.id == booking.learner_id)
    is_teacher = (current_user.id == booking.teacher_id)
    if not (is_learner or is_teacher):
        abort(403)

    # Status check: only approved or completed bookings can be reported
    if booking.status not in ("approved", "completed"):
        flash("Reports can only be filed for approved or completed sessions.", "danger")
        return redirect(url_for("booking.detail", booking_id=booking.id))

    # Determine reported user
    if is_learner:
        reported_id = booking.teacher_id
        reported_label = "teacher"
    else:
        reported_id = booking.learner_id
        reported_label = "learner"

    # Soft check: duplicate pending report from same reporter for this booking
    existing_pending = Report.query.filter_by(
        booking_id=booking.id,
        reporter_id=current_user.id,
        status="pending",
    ).first()

    if existing_pending:
        flash("You already have a pending report for this session.", "warning")
        return redirect(url_for("booking.detail", booking_id=booking.id))

    form = ReportForm()
    if form.validate_on_submit():
        report = Report(
            reporter_id=current_user.id,
            reported_id=reported_id,
            booking_id=booking.id,
            reason=form.reason.data,
            description=form.description.data.strip() if form.description.data else None,
            status="pending",
            created_at=datetime.utcnow(),
        )
        db.session.add(report)
        db.session.commit()

        # Notify all admins
        admins = User.query.filter_by(role="admin").all()
        for admin in admins:
            notify(
                user_id=admin.id,
                title=f"New Incident Report: Booking #{booking.id}",
                body=f"{current_user.full_name} reported their {reported_label} for {form.reason.data}.",
                notif_type="system",
                link=url_for("admin.report_list"),
            )

        flash("Your report has been submitted for administrative review.", "success")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{error}", "danger")

    return redirect(url_for("booking.detail", booking_id=booking.id))

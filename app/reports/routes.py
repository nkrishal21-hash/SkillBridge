"""
app/reports/routes.py — Report Admin Routes
Unified entry point for learners and teachers to submit reports, upload evidence,
request refunds (learners only), and submit responses to disputes.
"""

from datetime import datetime
from flask import redirect, url_for, flash, abort, request, current_app
from flask_login import login_required, current_user

from app import db
from app.models import User, Booking, Report, ReportEvidence, ReportResponse, Payment, RefundRequest
from app.reports.forms import (
    ReportForm,
    ReportResponseForm,
    REPORT_REASON_DICT,
    EVIDENCE_REQUIRED_REASONS,
)
from app.reports.utils import upload_report_evidence
from app.notifications.utils import notify
from app.reports import reports_bp


@reports_bp.route("/booking/<int:booking_id>", methods=["POST"])
@login_required
def report_booking(booking_id: int):
    """
    Submit a unified Report Admin case for an approved, completed, or cancelled booking.
    Learner reports teacher (with optional refund request).
    Teacher reports learner (no refund option).
    Evidence files (photos, videos, documents) are validated and stored.
    """
    booking = Booking.query.get_or_404(booking_id)

    # Participant verification
    is_learner = (current_user.id == booking.learner_id)
    is_teacher = (current_user.id == booking.teacher_id)
    if not (is_learner or is_teacher):
        abort(403)

    # Status check: approved, completed, or cancelled bookings can be reported
    if booking.status not in ("approved", "completed", "cancelled"):
        flash("Reports can only be filed for approved, completed, or cancelled sessions.", "danger")
        return redirect(url_for("booking.detail", booking_id=booking.id))

    # Automatic server-side participant assignment (cannot be forged)
    if is_learner:
        reported_id = booking.teacher_id
        reported_user = booking.teacher
        reported_label = "teacher"
    else:
        reported_id = booking.learner_id
        reported_user = booking.learner
        reported_label = "learner"

    # Soft check: duplicate pending report from same reporter for this booking
    existing_pending = Report.query.filter_by(
        booking_id=booking.id,
        reporter_id=current_user.id,
        status="pending",
    ).first()

    if existing_pending:
        flash("You already have an active pending Report Admin case for this session.", "warning")
        return redirect(url_for("booking.detail", booking_id=booking.id))

    form = ReportForm()
    if not form.validate_on_submit():
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{error}", "danger")
        return redirect(url_for("booking.detail", booking_id=booking.id))

    reason = form.reason.data
    description = form.description.data.strip() if form.description.data else None

    # ── Evidence handling ─────────────────────────────────────────────────────
    raw_files = request.files.getlist("evidence")
    valid_files = [f for f in raw_files if f and f.filename and f.filename.strip()]

    # Evidence required for primary complaint types
    if reason in EVIDENCE_REQUIRED_REASONS and not valid_files:
        flash(
            "Please upload at least one evidence file (screenshot, photo, video, or document) "
            "supporting your report.",
            "danger",
        )
        return redirect(url_for("booking.detail", booking_id=booking.id))

    uploaded_evidence = []
    for file_storage in valid_files:
        try:
            ev_data = upload_report_evidence(file_storage, current_user.id)
            uploaded_evidence.append(ev_data)
        except ValueError as err:
            flash(f"Evidence upload failed: {err}", "danger")
            return redirect(url_for("booking.detail", booking_id=booking.id))

    # ── Learner refund request handling ───────────────────────────────────────
    wants_refund = False
    linked_refund_request = None

    if is_learner:
        req_refund_val = request.form.get("request_refund", "no").strip().lower()
        if req_refund_val == "yes":
            payment = booking.payment or Payment.query.filter_by(
                booking_id_ref=booking.id,
            ).order_by(Payment.id.desc()).first()

            if not payment or payment.status != "success":
                flash(
                    "A refund request could not be attached because this session does not have "
                    "a successful, unrefunded payment.",
                    "warning",
                )
            else:
                # Check for an upheld misconduct report against the learner
                upheld_misconduct = Report.query.filter_by(
                    reported_id=booking.learner_id,
                    booking_id=booking.id,
                    status="resolved",
                ).first()
                if upheld_misconduct:
                    flash(
                        "You are not eligible to request a refund due to an upheld misconduct "
                        "report on record for this session.",
                        "danger",
                    )
                else:
                    # One open refund request per booking protection
                    existing_open_rr = RefundRequest.query.filter_by(
                        booking_id=booking.id,
                        status="pending",
                    ).first()
                    if existing_open_rr:
                        linked_refund_request = existing_open_rr
                        wants_refund = True
                    else:
                        linked_refund_request = RefundRequest(
                            booking_id=booking.id,
                            learner_id=current_user.id,
                            reason_type=reason,
                            description=description,
                            status="pending",
                            created_at=datetime.utcnow(),
                        )
                        db.session.add(linked_refund_request)
                        db.session.flush()
                        wants_refund = True

    # ── Create Report record ──────────────────────────────────────────────────
    report = Report(
        reporter_id=current_user.id,
        reported_id=reported_id,
        booking_id=booking.id,
        reason=reason,
        description=description,
        status="pending",
        refund_requested=wants_refund,
        refund_request_id=linked_refund_request.id if linked_refund_request else None,
        created_at=datetime.utcnow(),
    )
    db.session.add(report)
    db.session.flush()

    # ── Attach evidence records ───────────────────────────────────────────────
    for ev in uploaded_evidence:
        ev_record = ReportEvidence(
            report_id=report.id,
            uploaded_by=current_user.id,
            file_url=ev["file_url"],
            file_type=ev["file_type"],
            original_filename=ev["original_filename"],
            created_at=datetime.utcnow(),
        )
        db.session.add(ev_record)

    db.session.commit()

    # ── Notifications (Unified, non-duplicate) ────────────────────────────────
    reason_label = REPORT_REASON_DICT.get(reason, reason.replace("_", " ").title())
    admins = User.query.filter_by(role="admin").all()

    if wants_refund:
        admin_body = (
            f"New Report Admin case for Booking #{booking.id}.\n"
            f"Learner {current_user.full_name} reported teacher {booking.teacher.full_name} "
            f"for {reason_label} and requested a refund."
        )
    else:
        admin_body = (
            f"New Report Admin case for Booking #{booking.id}.\n"
            f"{current_user.full_name} reported their {reported_label} "
            f"{reported_user.full_name if reported_user else ''} for {reason_label}."
        )

    for adm in admins:
        notify(
            user_id=adm.id,
            title=f"New Report Admin Case: Booking #{booking.id}",
            body=admin_body,
            notif_type="system",
            link=url_for("admin.report_detail", report_id=report.id),
        )

    # Notify the reported user
    session_date_str = (
        booking.session_date.strftime("%b %d, %Y") if booking.session_date else "your session"
    )
    notify(
        user_id=reported_id,
        title=f"Report Admin Notice: Booking #{booking.id}",
        body=(
            f"A report has been submitted regarding {session_date_str} "
            f"({booking.topic or 'Mentorship Session'}). "
            "You may review the session details and submit an explanation or evidence to Admin."
        ),
        notif_type="system",
        link=url_for("booking.detail", booking_id=booking.id),
    )

    if wants_refund:
        flash(
            "Your report and refund request have been submitted to Admin for moderation review.",
            "success",
        )
    else:
        flash("Your report has been submitted to Admin for moderation review.", "success")

    return redirect(url_for("booking.detail", booking_id=booking.id))


@reports_bp.route("/<int:report_id>/respond", methods=["POST"])
@login_required
def respond_to_report(report_id: int):
    """
    Submit a formal response or explanation to an active Report Admin case.
    Typically used by the reported user to refute false accusations or provide
    context, along with proof/evidence files.
    """
    report = Report.query.get_or_404(report_id)

    # Permission check: reporter, reported user, or admin
    if current_user.id not in (report.reported_id, report.reporter_id) and not current_user.is_admin:
        abort(403)

    if report.status in ("resolved", "dismissed"):
        flash("This report case has already been closed.", "warning")
        return redirect(
            url_for("booking.detail", booking_id=report.booking_id)
            if report.booking_id
            else url_for("learner.dashboard")
        )

    explanation = request.form.get("explanation", "").strip()
    if not explanation:
        flash("Please provide an explanation or response text.", "danger")
        return redirect(
            url_for("booking.detail", booking_id=report.booking_id)
            if report.booking_id
            else url_for("learner.dashboard")
        )

    # Upload any evidence attached to this response
    raw_files = request.files.getlist("evidence")
    valid_files = [f for f in raw_files if f and f.filename and f.filename.strip()]
    uploaded_evidence = []
    for file_storage in valid_files:
        try:
            ev_data = upload_report_evidence(file_storage, current_user.id)
            uploaded_evidence.append(ev_data)
        except ValueError as err:
            flash(f"Evidence upload failed: {err}", "danger")
            return redirect(
                url_for("booking.detail", booking_id=report.booking_id)
                if report.booking_id
                else url_for("learner.dashboard")
            )

    response = ReportResponse(
        report_id=report.id,
        user_id=current_user.id,
        explanation=explanation,
        created_at=datetime.utcnow(),
    )
    db.session.add(response)
    db.session.flush()

    for ev in uploaded_evidence:
        ev_record = ReportEvidence(
            report_id=report.id,
            uploaded_by=current_user.id,
            file_url=ev["file_url"],
            file_type=ev["file_type"],
            original_filename=ev["original_filename"],
            response_id=response.id,
            created_at=datetime.utcnow(),
        )
        db.session.add(ev_record)

    # Transition pending to reviewed if response submitted
    if report.status == "pending":
        report.status = "reviewed"

    db.session.commit()

    # Notify admins that a response was submitted
    admins = User.query.filter_by(role="admin").all()
    for adm in admins:
        notify(
            user_id=adm.id,
            title=f"Response Submitted: Report #{report.id}",
            body=(
                f"{current_user.full_name} submitted a response and evidence for "
                f"Report #{report.id} (Booking #{report.booking_id})."
            ),
            notif_type="system",
            link=url_for("admin.report_detail", report_id=report.id),
        )

    flash("Your response and evidence have been submitted to Admin.", "success")
    return redirect(
        url_for("booking.detail", booking_id=report.booking_id)
        if report.booking_id
        else url_for("learner.dashboard")
    )

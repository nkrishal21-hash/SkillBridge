"""
app/booking/routes.py — 1-on-1 Mentorship Booking Blueprint Routes
Handles session requests, teacher approval/rejection workflow,
cancellations, detail views, and booking history.
"""

import uuid
from datetime import date, datetime
from app.utils.time import nepal_now, nepal_today, NPT
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    abort,
    has_request_context,
)
from flask_login import login_required, current_user
from sqlalchemy import or_, and_
from app import db
from app.models import Booking, User, TeacherProfile, Payment, Report, RefundRequest
from app.auth.utils import learner_required, teacher_required
from app.teacher.utils import available_days_list
from app.booking.forms import (
    BookingForm,
    BookingResponseForm,
    RefundRequestForm,
    REFUND_REASON_CHOICES,
)
from app.reviews.forms import ReviewForm
from app.reports.forms import (
    ReportForm,
    ReportResponseForm,
    LEARNER_REPORT_REASONS,
    TEACHER_REPORT_REASONS,
    REPORT_REASON_DICT,
)
from app.booking.utils import (
    calculate_session_times,
    send_new_booking_email,
    send_booking_response_email,
    booking_is_paid,
)
from app.notifications.utils import notify

booking_bp = Blueprint("booking", __name__)


# ─────────────────────────────────────────────────────────────────────────────
# 1. New Booking Request (Learner Only)
# ─────────────────────────────────────────────────────────────────────────────
@booking_bp.route("/new/<int:teacher_id>", methods=["GET", "POST"])
@login_required
@learner_required
def new(teacher_id: int):
    """
    Learner requests a 1-on-1 session with a teacher.
    teacher_id is the teacher's User.id (FK to users.id on Booking model).
    """
    teacher_user = User.query.filter_by(id=teacher_id, role="teacher").first_or_404()
    profile = teacher_user.teacher_profile

    if not profile:
        flash("This instructor has not set up their mentor profile yet.", "warning")
        return redirect(url_for("teacher.search"))

    if not profile.is_verified:
        flash("This mentor is pending verification and cannot be booked yet.", "warning")
        return redirect(url_for("teacher.public_profile", teacher_id=profile.id))

    # Cannot book with oneself
    if teacher_user.id == current_user.id:
        flash("You cannot book a mentorship session with yourself.", "warning")
        return redirect(url_for("teacher.search"))

    available_days = available_days_list(profile.availability)
    form = BookingForm()

    if form.validate_on_submit():
        session_date = form.session_date.data
        if session_date < nepal_today():
            flash("Session date cannot be in the past.", "danger")
            return render_template(
                "booking/new.html",
                form=form,
                teacher_user=teacher_user,
                profile=profile,
                available_days=available_days,
            )

        # Compute start and end times
        start_t, end_t = calculate_session_times(
            session_date, form.start_time.data, form.duration_minutes.data
        )

        # Check for scheduling conflict for this teacher (status in pending or approved)
        conflict = Booking.query.filter(
            Booking.teacher_id == teacher_user.id,
            Booking.session_date == session_date,
            Booking.status.in_(["pending", "approved"]),
            Booking.start_time < end_t,
            Booking.end_time > start_t,
        ).first()

        if conflict:
            flash(
                "This mentor already has a pending or scheduled session during that time window. "
                "Please choose another time slot or date.",
                "warning",
            )
            return render_template(
                "booking/new.html",
                form=form,
                teacher_user=teacher_user,
                profile=profile,
                available_days=available_days,
            )

        # Calculate session fee snapshot
        rate = float(profile.hourly_rate or 0)
        amount = round(rate * (form.duration_minutes.data / 60.0), 2)

        booking = Booking(
            learner_id=current_user.id,
            teacher_id=teacher_user.id,
            session_date=session_date,
            start_time=start_t,
            end_time=end_t,
            duration_minutes=form.duration_minutes.data,
            topic=form.topic.data.strip(),
            learner_notes=form.learner_notes.data.strip() if form.learner_notes.data else None,
            status="pending",
            amount=amount,
        )
        db.session.add(booking)
        db.session.commit()

        # Send email notification to teacher
        sent = send_new_booking_email(booking)
        if not sent:
            flash(
                "Booking request submitted successfully! [Dev Mode] (Notification logged to console).",
                "success",
            )
        else:
            flash(
                f"Booking request submitted successfully! {teacher_user.full_name} has been notified via email.",
                "success",
            )

        # Send in-app notification to teacher
        notify(
            user_id=booking.teacher_id,
            title=f"New Mentorship Request: {booking.topic}",
            body=f"{current_user.full_name} requested a {booking.duration_minutes}-min session on {booking.session_date.strftime('%b %d, %Y')}.",
            notif_type="booking",
            link=url_for("booking.detail", booking_id=booking.id),
        )

        return redirect(url_for("booking.detail", booking_id=booking.id))

    return render_template(
        "booking/new.html",
        form=form,
        teacher_user=teacher_user,
        profile=profile,
        available_days=available_days,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Booking Detail View
# ─────────────────────────────────────────────────────────────────────────────
@booking_bp.route("/<int:booking_id>")
@login_required
def detail(booking_id: int):
    """
    View full booking details, session timings, notes, and meeting status.
    Only the booking's learner, teacher, or an admin can access.
    """
    booking = Booking.query.get_or_404(booking_id)

    # Permission check
    if current_user.id not in (booking.learner_id, booking.teacher_id) and not current_user.is_admin:
        abort(403)

    is_teacher = (current_user.id == booking.teacher_id)
    is_learner = (current_user.id == booking.learner_id)
    response_form = BookingResponseForm()

    # Payment status check (fetch latest payment row even if refunded)
    payment = booking.payment or Payment.query.filter_by(
        booking_id_ref=booking.id,
    ).order_by(Payment.id.desc()).first()
    has_paid = booking_is_paid(booking)

    # Session completion eligibility
    session_end = datetime.combine(booking.session_date, booking.end_time).replace(tzinfo=NPT)
    is_past = (nepal_now() >= session_end)
    can_mark_complete = (booking.status == "approved" and is_past and has_paid)

    # Review status
    review = booking.review
    can_review = (booking.status == "completed" and is_learner and review is None)
    review_form = ReviewForm() if can_review else None

    # ── Report Admin Status & Context ─────────────────────────────────────────
    my_report = Report.query.filter_by(
        booking_id=booking.id,
        reporter_id=current_user.id,
    ).order_by(Report.id.desc()).first()

    report_against_me = Report.query.filter_by(
        booking_id=booking.id,
        reported_id=current_user.id,
    ).order_by(Report.id.desc()).first()

    pending_report = my_report if (my_report and my_report.status == "pending") else None
    can_report = False
    report_form = None

    if booking.status in ("approved", "completed", "cancelled") and (is_learner or is_teacher):
        # A user can file a report if they do not currently have a pending/reviewed report
        if not (my_report and my_report.status in ("pending", "reviewed")):
            can_report = True
            report_form = ReportForm()
            if is_learner:
                report_form.reason.choices = LEARNER_REPORT_REASONS
            else:
                report_form.reason.choices = TEACHER_REPORT_REASONS

    report_response_form = (
        ReportResponseForm()
        if (report_against_me and report_against_me.status in ("pending", "reviewed"))
        else None
    )

    booking_reports = Report.query.filter_by(booking_id=booking.id).order_by(Report.created_at.desc()).all()

    # Refund request status & eligibility
    latest_refund_req = RefundRequest.query.filter_by(
        booking_id=booking.id
    ).order_by(RefundRequest.id.desc()).first()
    open_refund_req = RefundRequest.query.filter_by(
        booking_id=booking.id,
        status="pending"
    ).first()

    # Misconduct report check (upheld report against learner blocks refund)
    upheld_misconduct = Report.query.filter_by(
        reported_id=booking.learner_id,
        booking_id=booking.id,
        status="resolved",
    ).first()

    can_request_refund = bool(
        is_learner
        and payment
        and payment.status == "success"
        and booking.status in ("cancelled", "approved", "completed")
        and not upheld_misconduct
        and not open_refund_req
    )
    refund_request_form = RefundRequestForm() if can_request_refund else None

    return render_template(
        "booking/detail.html",
        booking=booking,
        is_teacher=is_teacher,
        is_learner=is_learner,
        response_form=response_form,
        payment=payment,
        has_paid=has_paid,
        can_mark_complete=can_mark_complete,
        review=review,
        can_review=can_review,
        review_form=review_form,
        can_report=can_report,
        pending_report=pending_report,
        my_report=my_report,
        report_against_me=report_against_me,
        booking_reports=booking_reports,
        report_form=report_form,
        report_response_form=report_response_form,
        report_reason_dict=REPORT_REASON_DICT,
        refund_request=latest_refund_req,
        open_refund_request=open_refund_req,
        can_request_refund=can_request_refund,
        upheld_misconduct=upheld_misconduct,
        refund_request_form=refund_request_form,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. Approve Booking (Teacher Only)
# ─────────────────────────────────────────────────────────────────────────────
@booking_bp.route("/<int:booking_id>/approve", methods=["POST"])
@login_required
@teacher_required
def approve(booking_id: int):
    """
    Teacher approves a pending booking.
    Generates a unique Jitsi meeting room identifier and notifies the learner.
    """
    booking = Booking.query.get_or_404(booking_id)

    if current_user.id != booking.teacher_id:
        abort(403)

    if booking.status != "pending":
        flash(f"Booking #{booking.id} is already '{booking.status}' and cannot be approved.", "warning")
        return redirect(url_for("booking.detail", booking_id=booking.id))

    booking.status = "approved"
    booking.jitsi_room = f"skillbridge-{booking.id}-{uuid.uuid4().hex[:8]}"

    note = request.form.get("teacher_response_note", "").strip()
    if note:
        booking.teacher_response_note = note

    db.session.commit()

    # Send in-app notification to learner
    is_paid = booking_is_paid(booking)
    if is_paid:
        notif_body = f"{current_user.full_name} has approved your session for {booking.session_date.strftime('%b %d, %Y')} at {booking.start_time.strftime('%I:%M %p')}."
        notif_link = url_for("booking.detail", booking_id=booking.id)
    else:
        pay_url = url_for("payments.checkout", payment_for="booking", target_id=booking.id)
        notif_body = f"{current_user.full_name} has approved your session for {booking.session_date.strftime('%b %d, %Y')} at {booking.start_time.strftime('%I:%M %p')}. Payment of NPR {booking.amount or 0:.2f} is required to unlock your live session."
        notif_link = pay_url

    notify(
        user_id=booking.learner_id,
        title=f"Booking Approved: {booking.topic}",
        body=notif_body,
        notif_type="booking",
        link=notif_link,
    )

    # Send response email to learner
    send_booking_response_email(booking)
    flash("Session approved! The learner has been notified by email.", "success")
    return redirect(url_for("booking.detail", booking_id=booking.id))


# ─────────────────────────────────────────────────────────────────────────────
# 4. Reject Booking (Teacher Only)
# ─────────────────────────────────────────────────────────────────────────────
@booking_bp.route("/<int:booking_id>/reject", methods=["POST"])
@login_required
@teacher_required
def reject(booking_id: int):
    """
    Teacher rejects a pending booking request with an optional note.
    """
    booking = Booking.query.get_or_404(booking_id)

    if current_user.id != booking.teacher_id:
        abort(403)

    if booking.status != "pending":
        flash(f"Booking #{booking.id} is already '{booking.status}' and cannot be rejected.", "warning")
        return redirect(url_for("booking.detail", booking_id=booking.id))

    booking.status = "rejected"
    note = request.form.get("teacher_response_note", "").strip()
    if note:
        booking.teacher_response_note = note

    db.session.commit()

    # Send in-app notification to learner
    notify(
        user_id=booking.learner_id,
        title=f"Booking Request Update: {booking.topic}",
        body=f"{current_user.full_name} was unable to accept your booking request.",
        notif_type="booking",
        link=url_for("booking.detail", booking_id=booking.id),
    )

    # Send response email to learner
    send_booking_response_email(booking)
    flash("Booking request rejected. The learner has been notified.", "info")
    return redirect(url_for("booking.detail", booking_id=booking.id))


# ─────────────────────────────────────────────────────────────────────────────
# 5. Cancel Booking (Learner or Teacher)
# ─────────────────────────────────────────────────────────────────────────────
@booking_bp.route("/<int:booking_id>/cancel", methods=["POST"])
@login_required
def cancel(booking_id: int):
    """
    Learner or Teacher cancels a booking while it is in pending or approved status.
    Payment (if any) is held as 'success' — no auto-refund.
    Both parties are notified that the learner can request a refund from the booking page.
    """
    booking = Booking.query.get_or_404(booking_id)

    if current_user.id not in (booking.learner_id, booking.teacher_id) and not current_user.is_admin:
        abort(403)

    if booking.status not in ("pending", "approved"):
        flash(f"Booking #{booking.id} is currently '{booking.status}' and cannot be cancelled.", "warning")
        return redirect(url_for("booking.detail", booking_id=booking.id))

    booking.status = "cancelled"

    # Check if a successful payment exists for this booking
    payment = booking.payment if (booking.payment and booking.payment.status == "success") else Payment.query.filter_by(
        payment_for="booking",
        booking_id_ref=booking.id,
        status="success",
    ).first()

    db.session.commit()

    if payment:
        # Payment is held — do NOT auto-refund.
        # Notify learner that they can request a refund.
        notify(
            user_id=booking.learner_id,
            title=f"Session Cancelled — Refund Available: {booking.topic or 'Mentorship Session'}",
            body=(
                f"Your booking #{booking.id} has been cancelled by {current_user.full_name}. "
                f"Your payment of NPR {payment.amount:.2f} is held. "
                f"You can request a refund from the booking page."
            ),
            notif_type="payment",
            link=url_for("booking.detail", booking_id=booking.id),
        )
        # Notify teacher too
        if current_user.id == booking.learner_id:
            notify(
                user_id=booking.teacher_id,
                title=f"Session Cancelled: {booking.topic or 'Mentorship Session'}",
                body=(
                    f"{current_user.full_name} has cancelled the booked session "
                    f"scheduled for {booking.session_date.strftime('%b %d, %Y')}. "
                    f"The learner's payment is on hold pending a possible refund request."
                ),
                notif_type="booking",
                link=url_for("booking.detail", booking_id=booking.id),
            )
        else:
            # Teacher cancelled — notify learner (already notified above)
            pass

        flash(
            "The session booking has been cancelled. "
            "Your payment is held — you may request a refund from this booking page.",
            "info",
        )
    else:
        # No payment — just notify the other party about the cancellation
        other_user_id = booking.teacher_id if current_user.id == booking.learner_id else booking.learner_id
        notify(
            user_id=other_user_id,
            title=f"Session Cancelled: {booking.topic or 'Mentorship Session'}",
            body=f"{current_user.full_name} has cancelled the booking for {booking.session_date.strftime('%b %d, %Y')}.",
            notif_type="booking",
            link=url_for("booking.detail", booking_id=booking.id),
        )
        flash("The session booking has been cancelled.", "info")

    return redirect(url_for("booking.detail", booking_id=booking.id))


@booking_bp.route("/<int:booking_id>/refund-request", methods=["POST"])
@login_required
@learner_required
def submit_refund_request(booking_id: int):
    """
    Learner submits a refund request for a booking payment.
    Enforces eligibility: successful unrefunded payment, valid booking status,
    no upheld misconduct report, and at most one open refund request per booking.
    Notifies all administrators upon submission.
    """
    booking = Booking.query.get_or_404(booking_id)

    if current_user.id != booking.learner_id:
        abort(403)

    payment = booking.payment or Payment.query.filter_by(
        booking_id_ref=booking.id,
    ).order_by(Payment.id.desc()).first()

    if not payment or payment.status != "success":
        flash("Only bookings with a successful, unrefunded payment are eligible for refund requests.", "warning")
        return redirect(url_for("booking.detail", booking_id=booking.id))

    if booking.status not in ("cancelled", "approved", "completed"):
        flash(f"Cannot request a refund for a booking with status '{booking.status}'.", "warning")
        return redirect(url_for("booking.detail", booking_id=booking.id))

    # Misconduct report check
    upheld_misconduct = Report.query.filter_by(
        reported_id=booking.learner_id,
        booking_id=booking.id,
        status="resolved",
    ).first()
    if upheld_misconduct:
        flash("You are not eligible to request a refund due to an upheld misconduct report for this session.", "danger")
        return redirect(url_for("booking.detail", booking_id=booking.id))

    # One open request per booking
    existing_open = RefundRequest.query.filter_by(
        booking_id=booking.id,
        status="pending",
    ).first()
    if existing_open:
        flash("A refund request is already pending review for this booking.", "warning")
        return redirect(url_for("booking.detail", booking_id=booking.id))

    form = RefundRequestForm()
    if form.validate_on_submit():
        refund_req = RefundRequest(
            booking_id=booking.id,
            learner_id=current_user.id,
            reason_type=form.reason_type.data,
            description=(form.description.data or "").strip() or None,
            status="pending",
        )
        db.session.add(refund_req)
        db.session.commit()

        # Notify all admins
        reason_label = dict(REFUND_REASON_CHOICES).get(form.reason_type.data, form.reason_type.data)
        admins = User.query.filter_by(role="admin").all()
        for adm in admins:
            notify(
                user_id=adm.id,
                title=f"New Refund Request: Booking #{booking.id}",
                body=(
                    f"Learner {current_user.full_name} submitted a refund request for "
                    f"Booking #{booking.id} ({booking.topic or 'Mentorship Session'}).\n"
                    f"Reason: {reason_label}."
                ),
                notif_type="payment",
                link=f"/admin/refunds/{refund_req.id}",
            )

        flash("Your refund request has been submitted and is under administrative review.", "success")
    else:
        flash("Please select a valid refund reason.", "danger")

    return redirect(url_for("booking.detail", booking_id=booking.id))


# ─────────────────────────────────────────────────────────────────────────────
# 6. Complete Booking (Learner or Teacher)
# ─────────────────────────────────────────────────────────────────────────────
@booking_bp.route("/<int:booking_id>/complete", methods=["POST"])
@login_required
def complete(booking_id: int):
    """
    Learner or Teacher marks an approved booking as completed once the scheduled
    session date and end time has passed.
    """
    booking = Booking.query.get_or_404(booking_id)

    if current_user.id not in (booking.learner_id, booking.teacher_id) and not current_user.is_admin:
        abort(403)

    if booking.status != "approved":
        flash(f"Booking #{booking.id} cannot be marked complete because its current status is '{booking.status}'.", "warning")
        return redirect(url_for("booking.detail", booking_id=booking.id))

    if not booking_is_paid(booking):
        flash("This session cannot be marked complete because payment has not been received.", "warning")
        return redirect(url_for("booking.detail", booking_id=booking.id))

    session_end = datetime.combine(booking.session_date, booking.end_time).replace(tzinfo=NPT)
    if nepal_now() < session_end:
        flash("This session cannot be marked complete before its scheduled end time has elapsed.", "warning")
        return redirect(url_for("booking.detail", booking_id=booking.id))

    booking.status = "completed"
    db.session.commit()

    flash("Session marked as completed! You can now submit your rating and review.", "success")
    return redirect(url_for("booking.detail", booking_id=booking.id))


# ─────────────────────────────────────────────────────────────────────────────
# 6. Booking History (Learner & Teacher)
# ─────────────────────────────────────────────────────────────────────────────
@booking_bp.route("/history")
@login_required
def history():
    """
    Paginated list of bookings for the current user with status filtering.
    """
    status_filter = request.args.get("status", "all").strip().lower()
    page = request.args.get("page", 1, type=int)

    if current_user.is_teacher:
        base_query = Booking.query.filter_by(teacher_id=current_user.id)
    else:
        base_query = Booking.query.filter_by(learner_id=current_user.id)

    # Compute status counts for filter tabs
    status_counts = {
        "all": base_query.count(),
        "pending": base_query.filter_by(status="pending").count(),
        "approved": base_query.filter_by(status="approved").count(),
        "rejected": base_query.filter_by(status="rejected").count(),
        "cancelled": base_query.filter_by(status="cancelled").count(),
        "completed": base_query.filter_by(status="completed").count(),
    }

    query = base_query
    if status_filter in ("pending", "approved", "rejected", "cancelled", "completed"):
        query = query.filter(Booking.status == status_filter)

    query = query.order_by(
        Booking.session_date.desc(),
        Booking.start_time.desc(),
        Booking.id.desc(),
    )

    pagination = query.paginate(page=page, per_page=10, error_out=False)

    return render_template(
        "booking/history.html",
        pagination=pagination,
        bookings=pagination.items,
        status_filter=status_filter,
        status_counts=status_counts,
        is_teacher=current_user.is_teacher,
    )

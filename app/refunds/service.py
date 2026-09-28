"""
app/refunds/service.py — Central Refund Processing Service

process_refund(payment, amount, admin, note) is the single function
used by every refund path in the platform. It enforces all business rules
and side-effects in one place so they cannot be bypassed.

Business rules
--------------
1. payment.status must be 'success'  (no double-refunds)
2. 0 < amount <= payment.amount
3. If the LEARNER for this booking has a Report against them with
   status='resolved' → refuse the refund entirely.
   If the report is pending/reviewed → warn the admin but allow.
4. Effects on payment:
     status          → 'refunded'
     refund_amount   → amount
     refunded_at     → now (UTC)
     refunded_by     → admin.id
     refund_note     → note
     platform_fee_amount → payment.amount - amount  (whole retained remainder)
     teacher_payout_amount → 0
5. If payout_status was already 'released', process the refund but
   return a loud reconciliation warning in the result dict.
6. Notifications:
     Learner — amount refunded, original amount, session topic/teacher/date+time
     Teacher — admin refunded the student's payment, same session details + retained amount
   All datetimes shown via the npt filter (Nepal time).
"""

from datetime import datetime
from decimal import Decimal

from app import db
from app.models import Booking, Payment, Report, User
from app.notifications.utils import notify
from app.utils.time import to_nepal


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _format_npt(dt) -> str:
    """Format a UTC datetime in Nepal time for notification text."""
    if dt is None:
        return "N/A"
    return to_nepal(dt).strftime("%b %d, %Y %I:%M %p NPT")


def _get_booking_for_payment(payment: Payment):
    """Return the Booking linked to this payment, or None."""
    if payment.payment_for == "booking":
        if payment.booking_id_ref:
            booking = Booking.query.get(payment.booking_id_ref)
            if booking:
                return booking
        return Booking.query.filter_by(payment_id=payment.id).first()
    return None


def get_payment_hold_reason(payment: Payment):
    """
    Check if a payment is blocked from payout release to the teacher.
    Returns a human-readable reason string if on hold, or None if releasable.

    Hold conditions:
    1. Payment status is not 'success'
    2. Linked booking is cancelled
    3. Open refund request exists for this booking (status == 'pending')
    4. Open report exists for this booking (status in ('pending', 'reviewed'))
    """
    if payment.status != "success":
        return f"Payment is {payment.status}"

    if payment.payment_for == "booking":
        booking = _get_booking_for_payment(payment)
        if booking:
            if booking.status == "cancelled":
                return "Booking cancelled"

            from app.models import RefundRequest
            open_req = RefundRequest.query.filter_by(
                booking_id=booking.id,
                status="pending",
            ).first()
            if open_req:
                return "Open refund request"

            open_report = Report.query.filter(
                Report.booking_id == booking.id,
                Report.status.in_(["pending", "reviewed"]),
            ).first()
            if open_report:
                return f"Open report (#{open_report.id})"

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Main service function
# ─────────────────────────────────────────────────────────────────────────────

def process_refund(
    payment: Payment,
    amount: Decimal,
    admin: User,
    note: str,
) -> dict:
    """
    Process a refund for a payment record.

    Parameters
    ----------
    payment : Payment  — the payment row to refund
    amount  : Decimal  — NPR amount to refund to learner
    admin   : User     — the admin processing the refund
    note    : str      — admin note / reason

    Returns
    -------
    dict with keys:
        success       bool
        error         str | None        — human-readable error message
        warning       str | None        — non-fatal warning (e.g. payout conflict)
        payment       Payment | None    — updated payment row (on success)
    """
    amount = Decimal(str(amount))

    # ── 1. Status guard ───────────────────────────────────────────────────────
    if payment.status != "success":
        return {
            "success": False,
            "error": (
                f"Payment #{payment.id} cannot be refunded: "
                f"its current status is '{payment.status}'. "
                "Only payments with status 'success' are eligible for refund."
            ),
            "warning": None,
            "payment": None,
        }

    # ── 2. Amount bounds ──────────────────────────────────────────────────────
    gross = Decimal(str(payment.amount))
    if amount <= 0 or amount > gross:
        return {
            "success": False,
            "error": (
                f"Refund amount NPR {amount:.2f} is invalid. "
                f"Must be greater than 0 and at most NPR {gross:.2f} (the original payment)."
            ),
            "warning": None,
            "payment": None,
        }

    # ── 3. Learner misconduct check ───────────────────────────────────────────
    booking = _get_booking_for_payment(payment)
    learner_id = payment.learner_id
    misconduct_warning = None

    if booking:
        # Look for reports AGAINST the learner (reported_id == learner_id) for this booking
        upheld_report = Report.query.filter_by(
            reported_id=learner_id,
            booking_id=booking.id,
            status="resolved",
        ).first()

        if upheld_report:
            return {
                "success": False,
                "error": (
                    f"Refund blocked: learner has an upheld misconduct report "
                    f"(Report #{upheld_report.id}) for this booking. "
                    "Students with resolved misconduct reports are not eligible for refunds."
                ),
                "warning": None,
                "payment": None,
            }

        # Pending / reviewed report: warn but allow
        pending_report = Report.query.filter(
            Report.reported_id == learner_id,
            Report.booking_id == booking.id,
            Report.status.in_(["pending", "reviewed"]),
        ).first()
        if pending_report:
            misconduct_warning = (
                f"Warning: there is an open misconduct report (Report #{pending_report.id}, "
                f"status='{pending_report.status}') against this learner for this booking. "
                "The refund has been processed, but you may want to review the report first."
            )

    # ── 4. Payout-already-released check ─────────────────────────────────────
    payout_warning = None
    if payment.payout_status == "released":
        released_date = (
            _format_npt(payment.payout_released_at)
            if payment.payout_released_at
            else "unknown date"
        )
        payout_warning = (
            f"RECONCILIATION REQUIRED: The teacher payout for Payment #{payment.id} "
            f"(NPR {payment.teacher_payout_amount}) was already released on {released_date}. "
            "The internal refund record has been created, but the teacher has already "
            "received the funds. Offline reconciliation with the teacher is required — "
            "this is an internal record only, no eSewa money movement has occurred."
        )

    # ── 5. Apply refund effects ───────────────────────────────────────────────
    retained = gross - amount  # whole retained remainder → platform earnings

    payment.status = "refunded"
    payment.refund_amount = amount
    payment.refunded_at = datetime.utcnow()
    payment.refunded_by = admin.id
    payment.refund_note = (note or "").strip() or None
    payment.platform_fee_amount = retained    # everything not refunded is platform earnings
    payment.teacher_payout_amount = Decimal("0.00")

    db.session.commit()

    # ── 6. Notifications ──────────────────────────────────────────────────────
    _send_refund_notifications(payment, booking, amount, retained, admin)

    # ── 7. Compose result ─────────────────────────────────────────────────────
    warning_parts = []
    if misconduct_warning:
        warning_parts.append(misconduct_warning)
    if payout_warning:
        warning_parts.append(payout_warning)

    return {
        "success": True,
        "error": None,
        "warning": "\n\n".join(warning_parts) if warning_parts else None,
        "payment": payment,
    }


def _send_refund_notifications(
    payment: Payment,
    booking,        # Booking | None
    amount: Decimal,
    retained: Decimal,
    admin: User,
) -> None:
    """Send in-app notifications to learner and teacher after a refund."""
    from flask import url_for, has_request_context

    # Booking context strings
    if booking:
        teacher_name = booking.teacher.full_name if booking.teacher else "your instructor"
        topic = booking.topic or "Mentorship Session"
        session_date_str = booking.session_date.strftime("%b %d, %Y") if booking.session_date else "N/A"
        session_time_str = (
            f"{booking.start_time.strftime('%I:%M %p')} – {booking.end_time.strftime('%I:%M %p')}"
            if booking.start_time and booking.end_time
            else "N/A"
        )
        booking_link = (
            url_for("booking.detail", booking_id=booking.id)
            if has_request_context()
            else f"/booking/{booking.id}"
        )
        teacher_id = booking.teacher_id
    else:
        teacher_name = "your instructor"
        topic = payment.item_title or "Payment"
        session_date_str = "N/A"
        session_time_str = "N/A"
        booking_link = (
            url_for("payments.receipt", payment_id=payment.id)
            if has_request_context()
            else f"/payments/{payment.id}/receipt"
        )
        teacher_id = None

    refunded_at_str = _format_npt(payment.refunded_at)

    # ── Learner notification ─────────────────────────────────────────────────
    learner_body = (
        f"An administrator has issued a refund of NPR {amount:.2f} "
        f"from your original payment of NPR {payment.amount:.2f}.\n\n"
        f"Session: {topic}\n"
        f"Mentor: {teacher_name}\n"
        f"Date: {session_date_str} · {session_time_str}\n"
        f"Processed at: {refunded_at_str}\n\n"
        f"Note: This is an internal accounting record only — "
        f"no eSewa money movement has been triggered by this action."
    )
    notify(
        user_id=payment.learner_id,
        title=f"Refund Issued: NPR {amount:.2f} of NPR {payment.amount:.2f}",
        body=learner_body,
        notif_type="payment",
        link=booking_link,
    )

    # ── Teacher notification ─────────────────────────────────────────────────
    if teacher_id:
        teacher_body = (
            f"An administrator has refunded NPR {amount:.2f} of the student's payment "
            f"of NPR {payment.amount:.2f} for your session.\n\n"
            f"Session: {topic}\n"
            f"Date: {session_date_str} · {session_time_str}\n"
            f"Refund to learner: NPR {amount:.2f}\n"
            f"Retained by platform: NPR {retained:.2f}\n"
            f"Your payout for this session: NPR 0.00\n"
            f"Processed at: {refunded_at_str}\n\n"
            f"Note: This is an internal accounting record only — "
            f"no eSewa money movement has been triggered by this action."
        )
        notify(
            user_id=teacher_id,
            title=f"Session Payment Refunded by Admin: {topic}",
            body=teacher_body,
            notif_type="payment",
            link=booking_link,
        )

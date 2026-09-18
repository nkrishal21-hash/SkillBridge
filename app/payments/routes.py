"""
app/payments/routes.py — Payments Blueprint
Handles checkout initiation, signed eSewa forms, callback processing,
defense-in-depth status verification, order fulfillment, and receipts.
"""

import base64
import json
import uuid
from datetime import datetime
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    abort,
    current_app,
)
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import Payment, Course, Booking, Enrollment, User
from app.auth.utils import learner_required
from app.payments.utils import (
    build_esewa_signature,
    verify_esewa_callback,
    check_esewa_status,
)

payments_bp = Blueprint("payments", __name__)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Checkout Initiation
# ─────────────────────────────────────────────────────────────────────────────
@payments_bp.route("/checkout/<payment_for>/<int:target_id>")
@login_required
@learner_required
def checkout(payment_for: str, target_id: int):
    """
    Render checkout summary and auto-signed eSewa payment form.
    payment_for: 'course' or 'booking'
    target_id: course_id or booking_id
    """
    if payment_for not in ("course", "booking"):
        abort(404)

    target = None
    item_title = ""
    item_type = ""
    instructor_name = ""
    amount_val = 0.0

    if payment_for == "course":
        course = Course.query.get_or_404(target_id)
        target = course

        # Reject if already enrolled
        existing_enrollment = Enrollment.query.filter_by(
            learner_id=current_user.id,
            course_id=course.id
        ).first()
        if existing_enrollment:
            flash("You are already enrolled in this course! Access your lessons below.", "info")
            return redirect(url_for("courses.course_detail", course_id=course.id))

        # Reject if free
        if not course.price or course.price <= 0:
            flash("This course is free. You can enroll directly with no payment required.", "info")
            return redirect(url_for("courses.enroll", course_id=course.id))

        amount_val = float(course.price)
        item_title = course.title
        item_type = "Course Lifetime Access"
        instructor_name = (
            course.teacher.user.full_name
            if (course.teacher and course.teacher.user)
            else "SkillBridge Instructor"
        )

        # Reuse existing initiated payment or create new
        payment = Payment.query.filter_by(
            learner_id=current_user.id,
            payment_for="course",
            course_id=course.id,
            status="initiated"
        ).order_by(Payment.id.desc()).first()

        if not payment:
            payment = Payment(
                learner_id=current_user.id,
                payment_for="course",
                course_id=course.id,
                amount=course.price,
                gateway="esewa",
                status="initiated"
            )
            db.session.add(payment)
            db.session.flush()

        payment.amount = course.price
        payment.gateway_reference_id = f"SKB-C{course.id}-P{payment.id}-{uuid.uuid4().hex[:6]}"
        db.session.commit()

    elif payment_for == "booking":
        booking = Booking.query.get_or_404(target_id)
        target = booking

        # Learner ownership check
        if booking.learner_id != current_user.id:
            abort(403)

        # Reject if not approved
        if booking.status != "approved":
            flash("Sessions can only be paid for after your mentor has reviewed and approved the request.", "warning")
            return redirect(url_for("booking.detail", booking_id=booking.id))

        # Reject if already paid
        paid_record = Payment.query.filter_by(
            booking_id_ref=booking.id,
            status="success"
        ).first()
        if paid_record:
            flash("This session has already been paid for and confirmed.", "info")
            return redirect(url_for("booking.detail", booking_id=booking.id))

        if not booking.amount or booking.amount <= 0:
            flash("Session fee is NPR 0.00. No payment is required.", "info")
            return redirect(url_for("booking.detail", booking_id=booking.id))

        amount_val = float(booking.amount)
        item_title = f"1-on-1 Mentorship: {booking.topic}"
        item_type = f"Mentorship Session ({booking.duration_minutes} mins)"
        instructor_name = booking.teacher.full_name

        # Reuse existing initiated payment or create new
        payment = Payment.query.filter_by(
            learner_id=current_user.id,
            payment_for="booking",
            booking_id_ref=booking.id,
            status="initiated"
        ).order_by(Payment.id.desc()).first()

        if not payment:
            payment = Payment(
                learner_id=current_user.id,
                payment_for="booking",
                booking_id_ref=booking.id,
                amount=booking.amount,
                gateway="esewa",
                status="initiated"
            )
            db.session.add(payment)
            db.session.flush()

        payment.amount = booking.amount
        payment.gateway_reference_id = f"SKB-B{booking.id}-P{payment.id}-{uuid.uuid4().hex[:6]}"
        db.session.commit()

    # Build signed eSewa form fields
    total_amount_str = f"{amount_val:.2f}"
    product_code = current_app.config.get("ESEWA_MERCHANT_CODE", "EPAYTEST")
    transaction_uuid = payment.gateway_reference_id

    signature = build_esewa_signature(total_amount_str, transaction_uuid, product_code)

    esewa_form = {
        "amount": total_amount_str,
        "tax_amount": "0",
        "total_amount": total_amount_str,
        "transaction_uuid": transaction_uuid,
        "product_code": product_code,
        "product_service_charge": "0",
        "product_delivery_charge": "0",
        "success_url": url_for("payments.esewa_success", _external=True),
        "failure_url": url_for("payments.esewa_failure", _external=True),
        "signed_field_names": "total_amount,transaction_uuid,product_code",
        "signature": signature,
    }

    gateway_url = current_app.config.get(
        "ESEWA_GATEWAY_URL",
        "https://rc-epay.esewa.com.np/api/epay/main/v2/form"
    )

    return render_template(
        "payments/checkout.html",
        payment=payment,
        target=target,
        payment_for=payment_for,
        item_title=item_title,
        item_type=item_type,
        instructor_name=instructor_name,
        total_amount=total_amount_str,
        esewa_form=esewa_form,
        gateway_url=gateway_url,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. eSewa Success Callback
# ─────────────────────────────────────────────────────────────────────────────
@payments_bp.route("/esewa/success")
def esewa_success():
    """
    Handle return redirect from eSewa upon successful payment.
    Decodes ?data=<base64>, verifies HMAC signature, queries eSewa's status API,
    marks Payment status='success', and fulfills course enrollment or booking confirmation.
    """
    data = request.args.get("data")
    if not data:
        flash("No transaction data received from eSewa.", "danger")
        return render_template("payments/failure.html", error_message="Missing callback payload from payment gateway.")

    try:
        decoded_bytes = base64.b64decode(data)
        decoded_json = decoded_bytes.decode("utf-8")
        payload = json.loads(decoded_json)
    except Exception as exc:
        print(f"[SkillBridge Payment] Payload decode failed: {exc}")
        return render_template("payments/failure.html", error_message="Corrupted response data from eSewa.")

    transaction_uuid = payload.get("transaction_uuid")
    if not transaction_uuid:
        return render_template("payments/failure.html", error_message="Transaction reference missing in gateway response.")

    payment = Payment.query.filter_by(gateway_reference_id=transaction_uuid).first()
    if not payment:
        return render_template("payments/failure.html", error_message=f"Order '{transaction_uuid}' not found.")

    # Idempotency: if already marked success, render receipt view
    if payment.status == "success":
        return render_template("payments/success.html", payment=payment)

    # 1. Signature Verification
    if not verify_esewa_callback(payload):
        payment.status = "failed"
        db.session.commit()
        return render_template(
            "payments/failure.html",
            payment=payment,
            error_message="Security signature verification failed. Transaction response could not be verified."
        )

    # 2. Defense-in-depth Status Check API call
    product_code = payload.get("product_code", current_app.config.get("ESEWA_MERCHANT_CODE", "EPAYTEST"))
    total_amount = payload.get("total_amount", f"{float(payment.amount):.2f}")

    status_data = check_esewa_status(product_code, total_amount, transaction_uuid)
    gw_status = status_data.get("status")

    if gw_status != "COMPLETE":
        payment.status = "failed"
        db.session.commit()
        return render_template(
            "payments/failure.html",
            payment=payment,
            error_message=f"Gateway transaction status check did not return COMPLETE (received: {gw_status or 'ERROR'}). Order has not been charged."
        )

    # 3. Finalize Payment & Fulfill Order
    payment.status = "success"
    payment.gateway_transaction_id = payload.get("transaction_code") or status_data.get("ref_id")
    payment.completed_at = datetime.utcnow()

    if payment.payment_for == "course":
        try:
            existing_enroll = Enrollment.query.filter_by(
                learner_id=payment.learner_id,
                course_id=payment.course_id
            ).first()
            if not existing_enroll:
                enrollment = Enrollment(
                    learner_id=payment.learner_id,
                    course_id=payment.course_id,
                    payment_id=payment.id,
                    completed_lessons="",
                    progress_percent=0,
                )
                db.session.add(enrollment)
            else:
                existing_enroll.payment_id = payment.id
        except IntegrityError:
            db.session.rollback()

    elif payment.payment_for == "booking":
        booking = Booking.query.get(payment.booking_id_ref)
        if booking:
            booking.payment_id = payment.id

    db.session.commit()
    flash("🎉 Payment successful! Your order has been confirmed.", "success")
    return render_template("payments/success.html", payment=payment)


# ─────────────────────────────────────────────────────────────────────────────
# 3. eSewa Failure Callback
# ─────────────────────────────────────────────────────────────────────────────
@payments_bp.route("/esewa/failure")
def esewa_failure():
    """
    Handle return redirect from eSewa when user cancels or payment fails.
    eSewa's failure redirect carries little data; handles this gracefully without 500.
    """
    data = request.args.get("data")
    payment = None

    if data:
        try:
            decoded_bytes = base64.b64decode(data)
            payload = json.loads(decoded_bytes.decode("utf-8"))
            transaction_uuid = payload.get("transaction_uuid")
            if transaction_uuid:
                payment = Payment.query.filter_by(gateway_reference_id=transaction_uuid).first()
        except Exception:
            pass

    # If no data param, check if reference ID was passed as query param
    if not payment:
        ref = request.args.get("transaction_uuid") or request.args.get("ref")
        if ref:
            payment = Payment.query.filter_by(gateway_reference_id=ref).first()

    if payment and payment.status == "initiated":
        payment.status = "failed"
        db.session.commit()

    return render_template(
        "payments/failure.html",
        payment=payment,
        error_message="Payment was cancelled or could not be completed by eSewa."
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. Payment Receipt View
# ─────────────────────────────────────────────────────────────────────────────
@payments_bp.route("/receipt/<int:payment_id>")
@login_required
def receipt(payment_id: int):
    """
    Display a printable receipt for a completed transaction.
    Only the paying learner or an administrator can view.
    """
    payment = Payment.query.get_or_404(payment_id)

    if payment.learner_id != current_user.id and not current_user.is_admin:
        abort(403)

    return render_template("payments/receipt.html", payment=payment)

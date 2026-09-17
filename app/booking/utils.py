"""
app/booking/utils.py — Booking System Email Utilities
Provides email notifications for session booking workflows with graceful
fallback to console logging in development environments.
"""

from datetime import datetime, timedelta, time as dtime
from flask import current_app, url_for
from flask_mail import Message
from app import mail
from app.models import Booking


def calculate_session_times(session_date, start_time_str: str, duration_minutes: int) -> tuple[dtime, dtime]:
    """
    Parse start time string (HH:MM) and duration minutes into
    Python datetime.time start and end objects.
    """
    hour, minute = [int(p) for p in start_time_str.split(":")]
    start_t = dtime(hour=hour, minute=minute)

    # Combine with date to handle duration rollover correctly
    start_dt = datetime.combine(session_date, start_t)
    end_dt = start_dt + timedelta(minutes=duration_minutes)
    end_t = end_dt.time()

    return start_t, end_t


def send_new_booking_email(booking: Booking) -> bool:
    """
    Send email notification to teacher regarding a new 1-on-1 booking request.
    Gracefully logs details to console first so local dev testing works without SMTP.
    Returns True if sent via SMTP, False otherwise.
    """
    detail_url = url_for("booking.detail", booking_id=booking.id, _external=True)

    # Always log to console for dev convenience
    print(f"\n[SkillBridge Booking] New 1-on-1 Request for Teacher {booking.teacher.email}:")
    print(f"  Learner: {booking.learner.full_name} ({booking.learner.email})")
    print(f"  Topic: {booking.topic}")
    print(f"  Date & Time: {booking.session_date} {booking.start_time.strftime('%I:%M %p')} - {booking.end_time.strftime('%I:%M %p')}")
    print(f"  Duration: {booking.duration_minutes} mins (Amount: NPR {booking.amount or 0:.2f})")
    print(f"  Review URL: {detail_url}\n")

    mail_user = current_app.config.get("MAIL_USERNAME")
    if not mail_user or "your-gmail" in str(mail_user):
        return False

    try:
        msg = Message(
            subject=f"SkillBridge — New Mentorship Request: {booking.topic}",
            sender=current_app.config.get("MAIL_DEFAULT_SENDER", mail_user),
            recipients=[booking.teacher.email],
        )
        msg.html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 580px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 12px; background: #ffffff;">
            <div style="text-align: center; margin-bottom: 24px;">
                <h2 style="color: #4f46e5; margin: 0; font-size: 24px; font-weight: 700;">SkillBridge</h2>
                <p style="color: #64748b; font-size: 14px; margin-top: 4px;">Mentorship Booking Request</p>
            </div>
            <p style="color: #1e293b; font-size: 16px;">Hello <strong>{booking.teacher.full_name}</strong>,</p>
            <p style="color: #475569; font-size: 15px; line-height: 1.6;">
                <strong>{booking.learner.full_name}</strong> has requested a 1-on-1 mentorship session with you.
            </p>
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; margin: 20px 0;">
                <div style="margin-bottom: 8px;"><strong>Topic:</strong> {booking.topic}</div>
                <div style="margin-bottom: 8px;"><strong>Date:</strong> {booking.session_date.strftime('%A, %B %d, %Y')}</div>
                <div style="margin-bottom: 8px;"><strong>Time:</strong> {booking.start_time.strftime('%I:%M %p')} – {booking.end_time.strftime('%I:%M %p')} ({booking.duration_minutes} mins)</div>
                <div><strong>Fee:</strong> NPR {booking.amount or 0:.2f}</div>
                {f'<div style="margin-top: 10px; padding-top: 10px; border-top: 1px dashed #cbd5e1; font-size: 14px; color: #475569;"><em>"{booking.learner_notes}"</em></div>' if booking.learner_notes else ''}
            </div>
            <div style="text-align: center; margin: 28px 0;">
                <a href="{detail_url}" style="background-color: #4f46e5; color: #ffffff; padding: 12px 26px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 15px; display: inline-block;">
                    Review &amp; Respond
                </a>
            </div>
            <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 24px 0;">
            <p style="color: #94a3b8; font-size: 12px; text-align: center;">
                SkillBridge &bull; Peer-to-Peer Learning Platform
            </p>
        </div>
        """
        mail.send(msg)
        return True
    except Exception as exc:
        print(f"[SkillBridge Booking] Could not send email via SMTP: {exc}")
        return False


def send_booking_response_email(booking: Booking) -> bool:
    """
    Send email notification to learner when teacher approves or rejects their booking request.
    Gracefully logs details to console first.
    Returns True if sent via SMTP, False otherwise.
    """
    detail_url = url_for("booking.detail", booking_id=booking.id, _external=True)

    print(f"\n[SkillBridge Booking] Booking #{booking.id} Status Updated to '{booking.status.upper()}' for Learner {booking.learner.email}:")
    print(f"  Teacher: {booking.teacher.full_name}")
    print(f"  Topic: {booking.topic}")
    if booking.status == "approved":
        print(f"  Jitsi Room: {booking.jitsi_room}")
    if booking.teacher_response_note:
        print(f"  Teacher Note: {booking.teacher_response_note}")
    print(f"  Detail URL: {detail_url}\n")

    mail_user = current_app.config.get("MAIL_USERNAME")
    if not mail_user or "your-gmail" in str(mail_user):
        return False

    try:
        if booking.status == "approved":
            subject = f"SkillBridge — Booking Approved: {booking.topic}"
            status_text = f"Great news! <strong>{booking.teacher.full_name}</strong> has approved your 1-on-1 mentorship session."
            jitsi_note = f"""
            <div style="background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px; padding: 14px; margin-top: 14px; color: #065f46; font-size: 14px;">
                <strong>Session Link:</strong> Room ID <code>{booking.jitsi_room}</code> will be activated for your live video call at the scheduled time.
            </div>
            """
        else:
            subject = f"SkillBridge — Booking Request Update: {booking.topic}"
            status_text = f"<strong>{booking.teacher.full_name}</strong> was unable to accept your booking request for the scheduled time."
            jitsi_note = ""

        teacher_note_html = ""
        if booking.teacher_response_note:
            teacher_note_html = f"""
            <div style="margin-top: 14px; padding: 12px; background: #f8fafc; border-radius: 6px; border-left: 4px solid #cbd5e1; font-size: 14px; color: #334155;">
                <strong>Message from Instructor:</strong><br>{booking.teacher_response_note}
            </div>
            """

        msg = Message(
            subject=subject,
            sender=current_app.config.get("MAIL_DEFAULT_SENDER", mail_user),
            recipients=[booking.learner.email],
        )
        msg.html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 580px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 12px; background: #ffffff;">
            <div style="text-align: center; margin-bottom: 24px;">
                <h2 style="color: #4f46e5; margin: 0; font-size: 24px; font-weight: 700;">SkillBridge</h2>
                <p style="color: #64748b; font-size: 14px; margin-top: 4px;">Session Status Notification</p>
            </div>
            <p style="color: #1e293b; font-size: 16px;">Hello <strong>{booking.learner.full_name}</strong>,</p>
            <p style="color: #475569; font-size: 15px; line-height: 1.6;">
                {status_text}
            </p>
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; margin: 20px 0;">
                <div style="margin-bottom: 8px;"><strong>Topic:</strong> {booking.topic}</div>
                <div style="margin-bottom: 8px;"><strong>Date:</strong> {booking.session_date.strftime('%A, %B %d, %Y')}</div>
                <div style="margin-bottom: 8px;"><strong>Time:</strong> {booking.start_time.strftime('%I:%M %p')} – {booking.end_time.strftime('%I:%M %p')}</div>
                <div><strong>Status:</strong> <span style="text-transform: uppercase; font-weight: 700;">{booking.status}</span></div>
                {jitsi_note}
                {teacher_note_html}
            </div>
            <div style="text-align: center; margin: 28px 0;">
                <a href="{detail_url}" style="background-color: #4f46e5; color: #ffffff; padding: 12px 26px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 15px; display: inline-block;">
                    View Booking Details
                </a>
            </div>
            <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 24px 0;">
            <p style="color: #94a3b8; font-size: 12px; text-align: center;">
                SkillBridge &bull; Peer-to-Peer Learning Platform
            </p>
        </div>
        """
        mail.send(msg)
        return True
    except Exception as exc:
        print(f"[SkillBridge Booking] Could not send email via SMTP: {exc}")
        return False

"""
app/certificates/utils.py — ReportLab PDF Certificate Generation & Storage
Handles generation of branded course completion certificates and uploading to
Cloudinary with a graceful local disk fallback.
"""

import os
import io
from uuid import uuid4
from datetime import datetime
from flask import current_app, url_for, has_request_context
from reportlab.lib import pagesizes, colors
from reportlab.pdfgen import canvas
import cloudinary.uploader

from app.models import Certificate, Enrollment


def _is_cloudinary_configured() -> bool:
    """Check if valid Cloudinary credentials exist in current_app config."""
    cloud_name = current_app.config.get("CLOUDINARY_CLOUD_NAME")
    api_key = current_app.config.get("CLOUDINARY_API_KEY")
    api_secret = current_app.config.get("CLOUDINARY_API_SECRET")

    return bool(
        cloud_name
        and api_key
        and api_secret
        and "your-" not in str(cloud_name).lower()
    )


def generate_certificate_code() -> str:
    """
    Generate a unique certificate verification code formatted like:
    SKB-CERT-XXXXXXXXXX (10 hex characters).
    Guarantees uniqueness against the certificates table.
    """
    while True:
        code = f"SKB-CERT-{uuid4().hex[:10].upper()}"
        existing = Certificate.query.filter_by(certificate_code=code).first()
        if not existing:
            return code


def generate_certificate_pdf(learner, course, certificate_code: str) -> bytes:
    """
    Build a clean, beautifully formatted landscape single-page PDF certificate
    using ReportLab canvas.
    
    Includes:
    - SkillBridge branding / title
    - "Certificate of Completion"
    - Learner full name
    - Course title
    - Teacher full name
    - Completion date (from Enrollment or current time)
    - Anti-fraud verification code & verification URL notice
    
    Returns raw PDF bytes.
    """
    buffer = io.BytesIO()

    # Landscape A4 dimensions: 841.89 pt width x 595.27 pt height
    width, height = pagesizes.landscape(pagesizes.A4)
    c = canvas.Canvas(buffer, pagesize=(width, height))
    c.setTitle(f"SkillBridge Certificate - {course.title}")

    # Color palette
    primary_color = colors.HexColor("#4F46E5")      # Indigo 600
    primary_dark = colors.HexColor("#312E81")       # Indigo 900
    gold_accent = colors.HexColor("#D97706")        # Amber 600
    gold_light = colors.HexColor("#FDE68A")         # Amber 200
    text_dark = colors.HexColor("#0F172A")          # Slate 900
    text_muted = colors.HexColor("#64748B")         # Slate 500
    border_color = colors.HexColor("#E2E8F0")       # Slate 200

    # 1. Background fill
    c.setFillColor(colors.HexColor("#FAFAFC"))
    c.rect(0, 0, width, height, fill=True, stroke=False)

    # 2. Outer decorative double border
    c.setStrokeColor(primary_color)
    c.setLineWidth(4)
    c.rect(24, 24, width - 48, height - 48, fill=False, stroke=True)

    c.setStrokeColor(gold_accent)
    c.setLineWidth(1.5)
    c.rect(32, 32, width - 64, height - 64, fill=False, stroke=True)

    # Inner subtle corner marks
    corner_len = 20
    c.setStrokeColor(primary_dark)
    c.setLineWidth(1)
    # Top-left
    c.line(40, height - 40, 40 + corner_len, height - 40)
    c.line(40, height - 40, 40, height - 40 - corner_len)
    # Top-right
    c.line(width - 40, height - 40, width - 40 - corner_len, height - 40)
    c.line(width - 40, height - 40, width - 40, height - 40 - corner_len)
    # Bottom-left
    c.line(40, 40, 40 + corner_len, 40)
    c.line(40, 40, 40, 40 + corner_len)
    # Bottom-right
    c.line(width - 40, 40, width - 40 - corner_len, 40)
    c.line(width - 40, 40, width - 40, 40 + corner_len)

    # 3. Header Branding
    center_x = width / 2.0
    c.setFillColor(primary_color)
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(center_x, height - 85, "SKILLBRIDGE LEARNING PLATFORM")

    c.setFillColor(gold_accent)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(center_x, height - 102, "PEER-TO-PEER MENTORSHIP & SKILL ACCELERATION")

    # Thin accent divider
    c.setStrokeColor(gold_light)
    c.setLineWidth(1)
    c.line(center_x - 140, height - 114, center_x + 140, height - 114)

    # 4. Certificate Title
    c.setFillColor(text_dark)
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(center_x, height - 156, "CERTIFICATE OF COMPLETION")

    c.setFillColor(text_muted)
    c.setFont("Helvetica", 13)
    c.drawCentredString(center_x, height - 192, "This certificate is proudly awarded to")

    # 5. Learner's Full Name
    c.setFillColor(primary_dark)
    c.setFont("Helvetica-Bold", 26)
    c.drawCentredString(center_x, height - 232, str(learner.full_name))

    # Name underline bar
    name_width = min(420, max(260, len(str(learner.full_name)) * 14))
    c.setStrokeColor(primary_color)
    c.setLineWidth(2)
    c.line(center_x - (name_width / 2), height - 242, center_x + (name_width / 2), height - 242)

    # 6. Fulfillment statement & Course Title
    c.setFillColor(text_muted)
    c.setFont("Helvetica", 12.5)
    c.drawCentredString(
        center_x,
        height - 275,
        "for successfully fulfilling all curriculum requirements, lessons, and assessments for"
    )

    c.setFillColor(primary_color)
    c.setFont("Helvetica-Bold", 20)
    # Truncate or wrap title cleanly if very long
    course_title = course.title
    if len(course_title) > 65:
        course_title = course_title[:62] + "..."
    c.drawCentredString(center_x, height - 310, course_title)

    # 7. Metadata: Instructor, Date, and Verified Seal
    # Resolve completion date
    enrollment = Enrollment.query.filter_by(learner_id=learner.id, course_id=course.id).first()
    if enrollment and enrollment.completed_at:
        completion_date_str = enrollment.completed_at.strftime("%B %d, %Y")
    else:
        completion_date_str = datetime.utcnow().strftime("%B %d, %Y")

    # Resolve instructor name
    if course.teacher and course.teacher.user:
        teacher_name = course.teacher.user.full_name
    else:
        teacher_name = "SkillBridge Faculty"

    # Left: Instructor signature block
    sig_left_x = 160
    c.setStrokeColor(text_muted)
    c.setLineWidth(1)
    c.line(sig_left_x - 90, 140, sig_left_x + 90, 140)

    c.setFillColor(text_dark)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(sig_left_x, 122, teacher_name)
    c.setFillColor(text_muted)
    c.setFont("Helvetica", 10)
    c.drawCentredString(sig_left_x, 107, "Course Instructor")

    # Center: Decorative Seal
    c.setFillColor(colors.HexColor("#EEF2FF"))
    c.circle(center_x, 135, 34, fill=True, stroke=False)
    c.setStrokeColor(primary_color)
    c.setLineWidth(2)
    c.circle(center_x, 135, 34, fill=False, stroke=True)
    c.setFillColor(primary_color)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(center_x, 140, "OFFICIAL")
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(center_x, 126, "VERIFIED")

    # Right: Completion Date block
    sig_right_x = width - 160
    c.setStrokeColor(text_muted)
    c.setLineWidth(1)
    c.line(sig_right_x - 90, 140, sig_right_x + 90, 140)

    c.setFillColor(text_dark)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(sig_right_x, 122, completion_date_str)
    c.setFillColor(text_muted)
    c.setFont("Helvetica", 10)
    c.drawCentredString(sig_right_x, 107, "Date of Completion")

    # 8. Bottom Verification Bar
    c.setFillColor(text_muted)
    c.setFont("Helvetica", 9)
    verification_text = (
        f"Certificate ID: {certificate_code}   •   "
        f"Online Verification: /certificates/verify/{certificate_code}"
    )
    c.drawCentredString(center_x, 50, verification_text)

    # Finalize PDF
    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer.getvalue()


def upload_certificate_pdf(pdf_bytes: bytes, certificate_code: str) -> str:
    """
    Upload certificate PDF to Cloudinary with fallback to local disk.
    Mirrors upload_lesson_pdf pattern with resource_type="raw".
    Returns the URL/path to the PDF document.
    """
    # 1. Attempt upload to Cloudinary if configured
    if _is_cloudinary_configured():
        try:
            result = cloudinary.uploader.upload(
                pdf_bytes,
                folder="skillbridge/certificates",
                public_id=f"cert_{certificate_code}",
                overwrite=True,
                resource_type="raw",
            )
            secure_url = result.get("secure_url")
            if secure_url:
                return secure_url
        except Exception as exc:
            current_app.logger.warning(
                f"[Cloudinary] Certificate upload failed: {exc}. Falling back to local disk."
            )

    # 2. Local disk fallback storage
    upload_dir = os.path.join(current_app.root_path, "static", "uploads", "certificates")
    os.makedirs(upload_dir, exist_ok=True)

    filename = f"cert_{certificate_code}.pdf"
    destination = os.path.join(upload_dir, filename)
    with open(destination, "wb") as f:
        f.write(pdf_bytes)

    if has_request_context():
        return url_for("static", filename=f"uploads/certificates/{filename}")
    return f"/static/uploads/certificates/{filename}"

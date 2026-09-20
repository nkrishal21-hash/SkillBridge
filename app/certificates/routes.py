"""
app/certificates/routes.py — Certificate Generation, Download, and Verification
Handles issuing PDF certificates for completed courses, downloading stored PDF files,
and public credential authenticity verification.
"""

import os
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    abort,
    send_from_directory,
    current_app,
)
from flask_login import login_required, current_user
from app import db
from app.models import Course, Enrollment, Certificate
from app.auth.utils import learner_required
from app.certificates.utils import (
    generate_certificate_code,
    generate_certificate_pdf,
    upload_certificate_pdf,
)

certificates_bp = Blueprint("certificates", __name__)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Generate / Issue Certificate
# ─────────────────────────────────────────────────────────────────────────────
@certificates_bp.route("/generate/<int:course_id>")
@login_required
@learner_required
def generate(course_id: int):
    """
    Generate and persist a certificate for a completed course.
    If a certificate already exists, redirects to download immediately.
    Guards: Learner must have Enrollment with completed_at NOT NULL.
    """
    course = Course.query.get_or_404(course_id)
    enrollment = Enrollment.query.filter_by(
        learner_id=current_user.id,
        course_id=course.id
    ).first()

    if not enrollment or not enrollment.completed_at:
        flash("You must complete all lessons and pass required quizzes before claiming your certificate.", "warning")
        return redirect(url_for("courses.course_detail", course_id=course.id))

    # Check if certificate already exists (enforces unique constraint uq_certificate)
    existing_cert = Certificate.query.filter_by(
        learner_id=current_user.id,
        course_id=course.id
    ).first()

    if existing_cert:
        return redirect(url_for("certificates.download", certificate_id=existing_cert.id))

    # Generate unique code and build PDF bytes
    code = generate_certificate_code()
    pdf_bytes = generate_certificate_pdf(current_user, course, code)
    pdf_url = upload_certificate_pdf(pdf_bytes, code)

    cert = Certificate(
        learner_id=current_user.id,
        course_id=course.id,
        certificate_code=code,
        pdf_url=pdf_url,
    )
    db.session.add(cert)
    db.session.commit()

    flash("Congratulations! Your official Certificate of Completion has been generated.", "success")
    return redirect(url_for("certificates.download", certificate_id=cert.id))


# ─────────────────────────────────────────────────────────────────────────────
# 2. Download Certificate PDF
# ─────────────────────────────────────────────────────────────────────────────
@certificates_bp.route("/download/<int:certificate_id>")
@login_required
def download(certificate_id: int):
    """
    Download or view the certificate PDF.
    Access restricted to the earning learner or administrators (IDOR protection).
    """
    cert = Certificate.query.get_or_404(certificate_id)

    # Authorization guard: must be certificate's learner or an admin
    if cert.learner_id != current_user.id and not current_user.is_admin:
        abort(403)

    if not cert.pdf_url:
        flash("Certificate document is currently unavailable.", "danger")
        return redirect(url_for("learner.dashboard"))

    # If hosted on Cloudinary, redirect to secure URL
    if cert.pdf_url.startswith("http://") or cert.pdf_url.startswith("https://"):
        return redirect(cert.pdf_url)

    # Local fallback file serving
    # Expected local format: /static/uploads/certificates/cert_...pdf
    rel_path = cert.pdf_url.lstrip("/")
    if rel_path.startswith("static/"):
        rel_path = rel_path[len("static/"):]

    filename = os.path.basename(rel_path)
    cert_dir = os.path.join(current_app.root_path, "static", "uploads", "certificates")
    target_file = os.path.join(cert_dir, filename)

    if os.path.exists(target_file):
        return send_from_directory(
            cert_dir,
            filename,
            as_attachment=True,
            download_name=f"{cert.certificate_code}.pdf",
            mimetype="application/pdf",
        )

    # If file not found in certificates dir, try generic static directory
    static_dir = os.path.join(current_app.root_path, "static")
    dir_name = os.path.dirname(rel_path)
    full_dir = os.path.join(static_dir, dir_name)
    if os.path.exists(os.path.join(full_dir, filename)):
        return send_from_directory(
            full_dir,
            filename,
            as_attachment=True,
            download_name=f"{cert.certificate_code}.pdf",
            mimetype="application/pdf",
        )

    flash("Certificate file could not be located on the server.", "danger")
    return redirect(url_for("learner.dashboard"))


# ─────────────────────────────────────────────────────────────────────────────
# 3. Public Verification
# ─────────────────────────────────────────────────────────────────────────────
@certificates_bp.route("/verify/<string:code>")
def verify(code: str):
    """
    Public verification page for certificate authenticity.
    Anyone with the verification code (e.g. employers, peers) can confirm credential.
    """
    clean_code = code.strip().upper()
    cert = Certificate.query.filter_by(certificate_code=clean_code).first()

    return render_template(
        "certificates/verify.html",
        cert=cert,
        code=clean_code,
    )

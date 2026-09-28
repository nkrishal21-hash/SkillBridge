"""
app/teacher/routes.py — Teacher Blueprint Routes
Handles teacher dashboard, profile editing, mentor search, and public profile views.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import or_, and_, func
from app import db
from app.models import TeacherProfile, TeacherDocument, User, Payment, Booking, Course, Review
from app.auth.utils import teacher_required
from app.teacher.forms import TeacherProfileForm
from app.teacher.utils import (
    upload_profile_photo,
    upload_teacher_document,
    parse_skills,
    availability_to_json,
    available_days_list,
)

teacher_bp = Blueprint("teacher", __name__)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Teacher Dashboard
# ─────────────────────────────────────────────────────────────────────────────
@teacher_bp.route("/dashboard")
@login_required
@teacher_required
def dashboard():
    """Teacher studio dashboard with earnings, courses, bookings, and student reviews."""
    profile = current_user.teacher_profile
    if not profile:
        profile = TeacherProfile(user=current_user)
        db.session.add(profile)
        db.session.commit()

    # Profile completeness check
    profile_complete = bool(
        profile.headline and profile.skills and profile.hourly_rate is not None
    )

    # Use status="pending" (column on Booking model is status)
    pending_count = current_user.bookings_as_teacher.filter_by(status="pending").count()

    # Query teacher's booking IDs and course IDs for earnings calculation
    teacher_booking_subq = db.session.query(Booking.id).filter(Booking.teacher_id == current_user.id)
    teacher_course_subq = db.session.query(Course.id).filter(Course.teacher_id == profile.id)

    earnings_condition = and_(
        Payment.status == "success",
        or_(
            and_(Payment.payment_for == "booking", Payment.booking_id_ref.in_(teacher_booking_subq)),
            and_(Payment.payment_for == "course", Payment.course_id.in_(teacher_course_subq)),
        ),
    )

    # ── Earnings breakdown (gross / platform fee / net / paid out / pending) ──
    # Gross: full amount paid by learners for this teacher's courses + bookings
    gross_earnings = (
        db.session.query(func.coalesce(func.sum(Payment.amount), 0.0))
        .filter(earnings_condition)
        .scalar()
    ) or 0.0

    # Platform fee (20%) — sum of platform_fee_amount for successful payments
    platform_fee_total = (
        db.session.query(func.coalesce(func.sum(Payment.platform_fee_amount), 0.0))
        .filter(earnings_condition)
        .scalar()
    ) or 0.0

    # Net earnings (80%) — sum of teacher_payout_amount for successful payments
    net_earnings = (
        db.session.query(func.coalesce(func.sum(Payment.teacher_payout_amount), 0.0))
        .filter(earnings_condition)
        .scalar()
    ) or 0.0

    # If any rows have NULL teacher_payout_amount (pre-backfill edge case), fall back
    if float(net_earnings) == 0.0 and float(gross_earnings) > 0:
        net_earnings = float(gross_earnings) * 0.80
        platform_fee_total = float(gross_earnings) * 0.20

    # Already paid out (payout_status == 'released')
    released_condition = and_(earnings_condition, Payment.payout_status == "released")
    paid_out_total = (
        db.session.query(func.coalesce(func.sum(Payment.teacher_payout_amount), 0.0))
        .filter(released_condition)
        .scalar()
    ) or 0.0

    # Still pending payout (payout_status == 'pending')
    pending_payout_total = float(net_earnings) - float(paid_out_total)

    recent_payments = (
        Payment.query.filter(earnings_condition)
        .order_by(Payment.completed_at.desc(), Payment.id.desc())
        .limit(5)
        .all()
    )

    recent_reviews = (
        profile.reviews.order_by(Review.created_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "teacher/dashboard.html",
        user=current_user,
        profile=profile,
        profile_complete=profile_complete,
        pending_count=pending_count,
        gross_earnings=float(gross_earnings),
        platform_fee_total=float(platform_fee_total),
        net_earnings=float(net_earnings),
        paid_out_total=float(paid_out_total),
        pending_payout_total=float(pending_payout_total),
        total_earnings=float(gross_earnings),   # kept for backward compat
        recent_payments=recent_payments,
        recent_reviews=recent_reviews,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Profile Edit
# ─────────────────────────────────────────────────────────────────────────────
@teacher_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
@teacher_required
def profile_edit():
    """Edit teacher profile information, photo, and availability."""
    profile = current_user.teacher_profile
    if not profile:
        profile = TeacherProfile(user=current_user)
        db.session.add(profile)
        db.session.commit()

    form = TeacherProfileForm()

    if form.validate_on_submit():
        # Handle profile photo upload if provided
        if form.photo.data and getattr(form.photo.data, "filename", None):
            try:
                photo_url = upload_profile_photo(form.photo.data, current_user.id)
                current_user.profile_photo = photo_url
            except ValueError as err:
                flash(str(err), "danger")
                return render_template("teacher/profile_edit.html", form=form, profile=profile)

        # Update profile attributes
        profile.headline = form.headline.data.strip() if form.headline.data else None
        profile.bio = form.bio.data.strip() if form.bio.data else None
        profile.skills = form.skills.data.strip() if form.skills.data else None
        profile.qualifications = form.qualifications.data.strip() if form.qualifications.data else None
        profile.experience_years = form.experience_years.data or 0
        profile.teaching_languages = form.teaching_languages.data.strip() if form.teaching_languages.data else None
        profile.hourly_rate = form.hourly_rate.data
        profile.availability = availability_to_json(form.availability.data)
        profile.linkedin_url = form.linkedin_url.data.strip() if form.linkedin_url.data else None
        profile.website_url = form.website_url.data.strip() if form.website_url.data else None

        db.session.commit()
        flash("Your mentor profile has been saved successfully!", "success")
        return redirect(url_for("teacher.dashboard"))

    elif request.method == "GET":
        # Pre-populate form fields from database
        form.headline.data = profile.headline
        form.bio.data = profile.bio
        form.skills.data = profile.skills
        form.qualifications.data = profile.qualifications
        form.experience_years.data = profile.experience_years
        form.teaching_languages.data = profile.teaching_languages
        form.hourly_rate.data = profile.hourly_rate
        form.availability.data = available_days_list(profile.availability)
        form.linkedin_url.data = profile.linkedin_url
        form.website_url.data = profile.website_url

    existing_docs = (
        TeacherDocument.query
        .filter_by(teacher_profile_id=profile.id)
        .order_by(TeacherDocument.uploaded_at.desc())
        .all()
    )
    return render_template(
        "teacher/profile_edit.html",
        form=form,
        profile=profile,
        documents=existing_docs,
        document_type_labels=DOCUMENT_TYPE_LABELS,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3b. Teacher Document Upload / Management
# ─────────────────────────────────────────────────────────────────────────────
DOCUMENT_TYPE_LABELS = {
    "citizenship": "Citizenship Card",
    "passport": "Passport",
    "educational_certificate": "Educational Certificate",
    "other": "Other Document",
}


@teacher_bp.route("/documents", methods=["GET"])
@login_required
@teacher_required
def documents():
    """
    Legacy URL — kept so that existing links (dashboard banner, admin links) do not break.
    Redirects to Edit Profile which now hosts the credential documents section.
    """
    return redirect(url_for("teacher.profile_edit") + "#credential-documents")


@teacher_bp.route("/profile/documents/upload", methods=["POST"])
@login_required
@teacher_required
def upload_documents():
    """
    Multi-file credential document upload endpoint POSTed from the Edit Profile page.
    Accepts multiple files of the same document type in one batch (input[multiple]).
    Each file becomes its own TeacherDocument row.
    Validates extension (pdf/jpg/jpeg/png) and size (max 10 MB per file).
    Enforces a per-type cap of 10 documents.
    Redirects back to Edit Profile on success or error.
    """
    profile = current_user.teacher_profile
    if not profile:
        profile = TeacherProfile(user=current_user)
        db.session.add(profile)
        db.session.commit()

    allowed_types = ["citizenship", "passport", "educational_certificate", "other"]
    doc_type = request.form.get("document_type", "").strip()
    if doc_type not in allowed_types:
        flash("Please select a valid document type.", "danger")
        return redirect(url_for("teacher.profile_edit") + "#credential-documents")

    files = request.files.getlist("document_files")
    if not files or all(not f.filename for f in files):
        flash("No files were selected. Please choose at least one file.", "danger")
        return redirect(url_for("teacher.profile_edit") + "#credential-documents")

    # Per-type cap: count existing docs of this type
    existing_count = TeacherDocument.query.filter_by(
        teacher_profile_id=profile.id,
        document_type=doc_type,
    ).count()
    cap = 10
    slots_left = cap - existing_count
    if slots_left <= 0:
        flash(
            f"You already have {cap} documents of type '{DOCUMENT_TYPE_LABELS.get(doc_type, doc_type)}'. "
            "Delete some before uploading more.",
            "danger",
        )
        return redirect(url_for("teacher.profile_edit") + "#credential-documents")

    uploaded = 0
    errors = []
    for file_storage in files[:slots_left]:
        if not file_storage or not file_storage.filename:
            continue
        try:
            file_url = upload_teacher_document(file_storage, profile.id)
        except ValueError as err:
            errors.append(f"{file_storage.filename}: {err}")
            continue
        doc = TeacherDocument(
            teacher_profile_id=profile.id,
            document_type=doc_type,
            file_url=file_url,
        )
        db.session.add(doc)
        uploaded += 1

    if uploaded:
        db.session.commit()
        flash(
            f"{uploaded} document{'s' if uploaded != 1 else ''} uploaded. "
            "Admin will review them before granting verified status.",
            "success",
        )
    for err_msg in errors:
        flash(err_msg, "danger")

    return redirect(url_for("teacher.profile_edit") + "#credential-documents")


@teacher_bp.route("/documents/<int:doc_id>/delete", methods=["POST"])
@login_required
@teacher_required
def delete_document(doc_id: int):
    """Delete a previously uploaded credential document (only allowed while unverified)."""
    profile = current_user.teacher_profile
    doc = TeacherDocument.query.get_or_404(doc_id)
    # Ownership check — must belong to the current teacher's profile
    if not profile or doc.teacher_profile_id != profile.id:
        flash("You do not have permission to delete that document.", "danger")
        return redirect(url_for("teacher.profile_edit") + "#credential-documents")
    db.session.delete(doc)
    db.session.commit()
    flash("Document deleted.", "success")
    return redirect(url_for("teacher.profile_edit") + "#credential-documents")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Public Mentor Search (Must be registered before /<int:teacher_id>)

# ─────────────────────────────────────────────────────────────────────────────
@teacher_bp.route("/search")
def search():
    """
    Public teacher discovery page with real-time filtering and sorting.
    Gated on profile completeness (headline, skills, rate) rather than admin verification.
    """
    q = request.args.get("q", "").strip()
    min_rating = request.args.get("min_rating", type=float)
    max_price = request.args.get("max_price", type=float)
    day = request.args.get("day", "").strip()
    sort_by = request.args.get("sort", "rating").strip()
    page = request.args.get("page", 1, type=int)

    # Base query: Join TeacherProfile with User (verified mentors only)
    query = TeacherProfile.query.join(User).filter(
        User.is_active.is_(True),
        TeacherProfile.is_verified.is_(True),
        TeacherProfile.headline.isnot(None),
        TeacherProfile.headline != "",
        TeacherProfile.skills.isnot(None),
        TeacherProfile.skills != "",
        TeacherProfile.hourly_rate.isnot(None),
    )

    # Keyword search across skills, headline, bio, and teacher's full name
    if q:
        query = query.filter(
            or_(
                TeacherProfile.skills.ilike(f"%{q}%"),
                TeacherProfile.headline.ilike(f"%{q}%"),
                TeacherProfile.bio.ilike(f"%{q}%"),
                User.full_name.ilike(f"%{q}%"),
            )
        )

    # Rating filter
    if min_rating is not None and min_rating > 0:
        query = query.filter(TeacherProfile.average_rating >= min_rating)

    # Maximum hourly price filter
    if max_price is not None and max_price >= 0:
        query = query.filter(TeacherProfile.hourly_rate <= max_price)

    # Weekly availability day filter (checks JSON flag)
    if day:
        query = query.filter(TeacherProfile.availability.like(f'%"{day}": true%'))

    # Sorting
    if sort_by == "price_low":
        query = query.order_by(TeacherProfile.hourly_rate.asc())
    elif sort_by == "price_high":
        query = query.order_by(TeacherProfile.hourly_rate.desc())
    elif sort_by == "experience":
        query = query.order_by(TeacherProfile.experience_years.desc())
    else:  # default 'rating'
        query = query.order_by(
            TeacherProfile.average_rating.desc(),
            TeacherProfile.total_reviews.desc(),
            TeacherProfile.id.desc(),
        )

    pagination = query.paginate(page=page, per_page=9, error_out=False)

    return render_template(
        "teacher/search.html",
        pagination=pagination,
        teachers=pagination.items,
        q=q,
        min_rating=min_rating,
        max_price=max_price,
        selected_day=day,
        sort_by=sort_by,
        parse_skills=parse_skills,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. Public Profile Page (Registered last so /search, /dashboard match first)
# ─────────────────────────────────────────────────────────────────────────────
@teacher_bp.route("/<int:teacher_id>")
def public_profile(teacher_id: int):
    """View public profile of a teacher."""
    profile = TeacherProfile.query.get_or_404(teacher_id)
    skills_list = parse_skills(profile.skills)
    available_days = available_days_list(profile.availability)
    is_owner = (
        current_user.is_authenticated
        and current_user.id == profile.user_id
    )

    is_favorited = False
    if current_user.is_authenticated and current_user.is_learner:
        from app.models import Favorite
        is_favorited = (
            Favorite.query.filter_by(
                learner_id=current_user.id, teacher_id=profile.id
            ).first() is not None
        )

    return render_template(
        "teacher/public_profile.html",
        profile=profile,
        skills_list=skills_list,
        available_days=available_days,
        is_owner=is_owner,
        is_favorited=is_favorited,
    )

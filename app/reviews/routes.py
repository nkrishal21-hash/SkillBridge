"""
app/reviews/routes.py — Reviews and Ratings Blueprint Routes
Allows learners to review completed mentorship sessions and completed courses,
updating teacher average ratings and review counts dynamically.
"""

from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    request,
    abort,
)
from flask_login import login_required, current_user
from sqlalchemy import func

from app import db
from app.models import Review, Rating, Booking, Course, Enrollment, TeacherProfile
from app.auth.utils import learner_required
from app.reviews import reviews_bp
from app.reviews.forms import ReviewForm
from app.notifications.utils import notify


# ─────────────────────────────────────────────────────────────────────────────
# 1. Review Completed Mentorship Session
# ─────────────────────────────────────────────────────────────────────────────
@reviews_bp.route("/booking/<int:booking_id>", methods=["POST"])
@login_required
@learner_required
def review_booking(booking_id: int):
    """
    Submit a review and rating for a completed mentorship booking.
    Only the booking's learner can review, once status is 'completed'.
    """
    booking = Booking.query.get_or_404(booking_id)

    # Must be the booking's learner
    if booking.learner_id != current_user.id:
        abort(403)

    # Must be completed
    if booking.status != "completed":
        flash("You can only review mentorship sessions that have been completed.", "warning")
        return redirect(url_for("booking.detail", booking_id=booking.id))

    # Check if already reviewed
    existing_review = Review.query.filter_by(
        learner_id=current_user.id,
        booking_id=booking.id
    ).first()
    if existing_review:
        flash("You have already submitted a review for this session.", "info")
        return redirect(url_for("booking.detail", booking_id=booking.id))

    form = ReviewForm()
    if form.validate_on_submit():
        teacher_profile = booking.teacher.teacher_profile
        if not teacher_profile:
            flash("Mentor profile not found.", "danger")
            return redirect(url_for("booking.detail", booking_id=booking.id))

        rating_val = form.rating_value.data
        review_body = form.review_text.data.strip() if form.review_text.data else None

        # 1. Create Review
        review = Review(
            learner_id=current_user.id,
            teacher_id=teacher_profile.id,
            booking_id=booking.id,
            course_id=None,
            rating_value=rating_val,
            review_text=review_body,
        )
        db.session.add(review)

        # 2. Create Rating entry
        rating = Rating(
            teacher_id=teacher_profile.id,
            learner_id=current_user.id,
            value=rating_val,
        )
        db.session.add(rating)
        db.session.flush()

        # 3. Recalculate TeacherProfile.average_rating and total_reviews
        stats = db.session.query(
            func.avg(Rating.value),
            func.count(Rating.id)
        ).filter(Rating.teacher_id == teacher_profile.id).first()

        teacher_profile.average_rating = round(float(stats[0] or 0), 2)
        teacher_profile.total_reviews = int(stats[1] or 0)

        db.session.commit()

        # Notify teacher of new review
        notify(
            user_id=booking.teacher_id,
            title=f"New Session Review ({rating_val}★)",
            body=f"{current_user.full_name} left a {rating_val}-star review for '{booking.topic}'.",
            notif_type="review",
            link=url_for("booking.detail", booking_id=booking.id),
        )

        flash("⭐ Thank you! Your review and rating have been published.", "success")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{error}", "warning")

    return redirect(url_for("booking.detail", booking_id=booking.id))


# ─────────────────────────────────────────────────────────────────────────────
# 2. Review Completed Course
# ─────────────────────────────────────────────────────────────────────────────
@reviews_bp.route("/course/<int:course_id>", methods=["POST"])
@login_required
@learner_required
def review_course(course_id: int):
    """
    Submit a review and rating for a completed course.
    Only learners with an Enrollment where completed_at is set can review.
    """
    course = Course.query.get_or_404(course_id)

    # Must have completed the course
    enrollment = Enrollment.query.filter_by(
        learner_id=current_user.id,
        course_id=course.id
    ).first()

    if not enrollment or not enrollment.completed_at:
        flash("You can only review courses you have finished 100% of lessons for.", "warning")
        return redirect(url_for("courses.course_detail", course_id=course.id))

    # Gated to prevent duplicate reviews per learner per course
    existing_review = Review.query.filter_by(
        learner_id=current_user.id,
        course_id=course.id
    ).first()

    if existing_review:
        flash("You have already reviewed this course.", "info")
        return redirect(url_for("courses.course_detail", course_id=course.id))

    form = ReviewForm()
    if form.validate_on_submit():
        teacher_profile = course.teacher
        if not teacher_profile:
            flash("Course instructor profile not found.", "danger")
            return redirect(url_for("courses.course_detail", course_id=course.id))

        rating_val = form.rating_value.data
        review_body = form.review_text.data.strip() if form.review_text.data else None

        # 1. Create Review
        review = Review(
            learner_id=current_user.id,
            teacher_id=teacher_profile.id,
            booking_id=None,
            course_id=course.id,
            rating_value=rating_val,
            review_text=review_body,
        )
        db.session.add(review)

        # 2. Create Rating entry
        rating = Rating(
            teacher_id=teacher_profile.id,
            learner_id=current_user.id,
            value=rating_val,
        )
        db.session.add(rating)
        db.session.flush()

        # 3. Recalculate TeacherProfile.average_rating and total_reviews
        stats = db.session.query(
            func.avg(Rating.value),
            func.count(Rating.id)
        ).filter(Rating.teacher_id == teacher_profile.id).first()

        teacher_profile.average_rating = round(float(stats[0] or 0), 2)
        teacher_profile.total_reviews = int(stats[1] or 0)

        db.session.commit()

        # Notify instructor of new course review
        notify(
            user_id=teacher_profile.user_id,
            title=f"New Course Review ({rating_val}★)",
            body=f"{current_user.full_name} left a {rating_val}-star review on '{course.title}'.",
            notif_type="review",
            link=url_for("courses.course_detail", course_id=course.id),
        )

        flash("⭐ Thank you! Your course review and rating have been published.", "success")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{error}", "warning")

    return redirect(url_for("courses.course_detail", course_id=course.id))

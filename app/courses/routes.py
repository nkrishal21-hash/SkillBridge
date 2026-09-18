"""
app/courses/routes.py — Course Management Blueprint Routes
Handles course catalog, detail page, creation, editing, publishing,
lesson curriculum management, enrollment, lesson viewing, and quiz grading.
"""

from datetime import datetime
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    abort,
)
from flask_login import login_required, current_user
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import Course, Lesson, Enrollment, TeacherProfile, Review
from app.auth.utils import teacher_required, learner_required
from app.courses.forms import CourseForm, LessonForm
from app.reviews.forms import ReviewForm
from app.courses.utils import (
    upload_course_thumbnail,
    upload_lesson_video,
    upload_lesson_pdf,
    parse_quiz_data,
    format_quiz_data,
)
from app.notifications.utils import notify

courses_bp = Blueprint("courses", __name__)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Course Catalog (Public)
# ─────────────────────────────────────────────────────────────────────────────
@courses_bp.route("/")
def catalog():
    """
    Public course discovery catalog with search keyword, category, level,
    price filtering, sorting, and pagination.
    Only published courses are shown (admin approval workflow deferred to Phase 8).
    """
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    level = request.args.get("level", "").strip()
    price_filter = request.args.get("price", "").strip()
    sort_by = request.args.get("sort", "newest").strip()
    page = request.args.get("page", 1, type=int)

    query = Course.query.filter(Course.is_published.is_(True))

    # Keyword search across title and description
    if q:
        query = query.filter(
            or_(
                Course.title.ilike(f"%{q}%"),
                Course.description.ilike(f"%{q}%"),
            )
        )

    # Category filter
    if category:
        query = query.filter(Course.category == category)

    # Skill level filter
    if level in ("beginner", "intermediate", "advanced"):
        query = query.filter(Course.level == level)

    # Price filter: free vs paid
    if price_filter == "free":
        query = query.filter(or_(Course.price == 0.00, Course.price.is_(None)))
    elif price_filter == "paid":
        query = query.filter(Course.price > 0.00)

    # Sorting
    if sort_by == "price_low":
        query = query.order_by(Course.price.asc(), Course.id.desc())
    elif sort_by == "price_high":
        query = query.order_by(Course.price.desc(), Course.id.desc())
    else:  # 'newest' default
        query = query.order_by(Course.created_at.desc(), Course.id.desc())

    pagination = query.paginate(page=page, per_page=9, error_out=False)

    return render_template(
        "courses/catalog.html",
        pagination=pagination,
        courses=pagination.items,
        q=q,
        selected_category=category,
        selected_level=level,
        selected_price=price_filter,
        sort_by=sort_by,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Course Detail Page (Public)
# ─────────────────────────────────────────────────────────────────────────────
@courses_bp.route("/<int:course_id>")
def course_detail(course_id: int):
    """
    Public course overview page with instructor info, full syllabus,
    lock/preview indicators, and enroll call-to-action.
    """
    course = Course.query.get_or_404(course_id)

    # Determine ownership
    is_owner = (
        current_user.is_authenticated
        and current_user.is_teacher
        and current_user.teacher_profile
        and current_user.teacher_profile.id == course.teacher_id
    )

    # If course is not published, only the owner or an admin can view it
    if not course.is_published and not is_owner and not (current_user.is_authenticated and current_user.is_admin):
        flash("This course is currently an unpublished draft.", "warning")
        return redirect(url_for("courses.catalog"))

    # Check enrollment status
    enrollment = None
    completed_ids = []
    if current_user.is_authenticated:
        enrollment = Enrollment.query.filter_by(
            learner_id=current_user.id, course_id=course.id
        ).first()
        if enrollment and enrollment.completed_lessons:
            completed_ids = [
                int(cid) for cid in enrollment.completed_lessons.split(",") if cid.isdigit()
            ]

    lessons = course.lessons.order_by(Lesson.order.asc()).all()
    total_duration = sum(l.duration_minutes or 0 for l in lessons)

    # Reviews and learner completion status
    reviews = Review.query.filter_by(course_id=course.id).order_by(Review.created_at.desc()).all()
    user_review = None
    review_form = None
    can_review = False

    if current_user.is_authenticated and enrollment and enrollment.completed_at:
        user_review = Review.query.filter_by(
            learner_id=current_user.id,
            course_id=course.id
        ).first()
        if not user_review:
            can_review = True
            review_form = ReviewForm()

    return render_template(
        "courses/course_detail.html",
        course=course,
        lessons=lessons,
        total_duration=total_duration,
        is_owner=is_owner,
        enrollment=enrollment,
        completed_ids=completed_ids,
        reviews=reviews,
        user_review=user_review,
        can_review=can_review,
        review_form=review_form,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. Create Course (Teacher Only)
# ─────────────────────────────────────────────────────────────────────────────
@courses_bp.route("/create", methods=["GET", "POST"])
@login_required
@teacher_required
def create():
    """Create a new course owned by current_user.teacher_profile."""
    teacher_profile = current_user.teacher_profile
    if not teacher_profile:
        teacher_profile = TeacherProfile(user=current_user)
        db.session.add(teacher_profile)
        db.session.commit()

    form = CourseForm()

    if form.validate_on_submit():
        thumbnail_url = None
        if form.thumbnail.data and getattr(form.thumbnail.data, "filename", None):
            try:
                thumbnail_url = upload_course_thumbnail(form.thumbnail.data, teacher_profile.id)
            except ValueError as err:
                flash(str(err), "danger")
                return render_template("courses/course_form.html", form=form, is_edit=False)

        course = Course(
            teacher_id=teacher_profile.id,
            title=form.title.data.strip(),
            description=form.description.data.strip() if form.description.data else None,
            category=form.category.data,
            level=form.level.data,
            language=form.language.data.strip() if form.language.data else "English",
            price=form.price.data or 0.00,
            thumbnail_url=thumbnail_url,
            is_published=False,  # default draft
        )
        db.session.add(course)
        db.session.commit()

        flash(f"Course '{course.title}' created successfully! Now add lessons to build your curriculum.", "success")
        return redirect(url_for("courses.manage_lessons", course_id=course.id))

    return render_template("courses/course_form.html", form=form, is_edit=False)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Edit Course Metadata (Teacher Only)
# ─────────────────────────────────────────────────────────────────────────────
@courses_bp.route("/<int:course_id>/edit", methods=["GET", "POST"])
@login_required
@teacher_required
def edit(course_id: int):
    """Edit course details and thumbnail."""
    course = Course.query.get_or_404(course_id)

    if not current_user.teacher_profile or course.teacher_id != current_user.teacher_profile.id:
        abort(403)

    form = CourseForm()

    if form.validate_on_submit():
        if form.thumbnail.data and getattr(form.thumbnail.data, "filename", None):
            try:
                thumbnail_url = upload_course_thumbnail(form.thumbnail.data, current_user.teacher_profile.id)
                course.thumbnail_url = thumbnail_url
            except ValueError as err:
                flash(str(err), "danger")
                return render_template("courses/course_form.html", form=form, course=course, is_edit=True)

        course.title = form.title.data.strip()
        course.description = form.description.data.strip() if form.description.data else None
        course.category = form.category.data
        course.level = form.level.data
        course.language = form.language.data.strip() if form.language.data else "English"
        course.price = form.price.data or 0.00

        db.session.commit()
        flash("Course details updated successfully!", "success")
        return redirect(url_for("courses.course_detail", course_id=course.id))

    elif request.method == "GET":
        form.title.data = course.title
        form.description.data = course.description
        form.category.data = course.category
        form.level.data = course.level
        form.language.data = course.language
        form.price.data = course.price

    return render_template("courses/course_form.html", form=form, course=course, is_edit=True)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Toggle Course Publish Status
# ─────────────────────────────────────────────────────────────────────────────
@courses_bp.route("/<int:course_id>/publish", methods=["POST"])
@login_required
@teacher_required
def toggle_publish(course_id: int):
    """Publish or unpublish course in public catalog."""
    course = Course.query.get_or_404(course_id)
    if not current_user.teacher_profile or course.teacher_id != current_user.teacher_profile.id:
        abort(403)

    course.is_published = not course.is_published
    db.session.commit()

    status_label = "published and is now visible in the catalog" if course.is_published else "moved to unpublished drafts"
    flash(f"Course '{course.title}' has been {status_label}.", "success")
    return redirect(request.referrer or url_for("courses.manage_lessons", course_id=course.id))


# ─────────────────────────────────────────────────────────────────────────────
# 6. Manage Lessons Curriculum (Teacher Only)
# ─────────────────────────────────────────────────────────────────────────────
@courses_bp.route("/<int:course_id>/lessons")
@login_required
@teacher_required
def manage_lessons(course_id: int):
    """View and manage curriculum for a course."""
    course = Course.query.get_or_404(course_id)
    if not current_user.teacher_profile or course.teacher_id != current_user.teacher_profile.id:
        abort(403)

    lessons = course.lessons.order_by(Lesson.order.asc()).all()
    return render_template("courses/manage_lessons.html", course=course, lessons=lessons)


# ─────────────────────────────────────────────────────────────────────────────
# 7. Add Lesson to Course (Teacher Only)
# ─────────────────────────────────────────────────────────────────────────────
@courses_bp.route("/<int:course_id>/lessons/create", methods=["GET", "POST"])
@login_required
@teacher_required
def create_lesson(course_id: int):
    """Add a new lesson (video, PDF, text, or quiz) to a course."""
    course = Course.query.get_or_404(course_id)
    if not current_user.teacher_profile or course.teacher_id != current_user.teacher_profile.id:
        abort(403)

    form = LessonForm()

    # Suggest next sequence order on GET
    if request.method == "GET":
        last_lesson = course.lessons.order_by(Lesson.order.desc()).first()
        form.order.data = (last_lesson.order + 1) if last_lesson else 1

    if form.validate_on_submit():
        content_type = form.content_type.data
        video_url = None
        pdf_url = None
        text_content = None
        quiz_data = None

        try:
            if content_type == "video" and form.video_file.data and getattr(form.video_file.data, "filename", None):
                video_url = upload_lesson_video(form.video_file.data, course.id)
            elif content_type == "pdf" and form.pdf_file.data and getattr(form.pdf_file.data, "filename", None):
                pdf_url = upload_lesson_pdf(form.pdf_file.data, course.id)
            elif content_type == "text":
                text_content = form.text_content.data.strip() if form.text_content.data else None
            elif content_type == "quiz":
                # Build quiz questions from dynamic form fields
                questions = []
                for q_sub in form.quiz_questions.data:
                    q_text = q_sub.get("question", "").strip()
                    options = [
                        q_sub.get("option_1", "").strip(),
                        q_sub.get("option_2", "").strip(),
                        q_sub.get("option_3", "").strip(),
                        q_sub.get("option_4", "").strip(),
                    ]
                    clean_options = [opt for opt in options if opt]
                    if q_text and len(clean_options) >= 2:
                        questions.append({
                            "question": q_text,
                            "options": clean_options,
                            "answer": int(q_sub.get("answer", 0)),
                        })
                quiz_data = questions
        except ValueError as err:
            flash(str(err), "danger")
            return render_template("courses/lesson_form.html", form=form, course=course, is_edit=False)

        lesson = Lesson(
            course_id=course.id,
            title=form.title.data.strip(),
            description=form.description.data.strip() if form.description.data else None,
            order=form.order.data or 1,
            content_type=content_type,
            video_url=video_url,
            pdf_url=pdf_url,
            text_content=text_content,
            duration_minutes=form.duration_minutes.data,
            is_preview=form.is_preview.data,
            quiz_data=quiz_data,
            quiz_pass_score=form.quiz_pass_score.data or 60,
        )
        db.session.add(lesson)
        db.session.commit()

        flash(f"Lesson '{lesson.title}' added successfully!", "success")
        return redirect(url_for("courses.manage_lessons", course_id=course.id))

    return render_template("courses/lesson_form.html", form=form, course=course, is_edit=False)


# ─────────────────────────────────────────────────────────────────────────────
# 8. Edit Lesson (Teacher Only)
# ─────────────────────────────────────────────────────────────────────────────
@courses_bp.route("/<int:course_id>/lessons/<int:lesson_id>/edit", methods=["GET", "POST"])
@login_required
@teacher_required
def edit_lesson(course_id: int, lesson_id: int):
    """Edit lesson properties and content."""
    course = Course.query.get_or_404(course_id)
    if not current_user.teacher_profile or course.teacher_id != current_user.teacher_profile.id:
        abort(403)

    lesson = Lesson.query.filter_by(id=lesson_id, course_id=course.id).first_or_404()
    form = LessonForm()

    if form.validate_on_submit():
        lesson.title = form.title.data.strip()
        lesson.description = form.description.data.strip() if form.description.data else None
        lesson.order = form.order.data or lesson.order
        lesson.content_type = form.content_type.data
        lesson.duration_minutes = form.duration_minutes.data
        lesson.is_preview = form.is_preview.data
        lesson.quiz_pass_score = form.quiz_pass_score.data or 60

        try:
            if lesson.content_type == "video" and form.video_file.data and getattr(form.video_file.data, "filename", None):
                lesson.video_url = upload_lesson_video(form.video_file.data, course.id)
            elif lesson.content_type == "pdf" and form.pdf_file.data and getattr(form.pdf_file.data, "filename", None):
                lesson.pdf_url = upload_lesson_pdf(form.pdf_file.data, course.id)
            elif lesson.content_type == "text":
                lesson.text_content = form.text_content.data.strip() if form.text_content.data else None
            elif lesson.content_type == "quiz":
                questions = []
                for q_sub in form.quiz_questions.data:
                    q_text = q_sub.get("question", "").strip()
                    options = [
                        q_sub.get("option_1", "").strip(),
                        q_sub.get("option_2", "").strip(),
                        q_sub.get("option_3", "").strip(),
                        q_sub.get("option_4", "").strip(),
                    ]
                    clean_options = [opt for opt in options if opt]
                    if q_text and len(clean_options) >= 2:
                        questions.append({
                            "question": q_text,
                            "options": clean_options,
                            "answer": int(q_sub.get("answer", 0)),
                        })
                lesson.quiz_data = questions
        except ValueError as err:
            flash(str(err), "danger")
            return render_template("courses/lesson_form.html", form=form, course=course, lesson=lesson, is_edit=True)

        db.session.commit()
        flash(f"Lesson '{lesson.title}' updated successfully!", "success")
        return redirect(url_for("courses.manage_lessons", course_id=course.id))

    elif request.method == "GET":
        form.title.data = lesson.title
        form.description.data = lesson.description
        form.order.data = lesson.order
        form.content_type.data = lesson.content_type
        form.duration_minutes = lesson.duration_minutes
        form.is_preview = lesson.is_preview
        form.text_content.data = lesson.text_content
        form.quiz_pass_score.data = lesson.quiz_pass_score

        # Populate quiz questions
        if lesson.quiz_data:
            parsed = parse_quiz_data(lesson.quiz_data)
            for q_item in parsed:
                opts = q_item.get("options", [])
                form.quiz_questions.append_entry({
                    "question": q_item.get("question", ""),
                    "option_1": opts[0] if len(opts) > 0 else "",
                    "option_2": opts[1] if len(opts) > 1 else "",
                    "option_3": opts[2] if len(opts) > 2 else "",
                    "option_4": opts[3] if len(opts) > 3 else "",
                    "answer": q_item.get("answer", 0),
                })

    return render_template("courses/lesson_form.html", form=form, course=course, lesson=lesson, is_edit=True)


# ─────────────────────────────────────────────────────────────────────────────
# 9. Delete Lesson (Teacher Only)
# ─────────────────────────────────────────────────────────────────────────────
@courses_bp.route("/<int:course_id>/lessons/<int:lesson_id>/delete", methods=["POST"])
@login_required
@teacher_required
def delete_lesson(course_id: int, lesson_id: int):
    """Delete a lesson from course curriculum."""
    course = Course.query.get_or_404(course_id)
    if not current_user.teacher_profile or course.teacher_id != current_user.teacher_profile.id:
        abort(403)

    lesson = Lesson.query.filter_by(id=lesson_id, course_id=course.id).first_or_404()
    db.session.delete(lesson)
    db.session.commit()

    flash("Lesson deleted successfully.", "info")
    return redirect(url_for("courses.manage_lessons", course_id=course.id))


# ─────────────────────────────────────────────────────────────────────────────
# 10. Enroll in Course (Learner Only)
# ─────────────────────────────────────────────────────────────────────────────
@courses_bp.route("/<int:course_id>/enroll", methods=["POST"])
@login_required
@learner_required
def enroll(course_id: int):
    """
    Enroll learner in course.
    Free courses enroll immediately; paid courses display a placeholder message.
    Gracefully catches UniqueConstraint violations.
    """
    course = Course.query.get_or_404(course_id)

    # If course is paid, redirect directly to secure checkout
    if course.price and course.price > 0.00:
        return redirect(url_for("payments.checkout", payment_for="course", target_id=course.id))

    # Free course enrollment
    try:
        enrollment = Enrollment(
            learner_id=current_user.id,
            course_id=course.id,
            completed_lessons="",
            progress_percent=0,
        )
        db.session.add(enrollment)
        db.session.commit()
        flash(f"🎉 Enrolled successfully in '{course.title}'! Welcome to the course.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("You're already enrolled in this course! Keep up the good work.", "info")

    # Redirect to first lesson or course detail
    first_lesson = course.lessons.order_by(Lesson.order.asc()).first()
    if first_lesson:
        return redirect(url_for("courses.lesson_view", course_id=course.id, lesson_id=first_lesson.id))
    return redirect(url_for("courses.course_detail", course_id=course.id))


# ─────────────────────────────────────────────────────────────────────────────
# 11. Lesson Viewer
# ─────────────────────────────────────────────────────────────────────────────
@courses_bp.route("/<int:course_id>/lessons/<int:lesson_id>")
@login_required
def lesson_view(course_id: int, lesson_id: int):
    """
    Interactive lesson viewer.
    Access is granted if:
      - Current user is the course instructor
      - Lesson has is_preview == True
      - Current user is enrolled in the course
    """
    course = Course.query.get_or_404(course_id)
    lesson = Lesson.query.filter_by(id=lesson_id, course_id=course.id).first_or_404()

    is_owner = (
        current_user.is_authenticated
        and current_user.is_teacher
        and current_user.teacher_profile
        and current_user.teacher_profile.id == course.teacher_id
    )

    enrollment = None
    if current_user.is_authenticated:
        enrollment = Enrollment.query.filter_by(
            learner_id=current_user.id, course_id=course.id
        ).first()

    # Permission check
    can_access = is_owner or lesson.is_preview or (enrollment is not None)
    if not can_access:
        flash("Please enroll in this course to access this lesson.", "warning")
        return redirect(url_for("courses.course_detail", course_id=course.id))

    # All lessons for the curriculum sidebar
    all_lessons = course.lessons.order_by(Lesson.order.asc()).all()

    # Determine next and previous lessons
    lesson_ids = [l.id for l in all_lessons]
    curr_idx = lesson_ids.index(lesson.id)
    prev_lesson = all_lessons[curr_idx - 1] if curr_idx > 0 else None
    next_lesson = all_lessons[curr_idx + 1] if curr_idx < len(all_lessons) - 1 else None

    # Completed lessons set
    completed_ids = set()
    if enrollment and enrollment.completed_lessons:
        completed_ids = {
            int(cid) for cid in enrollment.completed_lessons.split(",") if cid.isdigit()
        }
    is_completed = lesson.id in completed_ids

    # Quiz parsed data
    quiz_questions = parse_quiz_data(lesson.quiz_data) if lesson.content_type == "quiz" else []

    return render_template(
        "courses/lesson_viewer.html",
        course=course,
        lesson=lesson,
        all_lessons=all_lessons,
        prev_lesson=prev_lesson,
        next_lesson=next_lesson,
        enrollment=enrollment,
        is_completed=is_completed,
        completed_ids=completed_ids,
        quiz_questions=quiz_questions,
        is_owner=is_owner,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 12. Complete Lesson
# ─────────────────────────────────────────────────────────────────────────────
@courses_bp.route("/<int:course_id>/lessons/<int:lesson_id>/complete", methods=["POST"])
@login_required
def complete_lesson(course_id: int, lesson_id: int):
    """
    Mark a video, PDF, or text lesson as complete and update progress percent.
    If reaching 100%, record completed_at timestamp and display congratulatory alert.
    """
    course = Course.query.get_or_404(course_id)
    lesson = Lesson.query.filter_by(id=lesson_id, course_id=course.id).first_or_404()

    enrollment = Enrollment.query.filter_by(
        learner_id=current_user.id, course_id=course.id
    ).first()

    if not enrollment:
        flash("You must be enrolled to record lesson progress.", "warning")
        return redirect(url_for("courses.course_detail", course_id=course.id))

    # Append lesson ID avoiding duplicates
    completed_set = {
        cid.strip() for cid in enrollment.completed_lessons.split(",") if cid.strip()
    }
    completed_set.add(str(lesson.id))
    enrollment.completed_lessons = ",".join(sorted(completed_set, key=int))

    # Recalculate progress percentage
    total_lessons = course.lessons.count()
    if total_lessons > 0:
        new_progress = int((len(completed_set) / total_lessons) * 100)
        enrollment.progress_percent = min(100, new_progress)
    else:
        enrollment.progress_percent = 100

    # Course completion trigger
    if enrollment.progress_percent >= 100:
        if not enrollment.completed_at:
            enrollment.completed_at = datetime.utcnow()
            notify(
                user_id=current_user.id,
                title=f"Course Completed: {course.title} 🎓",
                body="Congratulations on finishing all lessons! Your official Certificate of Completion is ready to download.",
                notif_type="course",
                link=url_for("certificates.generate", course_id=course.id),
            )
        flash("🎉 Course complete! Congratulations on finishing all lessons! Your Certificate of Completion is ready to download.", "success")
    else:
        flash(f"Lesson '{lesson.title}' marked as completed! Progress: {enrollment.progress_percent}%.", "success")

    db.session.commit()

    # Move to next lesson if available
    next_lesson = course.lessons.filter(Lesson.order > lesson.order).order_by(Lesson.order.asc()).first()
    if next_lesson:
        return redirect(url_for("courses.lesson_view", course_id=course.id, lesson_id=next_lesson.id))
    return redirect(url_for("courses.lesson_view", course_id=course.id, lesson_id=lesson.id))


# ─────────────────────────────────────────────────────────────────────────────
# 13. Submit Quiz
# ─────────────────────────────────────────────────────────────────────────────
@courses_bp.route("/<int:course_id>/lessons/<int:lesson_id>/quiz-submit", methods=["POST"])
@login_required
def submit_quiz(course_id: int, lesson_id: int):
    """
    Grade submitted quiz answers against Lesson.quiz_data.
    If score >= quiz_pass_score, mark lesson complete and update course progress.
    """
    course = Course.query.get_or_404(course_id)
    lesson = Lesson.query.filter_by(id=lesson_id, course_id=course.id).first_or_404()

    if lesson.content_type != "quiz":
        flash("This lesson does not contain a quiz.", "warning")
        return redirect(url_for("courses.lesson_view", course_id=course.id, lesson_id=lesson.id))

    quiz_questions = parse_quiz_data(lesson.quiz_data)
    total_questions = len(quiz_questions)

    if total_questions == 0:
        flash("This quiz has no questions yet.", "info")
        return redirect(url_for("courses.lesson_view", course_id=course.id, lesson_id=lesson.id))

    correct_count = 0
    for idx, q_data in enumerate(quiz_questions):
        user_choice = request.form.get(f"question_{idx}", type=int)
        expected_choice = int(q_data.get("answer", 0))
        if user_choice is not None and user_choice == expected_choice:
            correct_count += 1

    score_pct = int((correct_count / total_questions) * 100)
    passing_score = lesson.quiz_pass_score or 60

    enrollment = Enrollment.query.filter_by(
        learner_id=current_user.id, course_id=course.id
    ).first()

    if score_pct >= passing_score:
        if enrollment:
            # Mark quiz complete
            completed_set = {
                cid.strip() for cid in enrollment.completed_lessons.split(",") if cid.strip()
            }
            completed_set.add(str(lesson.id))
            enrollment.completed_lessons = ",".join(sorted(completed_set, key=int))

            total_lessons = course.lessons.count()
            if total_lessons > 0:
                enrollment.progress_percent = min(100, int((len(completed_set) / total_lessons) * 100))

            if enrollment.progress_percent >= 100:
                if not enrollment.completed_at:
                    enrollment.completed_at = datetime.utcnow()
                    notify(
                        user_id=current_user.id,
                        title=f"Course Completed: {course.title} 🎓",
                        body="Congratulations on completing the curriculum and quizzes! Your official Certificate of Completion is ready to download.",
                        notif_type="course",
                        link=url_for("certificates.generate", course_id=course.id),
                    )
                flash(f"🎉 Excellent! You passed with {score_pct}% ({correct_count}/{total_questions} correct)! You have completed the entire course! Your certificate is ready.", "success")
            else:
                flash(f"✅ Well done! You passed the quiz with {score_pct}% ({correct_count}/{total_questions} correct). Lesson marked complete!", "success")

            db.session.commit()
        else:
            flash(f"✅ Well done! You scored {score_pct}% on this preview quiz.", "success")
    else:
        flash(
            f"❌ You scored {score_pct}% ({correct_count}/{total_questions} correct). "
            f"Passing score is {passing_score}%. Review the material and try again!",
            "warning",
        )

    return redirect(url_for("courses.lesson_view", course_id=course.id, lesson_id=lesson.id))

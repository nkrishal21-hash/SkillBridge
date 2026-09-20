"""
app/models.py — SkillBridge Database Models
All 13 tables with columns, relationships, and foreign keys.
Uses Flask-SQLAlchemy ORM exclusively (no raw SQL).

Tables:
    users, teacher_profiles, courses, lessons, enrollments,
    bookings, messages, reviews, ratings, payments,
    notifications, certificates, favorites
"""

from datetime import datetime, timedelta
from flask_login import UserMixin
from app import db, bcrypt


# ─────────────────────────────────────────────────────────────────────────────
# 1. USERS
# ─────────────────────────────────────────────────────────────────────────────
class User(db.Model, UserMixin):
    """
    Central user table for all three roles: learner, teacher, admin.
    A single user record exists per account; role determines capabilities.
    """
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)   # NULL for OAuth-only accounts
    role = db.Column(
        db.Enum("learner", "teacher", "admin", name="user_role"),
        nullable=False,
        default="learner"
    )

    # OAuth fields (Google login)
    google_id = db.Column(db.String(100), unique=True, nullable=True)
    profile_photo = db.Column(db.String(500), nullable=True)   # Cloudinary URL

    # Account status
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_email_verified = db.Column(db.Boolean, default=False, nullable=False)
    email_verify_token = db.Column(db.String(200), nullable=True)

    # Password reset
    reset_token = db.Column(db.String(200), nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)

    # Login security
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Relationships ──────────────────────────────────────────────────────────
    teacher_profile = db.relationship(
        "TeacherProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    enrollments = db.relationship("Enrollment", foreign_keys="Enrollment.learner_id", back_populates="learner", lazy="dynamic")
    bookings_as_learner = db.relationship("Booking", foreign_keys="Booking.learner_id", back_populates="learner", lazy="dynamic")
    bookings_as_teacher = db.relationship("Booking", foreign_keys="Booking.teacher_id", back_populates="teacher", lazy="dynamic")
    sent_messages = db.relationship("Message", foreign_keys="Message.sender_id", back_populates="sender", lazy="dynamic")
    received_messages = db.relationship("Message", foreign_keys="Message.receiver_id", back_populates="receiver", lazy="dynamic")
    reviews_given = db.relationship("Review", foreign_keys="Review.learner_id", back_populates="learner", lazy="dynamic")
    payments = db.relationship("Payment", foreign_keys="Payment.learner_id", back_populates="learner", lazy="dynamic")
    notifications = db.relationship("Notification", back_populates="user", lazy="dynamic", cascade="all, delete-orphan")
    certificates = db.relationship("Certificate", back_populates="learner", lazy="dynamic")
    favorites = db.relationship("Favorite", back_populates="learner", lazy="dynamic", cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        """Hash and set the user's password using Flask-Bcrypt."""
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password: str) -> bool:
        """Verify the password against the stored bcrypt hash."""
        if not self.password_hash:
            return False
        return bcrypt.check_password_hash(self.password_hash, password)

    @property
    def is_learner(self) -> bool:
        return self.role == "learner"

    @property
    def is_teacher(self) -> bool:
        return self.role == "teacher"

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_locked(self) -> bool:
        """Check if account is temporarily locked due to excessive failed attempts."""
        if self.locked_until and self.locked_until > datetime.utcnow():
            return True
        return False

    def increment_failed_login(self, max_attempts: int = 5, lock_minutes: int = 15) -> bool:
        """
        Record a failed login attempt. If max_attempts reached, lock for lock_minutes.
        Returns True if newly locked, False otherwise.
        """
        self.failed_login_attempts = (self.failed_login_attempts or 0) + 1
        if self.failed_login_attempts >= max_attempts:
            self.locked_until = datetime.utcnow() + timedelta(minutes=lock_minutes)
            return True
        return False

    def reset_failed_login(self) -> None:
        """Reset failed login count and clear lock on successful authentication."""
        self.failed_login_attempts = 0
        self.locked_until = None

    def __repr__(self):
        return f"<User {self.id}: {self.email} ({self.role})>"


# ─────────────────────────────────────────────────────────────────────────────
# 2. TEACHER PROFILES
# ─────────────────────────────────────────────────────────────────────────────
class TeacherProfile(db.Model):
    """
    Extended profile for users with role='teacher'.
    Created when a teacher completes their profile setup.
    """
    __tablename__ = "teacher_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    # Bio & professional info
    bio = db.Column(db.Text, nullable=True)
    headline = db.Column(db.String(200), nullable=True)        # e.g. "Python Expert | 5 yrs"
    skills = db.Column(db.Text, nullable=True)                 # comma-separated skill tags
    qualifications = db.Column(db.Text, nullable=True)         # degree, certifications
    experience_years = db.Column(db.Integer, default=0)
    teaching_languages = db.Column(db.String(200), nullable=True)

    # Pricing & availability
    hourly_rate = db.Column(db.Numeric(10, 2), nullable=True)  # NPR per hour
    availability = db.Column(db.Text, nullable=True)            # JSON string: {Mon: ["9:00","10:00"], ...}

    # Ratings (pre-calculated for fast search sorting)
    average_rating = db.Column(db.Numeric(3, 2), default=0.00)
    total_reviews = db.Column(db.Integer, default=0)

    # Admin verification
    is_verified = db.Column(db.Boolean, default=False)
    verified_at = db.Column(db.DateTime, nullable=True)

    # Social links (optional)
    linkedin_url = db.Column(db.String(300), nullable=True)
    website_url = db.Column(db.String(300), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Relationships ──────────────────────────────────────────────────────────
    user = db.relationship("User", back_populates="teacher_profile")
    courses = db.relationship("Course", back_populates="teacher", lazy="dynamic")
    reviews = db.relationship("Review", foreign_keys="Review.teacher_id", back_populates="teacher", lazy="dynamic")

    def __repr__(self):
        return f"<TeacherProfile user_id={self.user_id} verified={self.is_verified}>"


# ─────────────────────────────────────────────────────────────────────────────
# 3. COURSES
# ─────────────────────────────────────────────────────────────────────────────
class Course(db.Model):
    """
    A course created by a teacher. Contains multiple lessons and optional quizzes.
    """
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher_profiles.id", ondelete="CASCADE"), nullable=False)

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(100), nullable=True)       # e.g. "Programming", "Design"
    level = db.Column(
        db.Enum("beginner", "intermediate", "advanced", name="course_level"),
        default="beginner"
    )
    language = db.Column(db.String(50), default="English")
    thumbnail_url = db.Column(db.String(500), nullable=True)  # Cloudinary URL
    price = db.Column(db.Numeric(10, 2), default=0.00)        # 0 = free
    is_published = db.Column(db.Boolean, default=False)

    # Approval by admin before listing publicly
    is_approved = db.Column(db.Boolean, default=False)
    approved_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Relationships ──────────────────────────────────────────────────────────
    teacher = db.relationship("TeacherProfile", back_populates="courses")
    lessons = db.relationship("Lesson", back_populates="course", lazy="dynamic", cascade="all, delete-orphan", order_by="Lesson.order")
    enrollments = db.relationship("Enrollment", back_populates="course", lazy="dynamic")
    certificates = db.relationship("Certificate", back_populates="course", lazy="dynamic")

    def __repr__(self):
        return f"<Course {self.id}: '{self.title}'>"


# ─────────────────────────────────────────────────────────────────────────────
# 4. LESSONS
# ─────────────────────────────────────────────────────────────────────────────
class Lesson(db.Model):
    """
    A single lesson within a course. Supports video, PDF notes, and quiz.
    """
    __tablename__ = "lessons"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    order = db.Column(db.Integer, default=1)                  # lesson sequence within course
    content_type = db.Column(
        db.Enum("video", "pdf", "text", "quiz", name="lesson_type"),
        default="video"
    )
    video_url = db.Column(db.String(500), nullable=True)      # Cloudinary video URL
    pdf_url = db.Column(db.String(500), nullable=True)        # Cloudinary PDF URL
    text_content = db.Column(db.Text, nullable=True)          # rich-text body
    duration_minutes = db.Column(db.Integer, nullable=True)   # for display

    # Quiz data stored as JSON string: [{"question": "...", "options": [...], "answer": 0}, ...]
    quiz_data = db.Column(db.JSON, nullable=True)
    quiz_pass_score = db.Column(db.Integer, default=60)       # % to pass

    is_preview = db.Column(db.Boolean, default=False)         # free preview before enrollment
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Relationships ──────────────────────────────────────────────────────────
    course = db.relationship("Course", back_populates="lessons")

    def __repr__(self):
        return f"<Lesson {self.id}: '{self.title}' (course={self.course_id})>"


# ─────────────────────────────────────────────────────────────────────────────
# 5. ENROLLMENTS
# ─────────────────────────────────────────────────────────────────────────────
class Enrollment(db.Model):
    """
    Tracks a learner's enrollment in a course, including lesson progress.
    """
    __tablename__ = "enrollments"

    id = db.Column(db.Integer, primary_key=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)

    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    # Progress: comma-separated lesson IDs the learner has completed
    completed_lessons = db.Column(db.Text, default="")        # e.g. "1,3,5"
    progress_percent = db.Column(db.Integer, default=0)       # 0-100

    # Payment reference (NULL if course is free)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id", ondelete="SET NULL"), nullable=True)

    # ── Unique constraint: one enrollment per learner-course pair ──────────────
    __table_args__ = (
        db.UniqueConstraint("learner_id", "course_id", name="uq_enrollment"),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    learner = db.relationship("User", foreign_keys=[learner_id], back_populates="enrollments")
    course = db.relationship("Course", back_populates="enrollments")
    payment = db.relationship("Payment", foreign_keys=[payment_id])

    def __repr__(self):
        return f"<Enrollment learner={self.learner_id} course={self.course_id} {self.progress_percent}%>"


# ─────────────────────────────────────────────────────────────────────────────
# 6. BOOKINGS
# ─────────────────────────────────────────────────────────────────────────────
class Booking(db.Model):
    """
    1-on-1 mentorship session booking between a learner and a teacher.
    Teacher must approve before the Jitsi room is activated.
    """
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Session timing
    session_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False, default=60)

    # Topic & notes
    topic = db.Column(db.String(300), nullable=True)
    learner_notes = db.Column(db.Text, nullable=True)

    # Booking workflow status
    status = db.Column(
        db.Enum("pending", "approved", "rejected", "completed", "cancelled", name="booking_status"),
        default="pending",
        nullable=False
    )
    teacher_response_note = db.Column(db.Text, nullable=True)

    # Price at time of booking (snapshot — teacher rate may change later)
    amount = db.Column(db.Numeric(10, 2), nullable=True)

    # Jitsi room name (unique per booking, set on approval)
    jitsi_room = db.Column(db.String(200), nullable=True)

    # Payment
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id", ondelete="SET NULL"), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Relationships ──────────────────────────────────────────────────────────
    learner = db.relationship("User", foreign_keys=[learner_id], back_populates="bookings_as_learner")
    teacher = db.relationship("User", foreign_keys=[teacher_id], back_populates="bookings_as_teacher")
    payment = db.relationship("Payment", foreign_keys=[payment_id])
    review = db.relationship("Review", back_populates="booking", uselist=False)

    def __repr__(self):
        return f"<Booking {self.id}: learner={self.learner_id} teacher={self.teacher_id} {self.status}>"


# ─────────────────────────────────────────────────────────────────────────────
# 7. MESSAGES
# ─────────────────────────────────────────────────────────────────────────────
class Message(db.Model):
    """
    Persisted chat messages sent via Flask-SocketIO.
    Indexed on sender+receiver and timestamp for fast inbox queries.
    """
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    body = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Optional: attach message to a booking context
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────────
    sender = db.relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    receiver = db.relationship("User", foreign_keys=[receiver_id], back_populates="received_messages")

    def __repr__(self):
        return f"<Message {self.id}: from={self.sender_id} to={self.receiver_id}>"


# ─────────────────────────────────────────────────────────────────────────────
# 8. REVIEWS
# ─────────────────────────────────────────────────────────────────────────────
class Review(db.Model):
    """
    Written review + star rating left by a learner after a booking or course.
    One review per learner per booking.
    """
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher_profiles.id", ondelete="CASCADE"), nullable=False)

    # Either a booking review OR a course review (one must be non-null)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)

    rating_value = db.Column(db.Integer, nullable=False)      # 1-5 stars
    review_text = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("learner_id", "booking_id", name="uq_review_booking"),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    learner = db.relationship("User", foreign_keys=[learner_id], back_populates="reviews_given")
    teacher = db.relationship("TeacherProfile", foreign_keys=[teacher_id], back_populates="reviews")
    booking = db.relationship("Booking", back_populates="review")

    def __repr__(self):
        return f"<Review {self.id}: {self.rating_value}⭐ by learner={self.learner_id}>"


# ─────────────────────────────────────────────────────────────────────────────
# 9. RATINGS  (aggregate snapshot — updated after each review)
# ─────────────────────────────────────────────────────────────────────────────
class Rating(db.Model):
    """
    Stores individual numeric ratings separate from review text,
    allowing fast aggregation queries on the search page.
    Each row corresponds to a single star-rating event.
    """
    __tablename__ = "ratings"

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher_profiles.id", ondelete="CASCADE"), nullable=False)
    learner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    value = db.Column(db.Integer, nullable=False)              # 1-5
    rated_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Relationships ──────────────────────────────────────────────────────────
    teacher = db.relationship("TeacherProfile")
    learner = db.relationship("User")

    def __repr__(self):
        return f"<Rating teacher={self.teacher_id} value={self.value}>"


# ─────────────────────────────────────────────────────────────────────────────
# 10. PAYMENTS
# ─────────────────────────────────────────────────────────────────────────────
class Payment(db.Model):
    """
    Payment record for course enrollments or session bookings.
    Supports eSewa and Khalti sandbox gateways.
    Status is updated via payment gateway callback.
    """
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # What was paid for
    payment_for = db.Column(
        db.Enum("course", "booking", name="payment_for_type"),
        nullable=False
    )
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    booking_id_ref = db.Column(db.Integer, nullable=True)     # soft reference to avoid circular FK

    # Amount
    amount = db.Column(db.Numeric(10, 2), nullable=False)     # NPR
    currency = db.Column(db.String(10), default="NPR")

    # Gateway info
    gateway = db.Column(
        db.Enum("esewa", "khalti", name="payment_gateway"),
        nullable=False
    )
    gateway_transaction_id = db.Column(db.String(200), nullable=True)  # returned by gateway
    gateway_reference_id = db.Column(db.String(200), nullable=True)    # our order ID sent to gateway

    # Status
    status = db.Column(
        db.Enum("initiated", "success", "failed", "refunded", name="payment_status"),
        default="initiated",
        nullable=False
    )

    initiated_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    # ── Platform Commission & Teacher Payout (added post-Phase-9) ─────────────
    # Computed on eSewa success callback: 20% platform / 80% teacher.
    # NULL on rows created before this feature was deployed (backfilled by db_init.py).
    platform_fee_amount = db.Column(db.Numeric(10, 2), nullable=True)
    teacher_payout_amount = db.Column(db.Numeric(10, 2), nullable=True)
    payout_status = db.Column(
        db.Enum("pending", "released", name="payout_status"),
        default="pending",
        nullable=False,
    )
    payout_released_at = db.Column(db.DateTime, nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────────
    learner = db.relationship("User", foreign_keys=[learner_id], back_populates="payments")
    course = db.relationship("Course")

    # ── Helper properties ──────────────────────────────────────────────────────
    @property
    def teacher_user(self):
        """Return the teacher User for this payment (works for both course and booking payments)."""
        if self.payment_for == "course" and self.course and self.course.teacher:
            return self.course.teacher.user
        if self.payment_for == "booking" and self.booking_id_ref:
            from app.models import Booking as _Booking
            booking = _Booking.query.get(self.booking_id_ref)
            if booking:
                return booking.teacher
        return None

    @property
    def teacher_profile(self):
        """Return the TeacherProfile for this payment."""
        if self.payment_for == "course" and self.course:
            return self.course.teacher
        if self.payment_for == "booking" and self.booking_id_ref:
            from app.models import Booking as _Booking
            booking = _Booking.query.get(self.booking_id_ref)
            if booking:
                return booking.teacher.teacher_profile if booking.teacher else None
        return None

    @property
    def item_title(self):
        """Return a human-readable title for the paid item."""
        if self.payment_for == "course" and self.course:
            return self.course.title
        if self.payment_for == "booking" and self.booking_id_ref:
            from app.models import Booking as _Booking
            booking = _Booking.query.get(self.booking_id_ref)
            if booking:
                return f"1-on-1 Mentorship: {booking.topic}"
        return "SkillBridge Order"

    def __repr__(self):
        return f"<Payment {self.id}: {self.gateway} {self.status} NPR {self.amount}>"


# ─────────────────────────────────────────────────────────────────────────────
# 11. NOTIFICATIONS
# ─────────────────────────────────────────────────────────────────────────────
class Notification(db.Model):
    """
    In-app notification bell entries.  Created by system events
    (booking approved, new message, course completed, etc.).
    """
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=True)
    notif_type = db.Column(db.String(50), nullable=True)       # 'booking', 'message', 'payment', etc.
    link = db.Column(db.String(300), nullable=True)            # optional URL to redirect on click
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # ── Relationships ──────────────────────────────────────────────────────────
    user = db.relationship("User", back_populates="notifications")

    def __repr__(self):
        return f"<Notification {self.id}: user={self.user_id} read={self.is_read}>"


# ─────────────────────────────────────────────────────────────────────────────
# 12. CERTIFICATES
# ─────────────────────────────────────────────────────────────────────────────
class Certificate(db.Model):
    """
    PDF certificate issued when a learner completes a course.
    PDF is generated with ReportLab and stored on Cloudinary.
    """
    __tablename__ = "certificates"

    id = db.Column(db.Integer, primary_key=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)

    # Unique code for verification (printed on PDF)
    certificate_code = db.Column(db.String(50), unique=True, nullable=False)

    # Cloudinary URL to the generated PDF
    pdf_url = db.Column(db.String(500), nullable=True)

    issued_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("learner_id", "course_id", name="uq_certificate"),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    learner = db.relationship("User", back_populates="certificates")
    course = db.relationship("Course", back_populates="certificates")

    def __repr__(self):
        return f"<Certificate {self.certificate_code}: learner={self.learner_id} course={self.course_id}>"


# ─────────────────────────────────────────────────────────────────────────────
# 13. FAVORITES
# ─────────────────────────────────────────────────────────────────────────────
class Favorite(db.Model):
    """
    Learner's saved/favorited teachers for quick access from dashboard.
    """
    __tablename__ = "favorites"

    id = db.Column(db.Integer, primary_key=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher_profiles.id", ondelete="CASCADE"), nullable=False)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("learner_id", "teacher_id", name="uq_favorite"),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    learner = db.relationship("User", back_populates="favorites")
    teacher = db.relationship("TeacherProfile")

    def __repr__(self):
        return f"<Favorite learner={self.learner_id} teacher={self.teacher_id}>"


# ─────────────────────────────────────────────────────────────────────────────
# 14. REPORTS
# ─────────────────────────────────────────────────────────────────────────────
class Report(db.Model):
    """
    Incident reports filed by learners or teachers for sessions/behavior.
    Reviewed by administrators for disciplinary action or refunds.
    """
    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reported_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True)
    reason = db.Column(db.Enum("late", "no_show", "misbehavior", "other", name="report_reason"), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.Enum("pending", "reviewed", "resolved", "dismissed", name="report_status"), default="pending", nullable=False)
    admin_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)

    reporter = db.relationship("User", foreign_keys=[reporter_id])
    reported = db.relationship("User", foreign_keys=[reported_id])
    booking = db.relationship("Booking")

    def __repr__(self):
        return f"<Report {self.id}: {self.reason} status={self.status}>"


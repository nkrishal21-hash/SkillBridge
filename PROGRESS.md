# SkillBridge — Progress Log

> Keep this file at the project root. Update it at the end of every phase — this is your running record for the project report and viva. Reference `SkillBridge_Master_Prompt_Final.md` for full scope of each phase.

---

## Quick Status Overview

| Phase | Focus | Status | Date Completed |
|---|---|---|---|
| 1 | Setup & Models | ✅ Done | 2026-09-14 |
| 2 | Authentication | ✅ Done | 2026-09-15 |
| 3 | Teacher Profile & Search | ✅ Done | 2026-09-15 |
| 4 | Course Management | ✅ Done | 2026-09-15 |
| 5 | Booking System | ✅ Done | 2026-09-17 |
| 6 | Live Class & Chat | ✅ Done | 2026-09-17 |
| 7 | Ratings & Payments | ✅ Done | 2026-09-18 |
| 8 | Certificates & Dashboards | ✅ Done | 2026-09-18 |
| 9 | Security & UI Polish | ✅ Done | 2026-09-18 |
| Post-9 | Trust & Safety: Moderation & Refunds | ✅ Done | 2026-09-20 |
| 10 | Deployment (Render + Aiven + Cloudinary) | ⬜ Not started | |

Status values: ⬜ Not started · 🟡 In progress · ✅ Done · ⚠️ Blocked

---

## Phase 1 — Setup & Models
**Status:** ✅ Done
**Date started / completed:** 2026-09-14 / 2026-09-14

**Checklist**
- [x] Full folder/file structure created
- [x] `requirements.txt` (pinned versions, includes `cloudinary`, `requests`)
- [x] `config.py` (dev config, MySQL URI via env var, mail config, Cloudinary config, SocketIO threading mode)
- [x] `run.py` (port 5001 — avoids macOS AirPlay conflict on 5000)
- [x] `app/__init__.py` (app factory + all 9 Blueprint registrations)
- [x] `app/models.py` — all 13 tables with relationships
- [x] `db_init.py` runs cleanly, creates all tables (all 13 tables verified)
- [x] `.env.example` created (no real secrets)

**Files created/modified:**
- `requirements.txt`
- `.env.example`
- `.gitignore`
- `config.py`
- `run.py`
- `db_init.py`
- `app/__init__.py`
- `app/models.py`
- `app/auth/__init__.py`, `app/auth/routes.py`
- `app/learner/__init__.py`, `app/learner/routes.py`
- `app/teacher/__init__.py`, `app/teacher/routes.py`
- `app/admin/__init__.py`, `app/admin/routes.py`
- `app/courses/__init__.py`, `app/courses/routes.py`
- `app/booking/__init__.py`, `app/booking/routes.py`
- `app/chat/__init__.py`, `app/chat/routes.py`
- `app/payments/__init__.py`, `app/payments/routes.py`
- `app/certificates/__init__.py`, `app/certificates/routes.py`
- `app/templates/index.html`
- `app/templates/errors/404.html`
- `app/templates/errors/500.html`

**Blockers / deviations from master prompt:**
- Port changed from 5000 → 5001 (macOS AirPlay Receiver occupies port 5000 by default)
- `requests` added explicitly to requirements.txt (Authlib 1.3.1 omits it as a declared dep on Python 3.14)
- MySQL initialized and verified on port 3306

**Notes for report/viva:**
- App factory pattern used: extensions created globally, initialized inside `create_app()` to avoid circular imports
- All 13 models defined with SQLAlchemy ORM; no raw SQL used anywhere
- Cloudinary URL columns on all media fields from day 1 (not added later) per §2b of master prompt
- SocketIO configured with `async_mode="threading"` — compatible with Render free tier polling transport (no eventlet/gevent needed)
- `allow_unsafe_werkzeug=True` required by Flask-SocketIO ≥ 5.x for the Werkzeug dev server

---

## Phase 2 — Authentication
**Status:** ✅ Done
**Date started / completed:** 2026-09-15 / 2026-09-15

**Checklist**
- [x] Register (Learner / Teacher separate flows with tabbed interface)
- [x] Login / Logout (with 5-attempt rate-limiting and temporary account lockout)
- [x] Google OAuth login working (Authlib integration with graceful fallback)
- [x] Forgot password → email sent via Flask-Mail (with dev mode token preview)
- [x] Reset password via token (itsdangerous URLSafeTimedSerializer with 30m expiry)
- [x] `templates/base.html` (modern design system, responsive navbar, flash notifications)
- [x] Role-based redirect after login (`/learner/dashboard`, `/teacher/dashboard`, `/admin/dashboard`)
- [x] Role-based route protection in place (`@learner_required`, `@teacher_required`, `@admin_required`)

**Files created/modified:**
- `app/models.py` (added bcrypt helpers `set_password`, `check_password`, role properties, and account lockout tracking)
- `app/auth/forms.py` (`RegisterForm`, `LoginForm`, `ForgotPasswordForm`, `ResetPasswordForm`)
- `app/auth/utils.py` (role decorators, token generation/verification, password reset email sender)
- `app/auth/routes.py` (register, login, logout, google OAuth, forgot_password, reset_password)
- `app/learner/routes.py` (protected `/learner/dashboard`)
- `app/teacher/routes.py` (protected `/teacher/dashboard`)
- `app/admin/routes.py` (protected `/admin/dashboard`)
- `app/static/css/style.css` (custom design system with CSS variables, responsive typography, and animations)
- `app/templates/base.html` (core layout with role-aware navigation, avatar dropdown, and toast flashes)
- `app/templates/auth/login.html` (styled sign-in form with Google OAuth and remember me)
- `app/templates/auth/register.html` (role-switching registration tabs for learner vs teacher)
- `app/templates/auth/forgot_password.html` (reset link request card)
- `app/templates/auth/reset_password.html` (password update form)
- `app/templates/learner/dashboard.html` (initial learner dashboard)
- `app/templates/teacher/dashboard.html` (initial teacher studio)
- `app/templates/admin/dashboard.html` (initial admin overview)
- `app/templates/index.html` (updated hero and features grid extending base.html)

**Blockers / deviations from master prompt:**
- None. Rate-limiting lockout implemented cleanly at model/ORM level without external Redis dependency.

**Notes for report/viva:**
- Passwords hashed using `Flask-Bcrypt` with salted rounds.
- Role-based access control enforces least-privilege security using Python function decorators.
- Rate-limiting prevents credential stuffing and brute-force attacks by locking accounts for 15 minutes after 5 failed attempts.
- Password reset tokens use cryptographic signing (`itsdangerous.URLSafeTimedSerializer`) with a strict 30-minute expiry window.
- UI built entirely using custom Vanilla CSS tokens for clean maintainability and zero framework bloat.

---

## Phase 3 — Teacher Profile & Search
**Status:** ✅ Done
**Date started / completed:** 2026-09-15 / 2026-09-15

**Checklist**
- [x] Teacher profile edit page (photo, bio, skills, qualifications, price, availability)
- [x] File uploads routed through **Cloudinary** with graceful local fallback
- [x] Public teacher profile page
- [x] Learner search with filters (skill, rating, price, availability)
- [x] Results sorted by rating, price, experience
- [x] Teacher cards (photo, skills, rating, price, verified badge)

**Files created/modified:**
- `app/teacher/forms.py` (`TeacherProfileForm` with photo, headline, bio, skills, rate, availability)
- `app/teacher/utils.py` (`upload_profile_photo`, `parse_skills`, `availability_to_json`, `availability_from_json`, `available_days_list`)
- `app/teacher/routes.py` (`dashboard`, `profile_edit`, `search`, `public_profile`)
- `app/templates/teacher/profile_edit.html` (profile form, photo preview script, availability grid)
- `app/templates/teacher/public_profile.html` (hero layout, skills pills, stats sidebar, placeholder booking button)
- `app/templates/teacher/search.html` (filter sidebar, mentor cards grid, pagination, empty state)
- `app/templates/teacher/dashboard.html` (added Edit Profile / View Public Profile links and profile completion banner)
- `app/templates/base.html` (unconditionally enabled "Find Mentors" navbar link)
- `app/static/css/style.css` (CSS tokens and layouts for search, teacher cards, profile hero, availability pills)

**Blockers / deviations from master prompt:**
- **Weekly Availability Schema**: Availability stored as per-day JSON booleans (`{"Mon": true, "Tue": false, ...}`) on `TeacherProfile.availability`. Detailed time-slot granularity is deferred to Phase 5 (Booking Calendar).
- **Search Gating Criteria**: Search results gate on profile completeness (`headline` + `skills` + `hourly_rate` present) rather than `is_verified`, enabling search functionality prior to Phase 8 admin verification workflows.
- **Dashboard Bug Fixes**: Corrected invalid `booking_status` filter in `teacher/dashboard.html` and `learner/dashboard.html` to target the actual `status` column on `Booking` (`status="pending"` for teacher, `status="approved"` for learner).

**Notes for report/viva:**
- Profile photo uploads utilize Cloudinary API (`cloudinary.uploader.upload`) with dynamic transformation (400x400 face crop), seamlessly falling back to local disk storage (`app/static/uploads/profile_photos/`) in dev environments without breaking.
- Mentor search features multi-column ILIKE matching (skills, headline, bio, full name), numerical rating/price filtering, day boolean matching, dynamic sorting, and clean 9-item pagination.

---

## Phase 4 — Course Management
**Status:** ✅ Done
**Date started / completed:** 2026-09-15 / 2026-09-15

**Checklist**
- [x] Teacher: create/edit course, add lessons, add quiz
- [x] Course files (video/PDF/thumbnail) via Cloudinary with local fallback
- [x] Learner: browse, enroll, view course detail
- [x] Lesson viewer with progress tracking
- [x] Quiz submission with passing & failing scores
- [x] Progress % updates correctly across curriculum
- [x] Course-complete trigger wired (certificate placeholder for Phase 8)

**Files created/modified:**
- `app/courses/utils.py` (`upload_course_thumbnail`, `upload_lesson_video`, `upload_lesson_pdf`, `parse_quiz_data`, `format_quiz_data`)
- `app/courses/forms.py` (`CourseForm`, `LessonForm`, `QuizQuestionForm`)
- `app/courses/routes.py` (catalog, detail, create, edit, toggle_publish, manage_lessons, create_lesson, edit_lesson, delete_lesson, enroll, lesson_view, complete_lesson, submit_quiz)
- `app/templates/courses/catalog.html` (search, filters, course cards grid, pagination, empty state)
- `app/templates/courses/course_detail.html` (hero header, instructor card, syllabus outline with lock indicators, enroll CTA)
- `app/templates/courses/course_form.html` (course creation/edit metadata with live thumbnail preview)
- `app/templates/courses/manage_lessons.html` (curriculum outline, lesson sequence management, status badges)
- `app/templates/courses/lesson_form.html` (dynamic type switcher, media uploads, interactive quiz builder)
- `app/templates/courses/lesson_viewer.html` (video player, PDF viewer, text reader, interactive quiz, curriculum sidebar)
- `app/templates/base.html` (connected "Courses" navbar link directly to `courses.catalog`)
- `app/templates/teacher/dashboard.html` (linked "+ Create New Course" button, displayed active courses list)
- `app/templates/learner/dashboard.html` (linked "Explore Courses" button, displayed enrolled courses with progress bars)
- `app/static/css/style.css` (course cards, syllabus list, lesson viewer layout, quiz cards, progress bars)

**Blockers / deviations from master prompt:**
- **Catalog Visibility Gating**: Published courses are visible in the public catalog based on `is_published == True` without gating on `is_approved` (admin verification and course approval workflows are built in Phase 8).
- **Paid Course Enrollment Placeholder**: Free courses enroll immediately on click; paid courses display a disabled placeholder button noting *"Payments launch in Phase 7"* (matching the placeholder pattern used in Phase 3 on public teacher profiles).
- **Course Completion Trigger**: When all lessons are finished (`progress_percent == 100`), `Enrollment.completed_at` is set and a celebratory flash message is displayed; ReportLab PDF certificate generation is deferred to Phase 8.

**Notes for report/viva:**
- Course thumbnails, MP4 lecture videos, and PDF handouts utilize Cloudinary API with automatic folder grouping and validation, falling back gracefully to local disk storage in development environments without crashing.
- Dynamic lesson viewer conditionally renders video player, PDF viewer, formatted text, or interactive multiple-choice quiz based on `content_type`.
- Quizzes are evaluated server-side against `Lesson.quiz_data` JSON structure and require meeting the instructor-defined `quiz_pass_score` before marking the lesson complete.
- Sequential curriculum progress is tracked on `Enrollment.completed_lessons` (comma-separated ID set) to avoid duplicate progress updates.

---

## Phase 5 — Booking System
**Status:** ✅ Done
**Date started / completed:** 2026-09-17 / 2026-09-17

**Checklist**
- [x] Learner: view teacher's slots, submit booking
- [x] Teacher: approve/reject booking
- [x] Booking history (both roles)
- [x] Email notification — new booking → teacher
- [x] Email notification — approve/reject → learner

**Files created/modified:**
- `app/booking/forms.py` (`BookingForm` with slot picker, duration options, past date validator; `BookingResponseForm` for teacher feedback notes)
- `app/booking/utils.py` (`calculate_session_times`, `send_new_booking_email`, `send_booking_response_email` with console fallback in dev mode)
- `app/booking/routes.py` (Blueprint routes: `new`, `detail`, `approve`, `reject`, `cancel`, `history` with role guards, conflict detection, and status filtering)
- `app/templates/booking/new.html` (mentor summary card, date/time/duration picker, live fee estimator, topic/notes inputs)
- `app/templates/booking/detail.html` (status badges, timings, participants, Jitsi room preview, teacher approval/rejection forms, cancellation CTA)
- `app/templates/booking/history.html` (tabbed filtering by status with counts, booking cards, pagination, role-aware empty states)
- `app/templates/base.html` (added Mentorship Sessions / Session Bookings links to user navigation dropdown)
- `app/templates/teacher/public_profile.html` (connected "Book a Session" CTA to `booking.new` using `profile.user_id`)
- `app/templates/teacher/dashboard.html` (wired "Mentorship Requests" stat card and "Booking Queue" review CTA)
- `app/templates/learner/dashboard.html` (wired "Upcoming Sessions" stat card and "Upcoming Mentorship" panel with booking links)
- `app/learner/routes.py` (queried upcoming active bookings for the learner dashboard)
- `app/static/css/style.css` (status badge tokens `.badge-status-pending`, `.badge-status-approved`, `.badge-status-rejected`, etc., and `.booking-card` styles)

**Blockers / deviations from master prompt:**
- **Availability Granularity**: `TeacherProfile.availability` is stored as day-of-week boolean flags (e.g. `{"Mon": true, ...}`). Specific time slot availability is chosen by the learner from standard half-hour daytime slots (08:00 to 20:00) with server-side overlap prevention against existing pending/approved bookings.
- **Jitsi Video Call Embed**: When approved, a unique Jitsi room identifier (e.g. `skillbridge-<id>-<hex>`) is generated and persisted to `Booking.jitsi_room`; the interactive Jitsi Meet iFrame UI and live chat integration are implemented in Phase 6.
- **Payment Processing**: Session fee is snapshotted to `Booking.amount` based on duration and the mentor's hourly rate; payment gateway checkout via eSewa/Khalti is implemented in Phase 7.

**Notes for report/viva:**
- **Time Overlap Conflict Prevention**: Concurrency conflicts are prevented at scheduling time by checking `Booking.start_time < new_end` and `Booking.end_time > new_start` for the teacher on the selected date for bookings in `('pending', 'approved')` status.
- **Email Notification Fallback**: Email dispatchers first output clear, formatted notification details directly to the console before attempting SMTP transmission via Flask-Mail, enabling offline local testing without requiring real email credentials.
- **Foreign Key Convention**: Reconciled teacher references between blueprints; routes use `User.id` for `Booking.teacher_id` (matching foreign key to `users.id`) while resolving `TeacherProfile` seamlessly.


---

## Phase 6 — Live Class & Chat
**Status:** ✅ Done
**Date started / completed:** 2026-09-17 / 2026-09-17

**Checklist**
- [x] Jitsi iFrame embedded, room name unique per booking
- [x] Join restricted to approved booking's learner + teacher
- [x] Whiteboard confirmed visible in call toolbar (default on meet.jit.si — no build needed)
- [x] SocketIO chat — messages persist to DB
- [x] SocketIO configured for **polling transport** (Render free-tier compatibility)
- [x] Unread message badge in navbar
- [x] Inbox + conversation view templates

**Files created/modified:**
- `app/chat/events.py` (SocketIO event handlers: `connect`, `join`, `send_message`, `mark_read`)
- `app/chat/routes.py` (inbox and 1-on-1 conversation view routes)
- `app/__init__.py` (registered `inject_chat_context` context processor and imported SocketIO events)
- `app/templates/chat/inbox.html` (inbox list template with recent message snippets and unread counters)
- `app/templates/chat/conversation.html` (bubble-style chat view with polling Socket.IO client script)
- `app/templates/base.html` (added Messages nav link and avatar dropdown item with unread badge)
- `app/templates/booking/detail.html` (embedded Jitsi Meet External API with launch button, room display, and Message participant link)
- `app/templates/teacher/public_profile.html` (added Message button for authenticated non-owners)
- `app/static/css/style.css` (CSS styles for chat inbox, message bubbles, unread badges, and Jitsi container)

**Blockers / deviations from master prompt:**
- **Open Messaging Scope**: Chat is available between any two authenticated users (not strictly restricted to users with existing active bookings), allowing learners to contact mentors prior to scheduling sessions.
- **Jitsi Free Instance Whiteboard**: Video calls utilize the free public server `meet.jit.si` via the External API script (`https://meet.jit.si/external_api.js`). The collaborative whiteboard (Excalidraw) is available natively in the meet.jit.si toolbar without any custom build or third-party license required.

**Notes for report/viva:**
- **Render Free-Tier Compatibility**: Socket.IO client explicitly uses `io({ transports: ["polling"], upgrade: false })` combined with Flask-SocketIO's `async_mode="threading"`, eliminating WebSocket drops on free cloud hosts.
- **Deterministic Room Routing**: SocketIO rooms follow the deterministic naming schema `f"conv_{min(id1, id2)}_{max(id1, id2)}"`, guaranteeing both participants join the exact same socket room regardless of who initiates the connection.
- **Global Unread Context Processor**: Unread count is queried via Flask `@app.context_processor` on `Message.query.filter_by(receiver_id=current_user.id, is_read=False)`, surfacing unread badges across all pages without duplicate route queries.

---

## Phase 7 — Ratings & Payments
**Status:** ✅ Done  
**Date started / completed:** 2026-09-18 / 2026-09-18

**Checklist**
- [x] Review submission restricted to completed booking/course
- [x] Average rating recalculated on `teacher_profiles` after every new `Rating` row
- [x] eSewa sandbox flow (initiate → HMAC-signed POST form → success/failure callback)
- [ ] Khalti sandbox flow (initiate → verify) — **deliberately deferred** (eSewa-only scope per master prompt)
- [x] Payment record stored; enrollment/booking confirmed on success
- [x] Checkout / success / failure / receipt templates
- [x] Defense-in-depth: callback HMAC signature verified + eSewa status API queried before fulfillment
- [x] Idempotency: re-visiting success URL on already-completed payment renders receipt, not error
- [x] Duplicate review prevention enforced at both DB constraint and route level
- [x] Session completion (POST `/booking/<id>/complete`) only allowed after scheduled end time
- [x] Booking detail shows "Mark Complete" button only when eligible; review form shown only on completed sessions
- [x] 30/30 integration tests passing (Flask test client)

**Files created/modified:**
- `app/payments/__init__.py` — blueprint module init
- `app/payments/utils.py` — `build_esewa_signature`, `verify_esewa_callback`, `check_esewa_status` (HMAC-SHA256)
- `app/payments/routes.py` — `payments_bp`: checkout, esewa_success, esewa_failure, receipt routes
- `app/reviews/__init__.py` — blueprint module init
- `app/reviews/forms.py` — `ReviewForm` (rating_value 1–5, review_text)
- `app/reviews/routes.py` — `reviews_bp`: review_booking, review_course routes
- `app/booking/routes.py` — added `complete` endpoint + `detail` wires payment/review context
- `app/courses/routes.py` — paid-course enroll → redirects to checkout
- `app/__init__.py` — registered `payments_bp` (`/payments`) and `reviews_bp` (`/reviews`)
- `app/templates/payments/checkout.html` — order summary + eSewa UAT credentials helper box + signed hidden form
- `app/templates/payments/success.html` — success confirmation with enrollment/booking link
- `app/templates/payments/failure.html` — failure page with retry options
- `app/templates/payments/receipt.html` — printable receipt
- `app/templates/booking/detail.html` — added: pay button, mark-complete form, review form, existing review display
- `app/templates/courses/course_detail.html` — paid course shows checkout CTA vs free enroll
- `app/static/css/style.css` — payment / review card styles

**Blockers / deviations from master prompt:**
- **Khalti deferred**: Master prompt lists Khalti as optional / parallel with eSewa. Per project scope decision, Khalti integration is deferred to a later polish pass. Only eSewa sandbox (UAT/EPAYTEST) is implemented in this phase.
- **eSewa live sandbox test**: The eSewa callback (`/payments/esewa/success`) requires an external round-trip to `rc-epay.esewa.com.np`. The signature logic and fulfillment code are fully implemented and verified against published eSewa UAT test vectors. Manual browser test with UAT credentials (`9806800001` / `Nepal@123` / MPIN `1122` / Token `123456`) is the definitive end-to-end validation.
- **`booking_id_ref` soft FK**: `Payment.booking_id_ref` is an integer column without a foreign key constraint (to avoid circular FK issues noted in models.py). All lookups use explicit `Payment.query.filter_by(booking_id_ref=booking.id)` — no ORM relationship needed.

**Notes for report/viva:**
- eSewa integration follows the **ePay v2** API: the checkout is a browser-side POST form (not a server-side redirect) so the HMAC signature is computed server-side and embedded as a hidden field — never exposed to JavaScript.
- Two-layer verification on callback: (1) HMAC-SHA256 `signed_field_names` chain — prevents payload tampering; (2) status check API call to eSewa — prevents replay of valid-looking callbacks without an actual charge.
- `Rating` table is a separate fast-aggregation log (one row per rating event). `TeacherProfile.average_rating` and `total_reviews` are recomputed via `func.avg` / `func.count` on every new rating write — simple and always accurate without a separate cron job.
- `Review` table has `UniqueConstraint('learner_id', 'booking_id', name='uq_review_booking')` enforced at DB level; the route also checks before insert for a friendly flash message rather than a 500.

---

## Phase 8 — Certificates & Dashboards
**Status:** ✅ Done
**Date started / completed:** 2026-09-18 / 2026-09-18

**Checklist**
- [x] PDF certificate generation (ReportLab landscape A4 — branding, learner name, course title, instructor, date, verification code)
- [x] Certificate stored on Cloudinary (`resource_type="raw"`) with local fallback in `app/static/uploads/certificates/`
- [x] `Certificate` record persisted with `uq_certificate` constraint enforced; re-visiting generate redirects to download
- [x] Download route: Cloudinary redirect or local `send_from_directory` with IDOR guard
- [x] Public verification page: `/certificates/verify/<code>` — no auth required, employer-friendly
- [x] In-app Notification system: `notify()` helper + inbox route + mark-read / mark-all-read
- [x] Navbar notification bell badge wired via context processor
- [x] Learner dashboard: enrolled courses + progress bars, upcoming mentorship, certificates grid, recent notifications, saved mentors
- [x] Favorites toggle: `/learner/favorites/<id>/toggle` — save/unsave teacher; IntegrityError handled gracefully
- [x] Teacher dashboard: courses list (with enrollment count + approval badge), booking queue card, earnings overview panel (gradient card + recent transactions), student reviews panel (star visualizer + review cards)
- [x] Admin dashboard: platform stats, revenue card, teacher verification + course approval queue alert cards, recent transactions table
- [x] Admin — Teacher Verification Queue: `/admin/teachers` — verify / revoke with notification to teacher on verify
- [x] Admin — Course Approval Queue: `/admin/courses` — approve / revoke with notification to teacher on approve
- [x] Admin — Payment Audit Log: `/admin/payments` — paginated full history with status filter tabs
- [x] Admin — User Listing: `/admin/users` — paginated with role filter tabs

**Files created/modified:**
- `app/certificates/utils.py` — `generate_certificate_code`, `generate_certificate_pdf` (ReportLab), `upload_certificate_pdf` (Cloudinary/local)
- `app/certificates/routes.py` — `generate`, `download`, `verify` routes
- `app/templates/certificates/verify.html` — public verification page
- `app/templates/courses/course_detail.html` — added Download Certificate button for completed enrollments
- `app/notifications/__init__.py`, `utils.py`, `routes.py` — full in-app notification module
- `app/templates/notifications/index.html` — notification inbox with pagination and mark-all-read
- `app/templates/base.html` — notification bell with unread badge
- `app/learner/routes.py` — dashboard with certificates/notifications/favorites; toggle_favorite route
- `app/templates/learner/dashboard.html` — full rebuild: courses, sessions, certificates, notifications, favorites
- `app/templates/teacher/public_profile.html` — favorite toggle button
- `app/teacher/routes.py` — dashboard passes total_earnings, recent_payments, recent_reviews
- `app/templates/teacher/dashboard.html` — earnings panel + reviews panel added
- `app/admin/routes.py` — full admin routes: dashboard, teacher_list, verify_teacher, unverify_teacher, course_list, approve_course, unapprove_course, payment_list, user_list
- `app/templates/admin/dashboard.html` — full rebuild with stats, revenue, queue cards, recent tx
- `app/templates/admin/teachers.html` — teacher verification queue with verify/revoke actions
- `app/templates/admin/courses.html` — course approval queue with approve/revoke actions
- `app/templates/admin/payments.html` — paginated payment audit log
- `app/templates/admin/users.html` — paginated user listing with role filter
- `app/static/css/style.css` — Phase 8 additions: certificate-card hover, admin-queue-card hover, notif-unread style

**Blockers / deviations from master prompt:**
- **Course catalog visibility**: Catalog still shows `is_published=True` courses without gating on `is_approved`. Admin approval adds a verified badge but does not block learner access (keeping demo usable before any admin approvals are granted).
- **Khalti gateway**: Deliberately deferred from Phase 7 (eSewa-only per scope). Not changed in Phase 8.

**Notes for report/viva:**
- `generate_certificate_pdf` uses ReportLab Canvas on a landscape A4 page (841×595 pt) with double decorative border (indigo + gold), centered learner name with dynamic underline bar, instructor/date signature blocks, decorative seal circle, and a bottom verification code bar.
- `upload_certificate_pdf` mirrors `upload_lesson_pdf` using `resource_type="raw"` for Cloudinary binary upload; falls back to local disk in dev environments without crashing.
- Admin verification/approval actions both trigger `notify()` to send in-app notifications to the affected teacher, closing the feedback loop without requiring email delivery.
- All admin POST actions (verify, approve, revoke) are CSRF-protected via Flask-WTF's `{{ csrf_token() }}` hidden inputs.

---

## Phase 9 — Security & UI Polish
**Status:** ✅ Done
**Date started / completed:** 2026-09-18 / 2026-09-18

**Checklist**
- [x] CSRF tokens verified on every form (GET search forms, Socket.IO chat, and eSewa external-POST form deliberately excluded — all correct)
- [x] Role-check decorators on every protected route (`@learner_required`, `@teacher_required`, `@admin_required` audited across all 7 blueprint route files)
- [x] File upload validation (type + size) enforced (`upload_course_thumbnail`, `upload_lesson_video`, `upload_lesson_pdf`, `upload_certificate_pdf`, `upload_profile_picture` all validate extension + byte size)
- [x] IDOR checks — ownership verified before edit/delete (every mutating route compares `current_user.id` against resource owner, `abort(403)` on mismatch)
- [x] Login rate limiting (5 attempts, 15-min lockout via `User.increment_failed_login` / `is_locked` — implemented in Phase 2, verified unchanged)
- [x] Navbar: unread badge + notification bell (implemented in Phase 8, verified in base.html)
- [x] Confirmation modals on all destructive actions: cancel/reject booking, complete session, unenroll from course, delete lesson, unpublish course/lesson, admin verify/unverify, admin approve/unapprove
- [x] Responsive check at 375px — navbar collapse, hero headers, stat grids, booking detail, checkout all tested and fixed with mobile-specific overrides
- [x] 404 / 500 error pages (implemented in Phase 1, styled with design system)
- [x] Flash message styling (success/error/info/warning — all four variants in base.html toast block)
- [x] Empty-state messages on all list views (no courses, no bookings, no reviews, no notifications, no favorites)
- [x] `.env.example` finalized (all keys present, no real secrets)
- [x] `requirements.txt` versions pinned
- [x] `README.md` written

**Files created/modified:**
- `README.md` — new: project overview, tech stack, folder structure, local setup, env vars, external services, deployment guide
- `app/courses/routes.py` — added `POST /courses/<course_id>/unenroll` route (deletes Enrollment + associated Certificate)
- `app/templates/courses/course_detail.html` — unenroll button + confirm; publish toggle confirm
- `app/templates/courses/manage_lessons.html` — delete lesson confirm; unpublish confirm
- `app/templates/booking/detail.html` — complete session confirm; responsive grid layout
- `app/templates/admin/teachers.html` — verify/unverify confirms
- `app/templates/admin/courses.html` — approve/unapprove confirms
- `app/static/css/style.css` — `.dashboard-two-col`, `.dashboard-even-col`, `.dashboard-three-col` responsive grid classes; 375 px mobile overrides
- `app/templates/learner/dashboard.html`, `teacher/dashboard.html`, `admin/dashboard.html`, `payments/checkout.html` — migrated to new responsive grid classes

**Blockers / deviations from master prompt:**
- Unenroll feature was not in the original Phase 9 checklist but was added here as it is a natural complement to the cancel booking / destructive-action audit.

**Notes for report/viva:**
- IDOR protection uses a consistent pattern across all blueprints: fetch resource by primary key (`get_or_404`), then assert `current_user.id == resource.owner_id`, else `abort(403)`. No route relies solely on a role decorator for ownership.
- File upload validation uses `seek(0, SEEK_END)` / `tell()` / `seek(0)` to measure byte size without reading the whole file into memory before validation — safe for large video uploads.
- Confirmation dialogs use native `window.confirm()` (zero JS dependencies, always synchronous) rather than custom modal libraries, keeping the codebase lightweight.
- `README.md` documents graceful-fallback behaviour for all optional services (Cloudinary → local disk, eSewa → mock, Google OAuth → skipped) so the app runs fully offline in dev.

---

## Post-Phase-9 — Trust & Safety: Reporting, Banning, Refunds
**Status:** ✅ Done
**Date started / completed:** 2026-09-20 / 2026-09-20

**Checklist**
- [x] Admin ban/unban mechanism reusing `User.is_active` (no extra columns needed)
- [x] Session deactivation check in `@app.before_request` hook so banned users are immediately logged out
- [x] Admin ban protection for admin accounts (cannot ban fellow admins)
- [x] `Report` model created for session complaints (late, no_show, misbehavior, other) with status workflow
- [x] Incident reporting blueprint `app/reports/` with CSRF-protected `ReportForm`
- [x] Soft prevention of duplicate pending reports for the same booking
- [x] In-app notification alert dispatched to all admins upon new report filing
- [x] Participant-tailored inline report form in `booking/detail.html` ("Report Teacher" / "Report Student")
- [x] Admin incident moderation queue `/admin/reports` with status filtering tabs
- [x] Admin dismiss and resolve actions with optional audit notes
- [x] Internal booking refund action flipping `Payment.status = 'refunded'` and excluding from teacher earnings
- [x] Direct moderation ban shortcut from report cards
- [x] Admin dashboard integration: pending reports counter on stat cards and quick management tools

**Files created/modified:**
- `app/models.py` — added `Report` model and table definition
- `app/__init__.py` — registered `reports_bp` and added `@app.before_request` session deactivation check
- `app/reports/__init__.py` — initialized reports blueprint
- `app/reports/forms.py` — `ReportForm` with reasons and description
- `app/reports/routes.py` — `POST /reports/booking/<id>` participant reporting route
- `app/admin/routes.py` — ban, unban, report listing, dismiss, resolve, and refund handlers
- `app/booking/routes.py` — passed report form and pending status to booking detail view
- `app/templates/booking/detail.html` — added inline reporting box and pending report banner
- `app/templates/admin/users.html` — added active/banned status badges and ban/unban action buttons
- `app/templates/admin/reports.html` — admin queue with status filtering, cards, and moderation buttons
- `app/templates/admin/dashboard.html` — added pending reports stat counter and queue alert
- `app/static/css/style.css` — added `.report-card`, `.report-reason-badge`, `.ban-badge` styles
- `PROGRESS.md` — documented trust & safety implementation and scope decisions

**Scope Decisions & Architectural Notes:**
- **Reversible Suspension vs Deletion**: User removal was deliberately implemented as account suspension (`is_active = False`) rather than permanent deletion. This maintains relational integrity (past bookings, payments, courses, reviews) while immediately blocking login and revoking public search listing.
- **Internal Accounting Refunds**: Refund action updates internal platform accounting (`Payment.status = 'refunded'`) to reverse teacher earnings and notify learners. It does not issue live merchant API payout calls to external gateway providers (eSewa/Khalti sandbox), avoiding unauthorized financial mutations outside the platform's scope.

---

## Phase 10 — Deployment (Render + Aiven + Cloudinary)
**Status:** ⬜
**Date started / completed:** —

**Checklist**
- [ ] Aiven free MySQL provisioned, connection string in Render env vars
- [ ] Cloudinary account connected, API keys in env vars
- [ ] Render web service deployed, builds successfully
- [ ] SocketIO polling transport confirmed working on live URL
- [ ] Google OAuth redirect URI updated to Render URL
- [ ] eSewa/Khalti sandbox callback URLs updated to Render URL
- [ ] Gmail SMTP tested from live deployment
- [ ] Jitsi calls tested from live deployment
- [ ] Cold-start behavior tested and understood (~30–60s after idle)
- [ ] Full end-to-end demo run-through completed on live URL

**Live URL:**
-

**Blockers / deviations from master prompt:**
-

**Notes for report/viva:**
-

---

## Environment / Credentials Checklist
*(Do not put real secrets in this file — just tick off that each one is set up somewhere safe, e.g. `.env` locally and Render's environment variables for deployment.)*

- [ ] Local MySQL running (XAMPP/Workbench)
- [ ] Aiven MySQL account created
- [ ] Google Cloud Console OAuth client created (test-user mode)
- [ ] Gmail account + App Password generated
- [ ] eSewa sandbox test credentials obtained
- [ ] Khalti sandbox test credentials obtained
- [ ] Cloudinary account created, API key/secret noted
- [ ] Render account created, GitHub repo connected

---

## Overall Notes / Lessons Learned
*(Free-form — useful for your project report's "challenges faced" section.)*

-

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
| 5 | Booking System | ⬜ Not started | |
| 6 | Live Class & Chat | ⬜ Not started | |
| 7 | Ratings & Payments | ⬜ Not started | |
| 8 | Certificates & Dashboards | ⬜ Not started | |
| 9 | Security & UI Polish | ⬜ Not started | |
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
**Status:** ⬜
**Date started / completed:** —

**Checklist**
- [ ] Jitsi iFrame embedded, room name unique per booking
- [ ] Join restricted to approved booking's learner + teacher
- [ ] Whiteboard confirmed visible in call toolbar (default on meet.jit.si — no build needed)
- [ ] SocketIO chat — messages persist to DB
- [ ] SocketIO configured for **polling transport** (Render free-tier compatibility)
- [ ] Unread message badge in navbar
- [ ] Inbox + conversation view templates

**Files created/modified:**
-

**Blockers / deviations from master prompt:**
-

**Notes for report/viva:**
-

---

## Phase 7 — Ratings & Payments
**Status:** ⬜
**Date started / completed:** —

**Checklist**
- [ ] Review submission restricted to completed booking/course
- [ ] Average rating recalculated on teacher_profiles
- [ ] eSewa sandbox flow (initiate → success/failure)
- [ ] Khalti sandbox flow (initiate → verify)
- [ ] Payment record stored; enrollment/booking confirmed on success
- [ ] Checkout / success / failure templates

**Files created/modified:**
-

**Blockers / deviations from master prompt:**
-

**Notes for report/viva:**
-

---

## Phase 8 — Certificates & Dashboards
**Status:** ⬜
**Date started / completed:** —

**Checklist**
- [ ] PDF certificate generation (ReportLab) with all required fields
- [ ] Certificate stored (Cloudinary) + record in `certificates` table
- [ ] Download route works
- [ ] Learner dashboard (courses, sessions, certificates, notifications, favorites)
- [ ] Teacher dashboard (courses, bookings, earnings, reviews)
- [ ] Admin dashboard (users, courses, payments, teacher verification queue)

**Files created/modified:**
-

**Blockers / deviations from master prompt:**
-

**Notes for report/viva:**
-

---

## Phase 9 — Security & UI Polish
**Status:** ⬜
**Date started / completed:** —

**Checklist**
- [ ] CSRF tokens verified on every form
- [ ] Role-check decorators on every protected route
- [ ] File upload validation (type + size) enforced
- [ ] IDOR checks — ownership verified before edit/delete
- [ ] Login rate limiting (5 attempts)
- [ ] Navbar: unread badge + notification bell
- [ ] Confirmation modals (cancel booking, unenroll)
- [ ] Responsive check at 375px
- [ ] 404 / 500 error pages
- [ ] Flash message styling (success/error/info)
- [ ] Empty-state messages (no courses, no bookings, no reviews)
- [ ] `.env.example` finalized
- [ ] `requirements.txt` versions pinned
- [ ] `README.md` written

**Files created/modified:**
-

**Blockers / deviations from master prompt:**
-

**Notes for report/viva:**
-

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

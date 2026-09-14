# SkillBridge — Progress Log

> Keep this file at the project root. Update it at the end of every phase — this is your running record for the project report and viva. Reference `SkillBridge_Master_Prompt_Final.md` for full scope of each phase.

---

## Quick Status Overview

| Phase | Focus | Status | Date Completed |
|---|---|---|---|
| 1 | Setup & Models | ✅ Done | 2026-09-14 |
| 2 | Authentication | ⬜ Not started | |
| 3 | Teacher Profile & Search | ⬜ Not started | |
| 4 | Course Management | ⬜ Not started | |
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
- MySQL not yet installed on dev machine — installing via Homebrew during Phase 1 setup

**Notes for report/viva:**
- App factory pattern used: extensions created globally, initialized inside `create_app()` to avoid circular imports
- All 13 models defined with SQLAlchemy ORM; no raw SQL used anywhere
- Cloudinary URL columns on all media fields from day 1 (not added later) per §2b of master prompt
- SocketIO configured with `async_mode="threading"` — compatible with Render free tier polling transport (no eventlet/gevent needed)
- `allow_unsafe_werkzeug=True` required by Flask-SocketIO ≥ 5.x for the Werkzeug dev server

---

## Phase 2 — Authentication
**Status:** ⬜
**Date started / completed:** —

**Checklist**
- [ ] Register (Learner / Teacher separate flows)
- [ ] Login / Logout
- [ ] Google OAuth login working
- [ ] Forgot password → email sent via Flask-Mail
- [ ] Reset password via token
- [ ] `templates/base.html` (navbar, flash messages)
- [ ] Role-based redirect after login
- [ ] Role-based route protection in place

**Files created/modified:**
-

**Blockers / deviations from master prompt:**
-

**Notes for report/viva:**
-

---

## Phase 3 — Teacher Profile & Search
**Status:** ⬜
**Date started / completed:** —

**Checklist**
- [ ] Teacher profile edit page (photo, bio, skills, qualifications, price, availability)
- [ ] File uploads routed through **Cloudinary** (not local disk)
- [ ] Public teacher profile page
- [ ] Learner search with filters (skill, rating, price, availability)
- [ ] Results sorted by rating
- [ ] Teacher cards (photo, skills, rating, price, verified badge)

**Files created/modified:**
-

**Blockers / deviations from master prompt:**
-

**Notes for report/viva:**
-

---

## Phase 4 — Course Management
**Status:** ⬜
**Date started / completed:** —

**Checklist**
- [ ] Teacher: create/edit course, add lessons, add quiz
- [ ] Course files (video/PDF) via Cloudinary
- [ ] Learner: browse, enroll, view course detail
- [ ] Lesson viewer with progress tracking
- [ ] Quiz submission
- [ ] Progress % updates correctly
- [ ] Course-complete trigger wired (certificate placeholder for Phase 8)

**Files created/modified:**
-

**Blockers / deviations from master prompt:**
-

**Notes for report/viva:**
-

---

## Phase 5 — Booking System
**Status:** ⬜
**Date started / completed:** —

**Checklist**
- [ ] Learner: view teacher's slots, submit booking
- [ ] Teacher: approve/reject booking
- [ ] Booking history (both roles)
- [ ] Email notification — new booking → teacher
- [ ] Email notification — approve/reject → learner

**Files created/modified:**
-

**Blockers / deviations from master prompt:**
-

**Notes for report/viva:**
-

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

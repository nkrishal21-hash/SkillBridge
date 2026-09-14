# SkillBridge — Master Project Prompt (Final, Free-Stack Edition)
*BCA 4th Semester Project — Full-Stack Skill Learning & Mentorship Platform*

---

## 0. How I Want You (the AI Agent) to Work

- I am building this project in **Antigravity IDE** with agent mode, phase by phase.
- Treat this document as **permanent project context** — refer back to it in every phase.
- I will give you **one phase at a time** (see Phase Plan at the end). Do **not** jump ahead to a later phase unless I explicitly ask.
- Before writing code for a phase, briefly confirm your understanding of that phase's scope in 2-3 lines, then deliver full working code — not pseudocode, not partial snippets.
- Always use **Flask Blueprints**, one per module, matching the folder structure below.
- Give **complete files** — models, routes, templates, and JS — whenever a feature touches multiple layers.
- Write **clean, commented, production-style code** appropriate for an academic capstone (examiners will read it).
- **Do not silently swap technologies.** Everything below must stay 100% free/open-source or free-tier — this is a student project with zero budget. If something in my stack genuinely can't be done for free, stop and tell me instead of substituting a paid service.
- After each phase, remind me to `git commit` before moving on.
- Track progress in a separate `PROGRESS.md` file at the project root (template provided alongside this prompt). At the end of each phase: tick off completed items, fill in the "Files created/modified" list, note the date, and log any blockers or deviations from this prompt. Don't skip this — it's the running record I'll use to write my project report.

---

## 1. What I Am Building

**SkillBridge** — a full-stack web platform connecting **learners** with **teachers/mentors**: search teachers, enroll in courses, book 1-on-1 sessions, attend live classes, chat in real time, pay for sessions/courses, and earn certificates.

---

## 2. Tech Stack — All Free/Open-Source (Do Not Change)

| Layer | Technology | Free Implementation Notes |
|---|---|---|
| Frontend | HTML, CSS, Bootstrap 5 | CDN — no cost |
| Backend | Python Flask | Open source |
| Database | MySQL + Flask-SQLAlchemy | **Local MySQL via XAMPP/MySQL Workbench for dev.** For a hosted demo, use a free tier such as **Railway**, **Clever Cloud**, or **PlanetScale free tier** (state clearly in README that credentials are for demo only) |
| Auth | Flask-Login + Google OAuth | Google Cloud Console **OAuth client (free)** — set up under "External" test users, no billing needed for dev/test scope |
| Real-Time Chat | Flask-SocketIO | Open source, runs on same free host |
| Video/Live Classes | Jitsi Meet API | Use the **free public server `meet.jit.si`** embedded via iFrame API — no self-hosting or paid Jitsi instance needed |
| Payments | eSewa Sandbox + Khalti Sandbox | Both are **official free test/sandbox environments** for Nepali payment gateways — no real transactions, no merchant account cost. Use their published test credentials |
| Email | Flask-Mail (Gmail SMTP) | Free Gmail account + **App Password** (not real password) — free up to Gmail's normal sending limits |
| PDF Certificates | ReportLab | Open source Python library |
| Version Control | GitHub | Free public/private repos |
| App Hosting (demo) | **Render free web service** | Free forever, no card required for the free tier. Two known limits to design around (see §2b) |
| Database Hosting (demo) | **Aiven free MySQL** | Always-free tier: 1GB storage/RAM, no credit card, no expiry — more reliable than Railway/Clever Cloud, which have dropped real free tiers |
| File/Image Storage (demo) | **Cloudinary free tier** | 25GB free, no card required — needed because Render's free disk is wiped on every redeploy/restart |

> **Note on scope:** Since this is a Nepal-context project (eSewa/Khalti), all payment flows must stay in sandbox/test mode for the entire project lifecycle — never switch to production merchant credentials.

---

## 2b. Deployment Plan (Completely Free) — Read Before Phase 9

This is the finalized, no-cost deployment stack for demoing SkillBridge live (e.g. during viva). Two limitations of free hosting are handled deliberately rather than discovered late:

1. **No reliable WebSockets on Render's free tier.**
   Free services sleep after 15 minutes idle, which drops live socket connections. Fix: configure Flask-SocketIO to use **long-polling only** (`async_mode` + client `transports: ["polling"]`), not raw websockets. Chat still updates in near-real-time; it just uses repeated HTTP requests instead of a persistent socket. This must be built in from Phase 6, not patched in later.

2. **Render's free disk is ephemeral** — uploaded profile photos, course PDFs/videos, and generated certificates would vanish on every redeploy or restart.
   Fix: route all file uploads (profile photos, course materials, certificate PDFs) through **Cloudinary's free tier** instead of local `static/uploads/`. Store only the returned Cloudinary URL in the database. This must be the default upload method from Phase 3 onward — not a local-disk fallback we swap later.

**Final deployment stack:**
- **Backend**: Render free web service (Flask + Flask-SocketIO, polling transport)
- **Database**: Aiven free MySQL (connection string via environment variable)
- **File storage**: Cloudinary free tier (photos, PDFs, certificates)
- **Email**: Gmail SMTP + App Password (works from any host)
- **Google OAuth**: add the Render URL as an authorized redirect URI in Google Cloud Console (free, test-user mode)
- **Payments**: eSewa/Khalti sandbox callback URLs point to the Render public URL
- **Video**: `meet.jit.si` — no hosting needed at all

**Known trade-off to expect during a live demo:** if the service has been idle, the first request after opening the site takes 30–60 seconds (cold start) before it responds normally. Worth opening the site a few minutes before a viva/demo to "wake it up."

---

## 3. Three User Roles

### Learner
- Register/login, search teachers by skill/rating/price/availability
- Enroll in courses, track progress, complete quizzes
- Book 1-on-1 mentorship sessions, attend live classes
- Chat with teachers, rate and review, download certificates
- Dashboard: enrolled courses, booked sessions, certificates, favorites

### Teacher
- Register/login, build full profile (photo, skills, qualifications, price, availability)
- Upload courses with video lessons, PDF notes, quizzes
- Manage booking requests, conduct live classes via Jitsi
- Chat with learners, view earnings, ratings, and reviews
- Dashboard: courses, enrollments, earnings, reviews

### Admin
- Verify teachers, approve course content
- Manage all users, monitor platform activity
- Dashboard: total users, courses, payments, reports

---

## 4. Database Tables Required

```
users
teacher_profiles
courses
lessons
enrollments
bookings
messages
reviews
ratings
payments
notifications
certificates
favorites
```

---

## 5. Core Features (Priority Order)

1. **Authentication** — Learner/Teacher registration, login/logout, Google OAuth, forgot password via email, Flask-Bcrypt hashing, role-based access control
2. **Teacher Search & Discovery** — filter by skill, rating, price, availability; sorted by rating; card layout with verification badge
3. **Teacher Profile System** — public profile, bio, skills, qualifications, certifications, experience, price, availability, verified badge
4. **Course Management** — teachers create courses/lessons/quizzes; learners enroll, track % progress, take quizzes, get certificate on completion
5. **Booking / Mentorship Sessions** — learner picks time slot, teacher approves/rejects, email notifications, booking history
6. **Live Class System** — Jitsi Meet iFrame embed, unique room per booking, tied to approved bookings only. On `meet.jit.si` the collaborative whiteboard (Excalidraw-based) is available by default in the call toolbar — no extra integration needed, just surface it in the UI
7. **Real-Time Chat** — Flask-SocketIO, message persistence, unread badge
8. **Rating & Review System** — 1–5 stars + written review after session/course, dynamic average rating
9. **Payment System** — eSewa + Khalti sandbox, for course enrollment and session bookings, payment verification/receipt
10. **Certificate Generation** — ReportLab PDF with learner name, course, instructor, completion date, downloadable
11. **Dashboards** — Learner, Teacher, Admin — each with role-relevant data

---

## 6. Security Requirements
- Flask-WTF CSRF protection on all forms
- Parameterized queries via SQLAlchemy ORM only (no raw SQL)
- Werkzeug/Bcrypt password hashing
- File upload validation (type + size limits): images jpg/png/gif ≤16MB, video mp4 ≤500MB, PDFs for notes
- Input sanitization and validation on all forms
- Role-based route protection (`@learner_required`, `@teacher_required`, `@admin_required`)
- IDOR prevention — verify ownership before edit/delete on every route
- Basic login rate limiting (max 5 attempts before lockout)

---

## 7. UI / Frontend Requirements
- Responsive, mobile-friendly (test down to 375px width), Bootstrap 5
- Pages: Home/Landing, Register, Login, Teacher Search, Teacher Profile, Course Detail, Learner Dashboard, Teacher Dashboard, Admin Dashboard, Booking Page, Chat Page, Payment Page
- Card-based teacher listings, search filter sidebar
- Clean, professional design — not default Bootstrap look
- Notification bell + unread message badge in navbar
- Styled flash messages (success/error/info), confirmation modals for cancel/unenroll actions, custom 404/500 pages

---

## 8. Project File Structure

```
skillbridge/
├── app/
│   ├── __init__.py          # App factory
│   ├── models.py            # All DB models
│   ├── auth/                # Register, login, OAuth
│   ├── learner/              # Learner routes & views
│   ├── teacher/              # Teacher routes & views
│   ├── admin/                # Admin routes & views
│   ├── courses/               # Course management
│   ├── booking/               # Booking system
│   ├── chat/                  # SocketIO chat
│   ├── payments/              # eSewa & Khalti
│   ├── certificates/          # ReportLab PDF
│   ├── static/                 # CSS, JS, images
│   └── templates/              # Jinja2 HTML templates
├── config.py                  # Config (DB URI, secrets, mail)
├── .env.example                # All required env vars, no real secrets
├── requirements.txt
└── run.py
```

---

## 9. Phase Plan (Build One at a Time)

| Phase | Focus | Key Deliverable |
|---|---|---|
| 1 | Setup & Models | Project runs, all DB tables created |
| 2 | Authentication | Register, login, Google OAuth, password reset |
| 3 | Teacher Profile & Search | Public profiles, search with filters |
| 4 | Course Management | Upload courses, enroll, track progress |
| 5 | Booking System | Book sessions, approve/reject, email alerts |
| 6 | Live Class & Chat | Jitsi video (meet.jit.si, built-in whiteboard), real-time SocketIO chat |
| 7 | Ratings & Payments | Reviews, eSewa + Khalti sandbox |
| 8 | Certificates & Dashboards | PDF certs, 3 role dashboards |
| 9 | Security & UI Polish | Hardening, responsive UI, README |

**Phase 1 kickoff task (when I say "start Phase 1"):**
1. Full folder/file structure as above
2. `requirements.txt` with pinned versions: Flask, Flask-Login, Flask-SQLAlchemy, Flask-Bcrypt, Flask-Mail, Flask-SocketIO, Flask-WTF, PyMySQL, ReportLab, Authlib, cloudinary
3. `config.py` — dev config class, MySQL URI from environment variables (local MySQL for dev, Aiven MySQL URI for the deployed demo), secret key, mail config, Cloudinary config (for file uploads instead of local disk), SocketIO `async_mode` set for polling-compatible deployment
4. `run.py` entry point
5. `app/__init__.py` — app factory with Blueprint registration
6. `app/models.py` — all 13 tables with columns, relationships, foreign keys
7. `db_init.py` to create all tables
8. `.env.example` listing every required variable (DB URI, Google OAuth keys, Gmail app password, eSewa/Khalti sandbox keys, Cloudinary API key/secret, secret key) — **no real secrets committed**

**Done when:** `python run.py` starts without errors, `python db_init.py` creates all tables, structure matches exactly.

---

## 10. Progress Tracking

Detailed phase-by-phase status, dates, files touched, and blockers live in **`PROGRESS.md`** (separate file, kept at the project root, updated at the end of every phase). This document (the master prompt) stays static as project context; `PROGRESS.md` is the living log.

---

*This is a BCA 4th semester academic project. All payment integrations remain in sandbox/test mode only — no real money changes hands at any point.*

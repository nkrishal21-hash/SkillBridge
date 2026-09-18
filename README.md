# SkillBridge

A full-stack e-learning platform connecting learners with verified teachers. Learners browse courses and book 1-on-1 sessions; teachers manage content, live classes, and earnings; admins oversee verification and approvals — all in one Flask application.

---

## Table of Contents

1. [Features](#features)  
2. [Tech Stack](#tech-stack)  
3. [Project Structure](#project-structure)  
4. [Local Setup](#local-setup)  
5. [Environment Variables](#environment-variables)  
6. [Running the App](#running-the-app)  
7. [Database Initialisation](#database-initialisation)  
8. [Default Admin Account](#default-admin-account)  
9. [External Services](#external-services)  
10. [Deployment (Render)](#deployment-render)

---

## Features

| Area | Details |
|---|---|
| **Authentication** | Email/password + Google OAuth, role-based redirect (learner / teacher / admin), forgot-password email flow, 5-attempt lockout |
| **Teacher Profiles** | Bio, hourly rate, subject tags, profile photo, verified badge (admin-controlled) |
| **Course Management** | Create/edit courses with thumbnail, publish/unpublish, per-lesson videos & PDFs, lesson ordering, quizzes |
| **Enrollment** | Learners enroll (free or paid), track progress lesson-by-lesson, receive certificate on completion |
| **1-on-1 Bookings** | Request/approve/reject/cancel sessions; Jitsi Meet live-class link auto-generated on approval |
| **Real-Time Chat** | Socket.IO room chat per booking; message history persisted in DB |
| **Payments** | eSewa sandbox integration (course enrollment + booking deposit); receipt & payment audit log |
| **Certificates** | ReportLab PDF with decorative border, learner name, completion date, QR-ready verification code; Cloudinary upload with local fallback |
| **Notifications** | In-app bell with unread badge; events: booking approve/reject/new, payment success, review received, teacher verified, course approved |
| **Favorites** | Learners can favorite teacher profiles |
| **Reviews & Ratings** | Star rating + comment on completed enrollments |
| **Admin Panel** | Dashboard with stats + revenue chart; teacher verification queue; course approval queue; payment audit log; user list |
| **Security** | CSRF on every POST form, IDOR ownership checks, role decorators on all protected routes, file-type + size validation on every upload |
| **UI** | Custom dark-mode design system, responsive down to 375 px, flash messages, empty-state cards, custom 404/500 pages |

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11+, Flask 3.0 |
| **ORM** | Flask-SQLAlchemy 3.1 / SQLAlchemy 2.0 |
| **Database** | MySQL (local via XAMPP; Aiven for production) |
| **Authentication** | Flask-Login 0.6, Flask-Bcrypt 1.0, Authlib 1.3 (Google OAuth) |
| **Forms / CSRF** | Flask-WTF 1.2, WTForms 3.1 |
| **Real-Time** | Flask-SocketIO 5.3 (`async_mode=threading`), simple-websocket |
| **Email** | Flask-Mail 0.10, Gmail SMTP |
| **File Storage** | Cloudinary 1.40 (primary), local `static/uploads/` (fallback) |
| **PDF Generation** | ReportLab 4.2 |
| **Payments** | eSewa sandbox (redirect-based) |
| **Live Classes** | Jitsi Meet (iframe embed, no server needed) |
| **Frontend** | Jinja2 templates, Vanilla CSS (custom design system), vanilla JS |
| **WSGI (prod)** | Gunicorn 22 |

---

## Project Structure

```
SkillBridge/
├── run.py                  # Entry point — starts Flask dev server on port 5001
├── config.py               # Dev / Prod config classes (reads from .env)
├── db_init.py              # One-time DB table creation script
├── requirements.txt        # Pinned Python dependencies
├── .env.example            # Template — copy to .env and fill in secrets
├── PROGRESS.md             # Phase-by-phase build log
│
└── app/
    ├── __init__.py         # App factory, extension init, blueprint registration
    ├── models.py           # All 13 SQLAlchemy models
    │
    ├── auth/               # Register, login, logout, Google OAuth, password reset
    ├── learner/            # Learner dashboard, favorites
    ├── teacher/            # Teacher dashboard, profile edit, public profile, search
    ├── admin/              # Admin dashboard, verification queues, payment log
    ├── courses/            # Course CRUD, lesson CRUD, enrollment, progress, quiz
    ├── booking/            # Booking request → approve/reject → live class → complete
    ├── chat/               # Socket.IO real-time chat per booking room
    ├── payments/           # eSewa checkout + callback + receipt
    ├── certificates/       # PDF generation, Cloudinary upload, download, public verify
    ├── notifications/      # notify() helper, inbox, mark-read routes
    ├── reviews/            # Submit review, display on course detail
    │
    ├── static/
    │   ├── css/style.css   # Custom design system (CSS variables, responsive grid)
    │   ├── js/             # Socket.IO client, quiz UI, misc helpers
    │   └── uploads/        # Local fallback upload dirs (auto-created at runtime)
    │
    └── templates/
        ├── base.html       # Master layout: navbar, flash messages, notification bell
        ├── auth/
        ├── learner/
        ├── teacher/
        ├── admin/
        ├── courses/
        ├── booking/
        ├── payments/
        ├── certificates/
        ├── notifications/
        ├── reviews/
        └── errors/         # 404.html, 500.html
```

---

## Local Setup

### Prerequisites

- Python 3.11+
- MySQL server running locally (e.g. XAMPP, Homebrew `mysql`, or MySQL Workbench)
- A MySQL database named `skillbridge` (or whatever you set in `.env`)
- Git

### 1 — Clone the repo

```bash
git clone https://github.com/your-username/SkillBridge.git
cd SkillBridge
```

### 2 — Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows
```

### 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### 4 — Configure environment variables

```bash
cp .env.example .env
# Open .env in your editor and fill in every value (see table below)
```

### 5 — Create the database tables

```bash
python db_init.py
```

This runs `db.create_all()` inside the app context and creates all 13 tables.

### 6 — Run the development server

```bash
python run.py
```

The app starts on **http://127.0.0.1:5001**  
(Port 5001 avoids conflict with macOS AirPlay Receiver on port 5000.)

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the values below.  
**Never commit `.env` to version control.**

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | ✅ | Flask session secret — use a long random string |
| `DATABASE_URL` | ✅ | MySQL URI, e.g. `mysql+pymysql://root:@localhost/skillbridge` |
| `MAIL_USERNAME` | ✅ | Gmail address for sending password-reset emails |
| `MAIL_PASSWORD` | ✅ | Gmail App Password (not your Google account password) |
| `GOOGLE_CLIENT_ID` | Optional | Google OAuth client ID (OAuth login is skipped gracefully if absent) |
| `GOOGLE_CLIENT_SECRET` | Optional | Google OAuth client secret |
| `CLOUDINARY_CLOUD_NAME` | Optional | Cloudinary account cloud name (uploads fall back to local disk if absent) |
| `CLOUDINARY_API_KEY` | Optional | Cloudinary API key |
| `CLOUDINARY_API_SECRET` | Optional | Cloudinary API secret |
| `ESEWA_MERCHANT_ID` | Optional | eSewa sandbox merchant code (payments skipped if absent) |

> **Local dev tip:** You can leave Cloudinary and eSewa variables empty. All file uploads will save to `app/static/uploads/` and payment flows will use a mock success path.

---

## Running the App

```bash
# Development (auto-reload, debug mode)
python run.py

# Production (Gunicorn)
gunicorn -w 1 -k gevent --bind 0.0.0.0:8000 "app:create_app()"
```

> ⚠️ Use `-w 1` with Socket.IO — multiple workers break WebSocket state sharing unless you add a Redis message queue.

---

## Database Initialisation

```bash
python db_init.py
```

Run this once after cloning (or after dropping/recreating the database). It also creates a default admin account printed to the console:

```
Admin account created — email: admin@skillbridge.com  password: Admin@123
```

Change the admin password immediately after first login.

---

## Default Admin Account

| Field | Value |
|---|---|
| Email | `admin@skillbridge.com` |
| Password | `Admin@123` |
| Role | admin |

---

## External Services

### Google OAuth
1. Go to [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials
2. Create an OAuth 2.0 Client ID (Web application)
3. Add `http://127.0.0.1:5001/auth/google/callback` as an authorised redirect URI
4. Copy Client ID and Secret into `.env`

### Gmail SMTP
1. Enable 2-Step Verification on your Google account
2. Generate an App Password (Google Account → Security → App Passwords)
3. Use the 16-character app password as `MAIL_PASSWORD` in `.env`

### Cloudinary
1. Create a free account at [cloudinary.com](https://cloudinary.com)
2. Copy Cloud Name, API Key, and API Secret from the dashboard into `.env`

### eSewa Sandbox
1. Obtain sandbox credentials from [eSewa developer docs](https://developer.esewa.com.np/)
2. Set `ESEWA_MERCHANT_ID` in `.env`
3. The callback URLs are already configured for `localhost:5001` in `config.py`

---

## Deployment (Render)

See **Phase 10** in [`PROGRESS.md`](PROGRESS.md) for the full deployment checklist.

High-level steps:
1. Provision a free MySQL instance on [Aiven](https://aiven.io)
2. Push repo to GitHub
3. Create a **Web Service** on Render pointing to the GitHub repo
4. Set all environment variables in Render's dashboard (same as `.env`)
5. Set `DATABASE_URL` to the Aiven connection string
6. Update Google OAuth redirect URI to the Render URL
7. Start command: `gunicorn -w 1 -k gevent --bind 0.0.0.0:$PORT "app:create_app()"`

---

## License

This project was built for academic purposes as part of a college capstone.

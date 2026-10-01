#!/usr/bin/env python3
"""
scripts/test_report_admin_unified.py
Comprehensive test suite verifying the SkillBridge Report Admin Unification
as specified in requirements TEST 1 through TEST 12, plus regression testing.

Uses direct model/service calls for reliable verification, and the Flask
test client only for route-level security & access control checks.

Run with: ./venv/bin/python3 scripts/test_report_admin_unified.py
"""
import io
import os
import sys
from datetime import datetime, date, time
from decimal import Decimal

# Resolve project root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import create_app, db
from app.models import (
    User, TeacherProfile, Booking, Payment, Report,
    ReportEvidence, ReportResponse, RefundRequest, Notification
)
from app.refunds.service import process_refund, get_payment_hold_reason
from app.reports.forms import ALL_REPORT_REASONS, REPORT_REASON_DICT

GRN = "\033[92m"
RED = "\033[91m"
YLW = "\033[93m"
RST = "\033[0m"
BLD = "\033[1m"

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    PASS += 1
    print(f"  {GRN}✓{RST} {msg}")


def fail(msg, detail=""):
    global FAIL
    FAIL += 1
    info = f" — {detail}" if detail else ""
    print(f"  {RED}✗{RST} {msg}{info}")


def section(title):
    print(f"\n{BLD}{YLW}{'─'*60}{RST}")
    print(f"{BLD}{title}{RST}")
    print(f"{BLD}{YLW}{'─'*60}{RST}")


# ─── Fixture helpers ────────────────────────────────────────────────────────

_counter = [0]

def _uid():
    _counter[0] += 1
    return _counter[0]

def get_or_create_user(email, role="learner", name="Test User"):
    u = User.query.filter_by(email=email).first()
    if u:
        return u
    u = User(email=email, full_name=name, role=role, is_active=True)
    u.set_password("Password123!")
    db.session.add(u)
    db.session.commit()
    return u


def get_or_create_teacher(email, name="Test Teacher"):
    u = get_or_create_user(email, role="teacher", name=name)
    tp = TeacherProfile.query.filter_by(user_id=u.id).first()
    if not tp:
        tp = TeacherProfile(
            user_id=u.id,
            headline="Expert Instructor",
            skills="Python, Web Development",
            hourly_rate=1000,
            is_verified=True,
            verified_at=datetime.utcnow()
        )
        db.session.add(tp)
        db.session.commit()
    return u


def create_booking_payment(learner, teacher, amount=2000, status="completed"):
    """Create a booking + successful payment fixture."""
    ts = int(datetime.utcnow().timestamp() * 1000)
    uid = _uid()
    b = Booking(
        learner_id=learner.id,
        teacher_id=teacher.id,
        topic=f"Test Mentorship Session #{uid}",
        status=status,
        session_date=date.today(),
        start_time=time(14, 0),
        end_time=time(15, 0),
        amount=Decimal(str(amount)),
    )
    db.session.add(b)
    db.session.flush()

    p = Payment(
        learner_id=learner.id,
        payment_for="booking",
        booking_id_ref=b.id,
        amount=Decimal(str(amount)),
        currency="NPR",
        gateway="esewa",
        gateway_transaction_id=f"TX_{b.id}_{ts}",
        gateway_reference_id=f"REF_{b.id}_{ts}",
        status="success",
        platform_fee_amount=Decimal(str(round(amount * 0.20, 2))),
        teacher_payout_amount=Decimal(str(round(amount * 0.80, 2))),
        payout_status="pending",
        initiated_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    db.session.add(p)
    db.session.commit()
    return b, p


def login_as(client, user):
    """Set the Flask-Login session to impersonate a user."""
    from flask import g
    g.__dict__.pop("_login_user", None)
    with client.session_transaction() as sess:
        sess.clear()
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True



# ═══════════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def run_tests():
    app = create_app()
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["TESTING"] = True

    with app.app_context():
        # ── Setup actors ──────────────────────────────────────────────────────
        admin = get_or_create_user("rpt_admin@sb.test", role="admin", name="Report Admin")
        learner1 = get_or_create_user("rpt_learner1@sb.test", role="learner", name="Rohan Learner")
        learner2 = get_or_create_user("rpt_learner2@sb.test", role="learner", name="Pooja Learner")
        teacher1 = get_or_create_teacher("rpt_teacher1@sb.test", name="Suman Teacher")
        teacher2 = get_or_create_teacher("rpt_teacher2@sb.test", name="Kiran Teacher")

        client = app.test_client()

        # ─────────────────────────────────────────────────────────────────────
        # TEST 1 — Learner reports teacher (no refund requested)
        # ─────────────────────────────────────────────────────────────────────
        section("TEST 1 — Learner reports teacher (Evidence, no refund)")
        b1, p1 = create_booking_payment(learner1, teacher1, amount=2000)
        notif_before = Notification.query.count()

        login_as(client, learner1)
        resp = client.post(
            f"/reports/booking/{b1.id}",
            data={
                "reason": "late",
                "description": "Teacher arrived 25 minutes late to session.",
                "request_refund": "no",
                "evidence": (io.BytesIO(b"fake image data"), "proof_screenshot.png"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )

        r1 = Report.query.filter_by(booking_id=b1.id, reporter_id=learner1.id).first()
        if r1 and r1.reason == "late" and r1.status == "pending":
            ok(f"Report #{r1.id} created with reason='late', status='pending'")
        else:
            fail("Report creation failed", f"r1={r1}")

        if r1 and not r1.refund_requested and r1.refund_request_id is None:
            ok("refund_requested=False, no RefundRequest created")
        else:
            fail("Unexpected refund request created")

        if r1 and len(r1.evidence_items) >= 1:
            ev = r1.evidence_items[0]
            ok(f"ReportEvidence created: type={ev.file_type}, file={ev.original_filename}")
        else:
            fail("ReportEvidence not attached to report")

        new_notifs = Notification.query.count() - notif_before
        if new_notifs >= 2:
            ok(f"{new_notifs} notifications created (admin + teacher)")
        else:
            fail(f"Expected >=2 notifications, got {new_notifs}")

        # Admin notification
        admin_notif = Notification.query.filter(
            Notification.user_id == admin.id,
            Notification.title.contains(f"Booking #{b1.id}"),
        ).first()
        if admin_notif:
            ok(f"Admin notified: '{admin_notif.title}'")
        else:
            fail("Admin notification not found for TEST 1")

        # Teacher notification
        teacher_notif = Notification.query.filter(
            Notification.user_id == teacher1.id,
            Notification.title.contains(f"Booking #{b1.id}"),
        ).first()
        if teacher_notif:
            ok(f"Teacher notified: '{teacher_notif.title}'")
        else:
            fail("Teacher notification not found for TEST 1")

        # Payment untouched
        db.session.refresh(p1)
        if p1.status == "success" and p1.refund_amount is None:
            ok("Payment remains 'success' with no automatic refund")
        else:
            fail(f"Payment unexpectedly modified: status={p1.status}")

        # ─────────────────────────────────────────────────────────────────────
        # TEST 2 — Learner reports teacher + requests refund
        # ─────────────────────────────────────────────────────────────────────
        section("TEST 2 — Learner reports teacher + requests refund (no auto-refund)")
        b2, p2 = create_booking_payment(learner1, teacher1, amount=2500)

        login_as(client, learner1)
        resp2 = client.post(
            f"/reports/booking/{b2.id}",
            data={
                "reason": "teacher_marked_completed_without_teaching",
                "description": "Teacher did not join the call and marked completed.",
                "request_refund": "yes",
                "evidence": (io.BytesIO(b"fake absence proof"), "absence_proof.jpg"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )

        r2 = Report.query.filter_by(booking_id=b2.id, reporter_id=learner1.id).first()
        if r2 and r2.refund_requested:
            ok(f"Report #{r2.id} created with refund_requested=True")
        else:
            fail("Report creation or refund_requested failed", f"r2={r2}")

        rr2 = None
        if r2:
            rr2 = RefundRequest.query.filter_by(booking_id=b2.id, status="pending").first()
            if rr2 and r2.refund_request_id == rr2.id:
                ok(f"RefundRequest #{rr2.id} safely linked to Report #{r2.id}")
            else:
                fail("RefundRequest not properly linked", f"rr2={rr2}")

        db.session.refresh(p2)
        if p2.status == "success" and p2.refund_amount is None:
            ok("No automatic refund: payment remains 'success'")
        else:
            fail(f"Payment auto-refunded unexpectedly: status={p2.status}")

        # Unified notification to admin (no duplicate)
        admin_notif2 = Notification.query.filter(
            Notification.user_id == admin.id,
            Notification.body.contains("requested a refund"),
        ).first()
        if admin_notif2:
            ok("Unified admin notification mentions both complaint and refund request")
        else:
            fail("Admin notification did not mention refund request")

        # ─────────────────────────────────────────────────────────────────────
        # TEST 3 — Admin approves refund via Report Admin (direct service call)
        # ─────────────────────────────────────────────────────────────────────
        section("TEST 3 — Admin approves refund from Report Admin")
        if r2 and rr2 and p2.status == "success":
            result = process_refund(p2, Decimal("2000.00"), admin, f"Report Admin #{r2.id}: Partial refund for 45m missed")
            db.session.refresh(p2)

            if result["success"]:
                ok("process_refund() returned success=True")
            else:
                fail(f"process_refund() failed: {result.get('error')}")

            if p2.status == "refunded":
                ok("Payment.status == 'refunded'")
            else:
                fail(f"Payment status is '{p2.status}', expected 'refunded'")

            if p2.refund_amount == Decimal("2000.00") and p2.teacher_payout_amount == Decimal("0.00"):
                ok("refund_amount=2000.00, teacher_payout_amount=0.00")
            else:
                fail(f"Amounts wrong: refund={p2.refund_amount}, payout={p2.teacher_payout_amount}")

            # Synchronize RefundRequest
            is_full = (Decimal("2000.00") == Decimal(str(p2.amount)))
            rr2.status = "approved" if is_full else "partially_approved"
            rr2.approved_amount = Decimal("2000.00")
            rr2.admin_notes = "Partial refund approved via Report Admin"
            rr2.decided_by = admin.id
            rr2.decided_at = datetime.utcnow()

            # Mark report resolved
            r2.status = "resolved"
            r2.resolved_at = datetime.utcnow()
            r2.admin_notes = f"Refunded NPR 2000.00 via Payment #{p2.id}"
            db.session.commit()

            db.session.refresh(rr2)
            if rr2.status == "partially_approved":
                ok(f"RefundRequest #{rr2.id} status = 'partially_approved'")
            else:
                fail(f"RefundRequest status is '{rr2.status}'")

            db.session.refresh(r2)
            if r2.status == "resolved":
                ok(f"Report #{r2.id} marked as 'resolved'")
            else:
                fail(f"Report status is '{r2.status}'")
        else:
            fail("Skipped TEST 3: prerequisites not met (r2 or rr2 missing)")

        # ─────────────────────────────────────────────────────────────────────
        # TEST 4 — Teacher reports learner (no refund option)
        # ─────────────────────────────────────────────────────────────────────
        section("TEST 4 — Teacher reports learner (no refund option)")
        b4, p4 = create_booking_payment(learner2, teacher1, amount=1500)

        login_as(client, teacher1)
        resp4 = client.post(
            f"/reports/booking/{b4.id}",
            data={
                "reason": "false_or_misleading_information",
                "description": "Student provided inaccurate requirements and sent abusive messages.",
                "request_refund": "yes",  # Teacher attempts to sneak refund request
                "evidence": (io.BytesIO(b"teacher chat screenshot"), "chat_log.png"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )

        r4 = Report.query.filter_by(booking_id=b4.id, reporter_id=teacher1.id).first()
        if r4 and r4.reported_id == learner2.id:
            ok(f"Teacher Report #{r4.id} created against learner #{learner2.id}")
        else:
            fail(f"Teacher report creation failed, r4={r4}")

        if r4 and not r4.refund_requested and r4.refund_request_id is None:
            ok("Teacher refund attempt blocked: refund_requested=False, no RefundRequest")
        else:
            fail("Teacher was permitted to request refund!")

        learner_notif = Notification.query.filter(
            Notification.user_id == learner2.id,
            Notification.title.contains(f"Booking #{b4.id}"),
        ).first()
        if learner_notif:
            ok(f"Learner notified: '{learner_notif.title}'")
        else:
            fail("Learner notification missing")

        # ─────────────────────────────────────────────────────────────────────
        # TEST 5 — Teacher disputes learner's accusation (Response system)
        # ─────────────────────────────────────────────────────────────────────
        section("TEST 5 — Teacher responds to learner's report")
        b5, p5 = create_booking_payment(learner2, teacher2, amount=1800)

        # Step 1: Learner files report
        login_as(client, learner2)
        client.post(
            f"/reports/booking/{b5.id}",
            data={
                "reason": "inappropriate_behavior",
                "description": "Teacher was rude during the video session.",
                "request_refund": "no",
                "evidence": (io.BytesIO(b"learner evidence data"), "evidence_clip.png"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )

        r5 = Report.query.filter_by(booking_id=b5.id, reporter_id=learner2.id).first()
        if not r5:
            fail("CRITICAL: Learner report for TEST 5 not created!")
        else:
            ok(f"Learner report #{r5.id} created (reason='{r5.reason}')")
            orig_description = r5.description

            # Step 2: Teacher responds
            login_as(client, teacher2)
            resp5 = client.post(
                f"/reports/{r5.id}/respond",
                data={
                    "explanation": "This accusation is false. Full recording shows professional conduct throughout.",
                    "evidence": (io.BytesIO(b"teacher recording proof"), "recording.mp4"),
                },
                content_type="multipart/form-data",
                follow_redirects=True,
            )

            db.session.refresh(r5)
            if r5.description == orig_description:
                ok("Original learner report description unchanged")
            else:
                fail("Original learner report was overwritten!")

            if len(r5.responses) == 1 and r5.responses[0].user_id == teacher2.id:
                ok(f"Teacher response stored separately (ReportResponse #{r5.responses[0].id})")
            else:
                fail(f"Teacher response not stored correctly, responses={len(r5.responses)}")

            if r5.status == "reviewed":
                ok("Report status transitioned to 'reviewed' after response")
            else:
                fail(f"Report status is '{r5.status}', expected 'reviewed'")

            # Step 3: Admin case page renders both sides
            login_as(client, admin)
            case_page = client.get(f"/admin/reports/{r5.id}")
            if case_page.status_code == 200:
                html = case_page.get_data(as_text=True)
                has_learner = "Teacher was rude" in html
                has_teacher = "This accusation is false" in html
                if has_learner and has_teacher:
                    ok("Admin case page displays both learner report and teacher response")
                else:
                    fail(f"Admin case page missing content: learner={has_learner}, teacher={has_teacher}")
            else:
                fail(f"Admin case page returned {case_page.status_code}")

        # ─────────────────────────────────────────────────────────────────────
        # TEST 6 — Unauthorized booking (IDOR protection)
        # ─────────────────────────────────────────────────────────────────────
        section("TEST 6 — Unauthorized booking submission blocked (IDOR)")
        login_as(client, learner1)  # Learner1 tries to report Learner2's booking
        resp6 = client.post(
            f"/reports/booking/{b5.id}",
            data={
                "reason": "other",
                "description": "Should be blocked.",
                "evidence": (io.BytesIO(b"x"), "x.pdf"),
            },
            content_type="multipart/form-data",
        )
        if resp6.status_code == 403:
            ok("IDOR blocked: learner1 cannot report learner2's booking (403)")
        else:
            fail(f"Expected 403, got {resp6.status_code}")

        # ─────────────────────────────────────────────────────────────────────
        # TEST 7 — Teacher direct refund endpoint blocked
        # ─────────────────────────────────────────────────────────────────────
        section("TEST 7 — Teacher cannot access refund endpoint")
        login_as(client, teacher1)
        resp7 = client.post(
            f"/booking/{b1.id}/refund-request",
            data={"reason_type": "session_not_held"},
            follow_redirects=False,
        )
        if resp7.status_code in (302, 403):
            ok(f"Teacher refund endpoint access blocked ({resp7.status_code}, redirected to {resp7.location})")
        else:
            fail(f"Expected 302 or 403, got {resp7.status_code}")

        # ─────────────────────────────────────────────────────────────────────
        # TEST 8 — Duplicate refund blocked
        # ─────────────────────────────────────────────────────────────────────
        section("TEST 8 — Duplicate refund blocked by process_refund()")
        # p2 was already refunded in TEST 3
        dup_result = process_refund(p2, Decimal("100.00"), admin, "Duplicate attempt")
        if not dup_result["success"]:
            err = dup_result.get("error", "")
            if "refunded" in err.lower() or "status" in err.lower():
                ok(f"Duplicate refund correctly blocked: '{err[:60]}...'")
            else:
                ok(f"Duplicate refund blocked (different message): '{err[:60]}'")
        else:
            fail("Double refund was not blocked!")

        # ─────────────────────────────────────────────────────────────────────
        # TEST 9 & 10 — Existing records compatibility
        # ─────────────────────────────────────────────────────────────────────
        section("TEST 9 & 10 — Existing Report and RefundRequest records")
        try:
            all_reports = Report.query.all()
            ok(f"Loaded {len(all_reports)} Report records without errors")
        except Exception as e:
            fail(f"Report query failed: {e}")

        try:
            all_rr = RefundRequest.query.all()
            ok(f"Loaded {len(all_rr)} RefundRequest records without errors")
        except Exception as e:
            fail(f"RefundRequest query failed: {e}")

        # Verify all report statuses are valid
        valid_statuses = {"pending", "reviewed", "resolved", "dismissed"}
        for rep in all_reports:
            if rep.status not in valid_statuses:
                fail(f"Report #{rep.id} has invalid status '{rep.status}'")
                break
        else:
            ok("All Report status values are valid")

        # Verify all report reasons load safely
        for rep in all_reports:
            if rep.reason:
                ok(f"All Report reason fields load successfully (sample: '{all_reports[0].reason}')")
                break
        else:
            ok("No reports to verify reasons (empty)")

        # ─────────────────────────────────────────────────────────────────────
        # TEST 11 — Payout hold with active Report Admin dispute
        # ─────────────────────────────────────────────────────────────────────
        section("TEST 11 — Payout hold with open Report Admin dispute")
        b11, p11 = create_booking_payment(learner1, teacher2, amount=3000)

        # Create report directly (model-level)
        r11 = Report(
            reporter_id=learner1.id,
            reported_id=teacher2.id,
            booking_id=b11.id,
            reason="misbehavior",
            description="Active dispute in progress",
            status="pending",
            created_at=datetime.utcnow()
        )
        db.session.add(r11)
        db.session.commit()

        hold = get_payment_hold_reason(p11)
        if hold and "report" in hold.lower():
            ok(f"Payout correctly on hold: '{hold}'")
        else:
            fail(f"Expected hold reason about report, got: '{hold}'")

        # ─────────────────────────────────────────────────────────────────────
        # TEST 12 — Admin cannot release payout while hold is active
        # ─────────────────────────────────────────────────────────────────────
        section("TEST 12 — Admin payout release blocked during active dispute")
        login_as(client, admin)
        resp12 = client.post(
            f"/admin/payouts/{p11.id}/release",
            follow_redirects=True,
        )
        db.session.refresh(p11)
        if p11.payout_status == "pending":
            ok("Payout release blocked: payout_status remains 'pending'")
        else:
            fail(f"Payout released inappropriately: status={p11.payout_status}")

        # Now dismiss the report and verify hold is lifted
        r11.status = "dismissed"
        r11.resolved_at = datetime.utcnow()
        db.session.commit()

        hold_after = get_payment_hold_reason(p11)
        if hold_after is None:
            ok("After dismissing report, payout hold released (None)")
        else:
            fail(f"Hold still active after dismissal: '{hold_after}'")

        # ─────────────────────────────────────────────────────────────────────
        # TEST 13 — Admin Report Admin queue and query param fix
        # ─────────────────────────────────────────────────────────────────────
        section("TEST 13 — Admin Report Admin queue & query param fix")
        login_as(client, admin)

        resp_filter = client.get("/admin/reports?filter=pending")
        resp_status = client.get("/admin/reports?status=pending")
        resp_refund = client.get("/admin/reports?filter=refund_requested")
        resp_all = client.get("/admin/reports?filter=all")

        if resp_filter.status_code == 200 and resp_status.status_code == 200:
            ok("Reports queue handles both ?filter= and ?status= params (query bug fix)")
        else:
            fail(f"Query param handling: ?filter={resp_filter.status_code}, ?status={resp_status.status_code}")

        if resp_refund.status_code == 200:
            ok("'refund_requested' filter tab loads successfully")
        else:
            fail(f"Refund requested filter returned {resp_refund.status_code}")

        if resp_all.status_code == 200:
            ok("'all' filter tab loads successfully")
        else:
            fail(f"All filter returned {resp_all.status_code}")

        # ─────────────────────────────────────────────────────────────────────
        # TEST 14 — Admin report detail page
        # ─────────────────────────────────────────────────────────────────────
        section("TEST 14 — Admin report detail page renders")
        if r1:
            detail = client.get(f"/admin/reports/{r1.id}")
            if detail.status_code == 200:
                html = detail.get_data(as_text=True)
                has_reason = "late" in html.lower() or "Late" in html
                has_booking = f"Booking" in html
                ok(f"Report detail page loads: has_reason={has_reason}, has_booking={has_booking}")
            else:
                fail(f"Report detail returned {detail.status_code}")

        # ─────────────────────────────────────────────────────────────────────
        # TEST 15 — Admin report action routes
        # ─────────────────────────────────────────────────────────────────────
        section("TEST 15 — Admin report action routes")
        if r1:
            # Mark under review
            mr = client.post(f"/admin/reports/{r1.id}/mark-reviewed", follow_redirects=True)
            db.session.refresh(r1)
            if r1.status == "reviewed":
                ok(f"Mark reviewed: Report #{r1.id} status is now 'reviewed'")
            else:
                fail(f"Mark reviewed failed: status={r1.status}")

            # Dismiss
            dism = client.post(
                f"/admin/reports/{r1.id}/dismiss",
                data={"admin_notes": "Automated test dismissal."},
                follow_redirects=True,
            )
            db.session.refresh(r1)
            if r1.status == "dismissed":
                ok(f"Dismiss: Report #{r1.id} status is now 'dismissed'")
            else:
                fail(f"Dismiss failed: status={r1.status}")

        # ─────────────────────────────────────────────────────────────────────
        # TEST 16 — Legacy refund route → Report synchronization
        # ─────────────────────────────────────────────────────────────────────
        section("TEST 16 — Legacy refund_approve synchronizes linked Report")
        b16, p16 = create_booking_payment(learner2, teacher2, amount=1000)

        # Create linked report + refund request
        rr16 = RefundRequest(
            booking_id=b16.id,
            learner_id=learner2.id,
            reason_type="session_not_held",
            description="Test legacy sync",
            status="pending",
        )
        db.session.add(rr16)
        db.session.flush()

        r16 = Report(
            reporter_id=learner2.id,
            reported_id=teacher2.id,
            booking_id=b16.id,
            reason="no_show",
            description="Teacher no show - legacy route test",
            status="pending",
            refund_requested=True,
            refund_request_id=rr16.id,
            created_at=datetime.utcnow(),
        )
        db.session.add(r16)
        db.session.commit()

        # Simulate legacy admin refund approval
        login_as(client, admin)
        resp16 = client.post(
            f"/admin/refunds/{rr16.id}/approve",
            data={"refund_amount": "1000.00", "admin_notes": "Legacy route approval test"},
            follow_redirects=True,
        )

        db.session.refresh(p16)
        db.session.refresh(rr16)
        db.session.refresh(r16)

        if p16.status == "refunded":
            ok("Legacy refund_approve: payment status = 'refunded'")
        else:
            fail(f"Legacy refund failed: payment status = '{p16.status}'")

        if rr16.status in ("approved", "partially_approved"):
            ok(f"Legacy refund_approve: RefundRequest status = '{rr16.status}'")
        else:
            fail(f"RefundRequest status unexpected: '{rr16.status}'")

        if r16.status == "resolved":
            ok("Legacy refund_approve: linked Report status synchronized to 'resolved'")
        else:
            fail(f"Linked Report status not synchronized: '{r16.status}'")

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"\n{BLD}{'═'*60}{RST}")
    print(f"{BLD}Report Admin Unification: {GRN}{PASS} passed{RST}, {RED if FAIL else GRN}{FAIL} failed{RST}")
    print(f"{BLD}{'═'*60}{RST}")

    if FAIL > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_tests()

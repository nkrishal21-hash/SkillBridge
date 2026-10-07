#!/usr/bin/env python3
"""
scripts/test_user_delete_and_credit.py
Automated verification for:
1. Footer credit in base.html ("Developed by Krishal Neupane")
2. Safe user delete logic:
   - Self deletion guard: admin cannot delete self
   - Admin account guard: admin cannot delete another admin
   - Empty learner: hard deleted from database
   - Empty teacher: hard deleted along with TeacherProfile
   - Active learner: soft delete / anonymize, preserve payments & bookings
   - Active teacher: soft delete / anonymize, preserve courses & profiles
   - Login prevention: original credentials fail, password hash cleared
   - Idempotent repeat deletion: handled gracefully with info message
3. Admin users list page rendering & actions
"""

import sys
import os
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app, db
from app.models import User, TeacherProfile, Course, Booking, Payment, Review, Enrollment

app = create_app()
app.config["TESTING"] = True
app.config["WTF_CSRF_ENABLED"] = False


def login_as(client, user):
    """Set the Flask-Login session to impersonate a user."""
    from flask import g
    g.__dict__.pop("_login_user", None)
    with client.session_transaction() as sess:
        sess.clear()
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True


def test_footer_credit():
    print("=== TEST 1: Footer Developer Credit ===")
    with app.test_client() as client:
        res = client.get("/")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        html = res.get_data(as_text=True)
        assert "Developed by Krishal Neupane" in html, "Developer credit not found in HTML!"
        assert "2026 SkillBridge. All rights reserved." in html, "Copyright text not found in HTML!"
        assert "footer-bottom" in html, "footer-bottom class not found in HTML!"
        print("  ✓ PASSED: Footer developer credit properly rendered.")


def test_admin_delete_safeties():
    print("\n=== TEST 2: Admin Delete Endpoint Safeties ===")
    with app.app_context():
        admin = User.query.filter_by(role="admin").first()
        assert admin is not None, "No admin user found in database!"

        client = app.test_client()
        login_as(client, admin)

        # 1. Test Self Deletion Guard
        print("  [2.1] Testing self deletion guard...")
        res = client.post(f"/admin/users/{admin.id}/delete", follow_redirects=True)
        assert res.status_code == 200
        html = res.get_data(as_text=True)
        assert "cannot delete your own" in html.lower()
        assert db.session.get(User, admin.id) is not None
        print("      ✓ PASSED: Admin cannot delete their own account.")

        # 2. Test Admin Deletion Guard (protecting other admins)
        print("  [2.2] Testing other admin deletion guard...")
        test_adm_email = f"temp_adm_{uuid.uuid4().hex[:8]}@sb.test"
        other_admin = User(
            full_name="Temporary Admin",
            email=test_adm_email,
            role="admin",
        )
        db.session.add(other_admin)
        db.session.commit()
        other_admin_id = other_admin.id

        res = client.post(f"/admin/users/{other_admin_id}/delete", follow_redirects=True)
        assert res.status_code == 200
        html = res.get_data(as_text=True)
        assert "cannot delete an administrator account" in html.lower()
        assert db.session.get(User, other_admin_id) is not None
        print("      ✓ PASSED: Administrator accounts are strictly protected from deletion.")

        db.session.delete(other_admin)
        db.session.commit()

        # 3. Test Empty Learner Hard Deletion
        print("  [2.3] Testing empty learner hard deletion...")
        empty_learner = User(
            full_name="Disposable Empty Learner",
            email=f"empty_learner_{uuid.uuid4().hex[:8]}@sb.local",
            role="learner",
        )
        empty_learner.set_password("Secret123!")
        db.session.add(empty_learner)
        db.session.commit()
        empty_id = empty_learner.id

        assert not empty_learner.has_activity(), "Empty learner should have zero activity"

        res = client.post(f"/admin/users/{empty_id}/delete", follow_redirects=True)
        assert res.status_code == 200
        html = res.get_data(as_text=True)
        assert "permanently deleted from the database" in html
        assert db.session.get(User, empty_id) is None
        print("      ✓ PASSED: Empty learner was hard-deleted from users table.")

        # 4. Test Empty Teacher Hard Deletion (with TeacherProfile)
        print("  [2.4] Testing empty teacher hard deletion...")
        empty_teacher = User(
            full_name="Disposable Empty Teacher",
            email=f"empty_teacher_{uuid.uuid4().hex[:8]}@sb.local",
            role="teacher",
        )
        empty_teacher.set_password("Secret123!")
        db.session.add(empty_teacher)
        db.session.flush()

        tp = TeacherProfile(user=empty_teacher, headline="Test Teacher", hourly_rate=500.0)
        db.session.add(tp)
        db.session.commit()
        empty_teacher_id = empty_teacher.id
        tp_id = tp.id

        assert not empty_teacher.has_activity(), "Empty teacher should have zero activity"

        res = client.post(f"/admin/users/{empty_teacher_id}/delete", follow_redirects=True)
        assert res.status_code == 200
        html = res.get_data(as_text=True)
        assert "permanently deleted from the database" in html
        assert db.session.get(User, empty_teacher_id) is None
        assert db.session.get(TeacherProfile, tp_id) is None
        print("      ✓ PASSED: Empty teacher and its profile were cleanly hard-deleted.")

        # 5. Test Active Learner Soft Delete / Anonymize
        print("  [2.5] Testing active learner soft delete / anonymization...")
        original_learner_email = f"learner_{uuid.uuid4().hex[:8]}@example.com"
        active_learner = User(
            full_name="Real Active Learner Test",
            email=original_learner_email,
            role="learner",
            profile_photo="https://example.com/photo.jpg",
            is_active=True,
        )
        active_learner.set_password("Password123!")
        db.session.add(active_learner)
        db.session.flush()
        al_id = active_learner.id

        dummy_payment = Payment(
            learner_id=al_id,
            payment_for="course",
            amount=1500.00,
            gateway="esewa",
            status="success",
        )
        db.session.add(dummy_payment)
        db.session.commit()

        assert active_learner.has_activity(), "Learner with payment must have activity!"

        res = client.post(f"/admin/users/{al_id}/delete", follow_redirects=True)
        assert res.status_code == 200
        html = res.get_data(as_text=True)
        assert "safely anonymized" in html
        assert "historical records preserved" in html

        anonymized_user = db.session.get(User, al_id)
        assert anonymized_user is not None, "Active user must NOT be deleted from DB!"
        assert anonymized_user.full_name == "Deleted User"
        assert anonymized_user.email == f"deleted_user_{al_id}@skillbridge.local"
        assert anonymized_user.profile_photo is None
        assert anonymized_user.is_active is False
        assert anonymized_user.password_hash is None
        assert anonymized_user.is_anonymized is True
        assert not anonymized_user.check_password("Password123!")
        # Old email is no longer in users table
        assert User.query.filter_by(email=original_learner_email).first() is None

        pay_check = db.session.get(Payment, dummy_payment.id)
        assert pay_check is not None
        assert pay_check.learner_id == al_id
        assert pay_check.learner.full_name == "Deleted User"
        assert pay_check.amount == 1500.00
        print("      ✓ PASSED: Active learner anonymized, personal info scrubbed, payment record intact.")

        # 6. Test Active Teacher Soft Delete / Anonymize
        print("  [2.6] Testing active teacher soft delete / anonymization...")
        original_teacher_email = f"teacher_{uuid.uuid4().hex[:8]}@example.com"
        active_teacher = User(
            full_name="Real Active Teacher Test",
            email=original_teacher_email,
            role="teacher",
            profile_photo="https://example.com/teacher.jpg",
            is_active=True,
        )
        active_teacher.set_password("TeacherPass123!")
        db.session.add(active_teacher)
        db.session.flush()
        at_id = active_teacher.id

        teacher_prof = TeacherProfile(
            user=active_teacher,
            headline="Senior Developer",
            skills="Python, Flask",
            hourly_rate=1200.0,
            linkedin_url="https://linkedin.com/in/test",
            website_url="https://test.me",
        )
        db.session.add(teacher_prof)
        db.session.flush()

        test_course = Course(
            teacher=teacher_prof,
            title="Mastering Antigravity",
            price=500.0,
            is_published=True,
            is_approved=True,
        )
        db.session.add(test_course)
        db.session.commit()

        assert active_teacher.has_activity(), "Teacher with a course must have activity!"

        res = client.post(f"/admin/users/{at_id}/delete", follow_redirects=True)
        assert res.status_code == 200
        html = res.get_data(as_text=True)
        assert "safely anonymized" in html

        anonymized_teacher = db.session.get(User, at_id)
        assert anonymized_teacher is not None, "Teacher must remain in DB!"
        assert anonymized_teacher.full_name == "Deleted User"
        assert anonymized_teacher.email == f"deleted_user_{at_id}@skillbridge.local"
        assert anonymized_teacher.profile_photo is None
        assert anonymized_teacher.is_active is False
        assert anonymized_teacher.password_hash is None
        assert anonymized_teacher.is_anonymized is True
        assert anonymized_teacher.teacher_profile is not None
        assert anonymized_teacher.teacher_profile.linkedin_url is None

        course_check = db.session.get(Course, test_course.id)
        assert course_check is not None
        assert course_check.teacher.user.full_name == "Deleted User"
        print("      ✓ PASSED: Active teacher safely anonymized, courses and profiles preserved intact.")

        # 7. Test Repeat Deletion on Anonymized Account
        print("  [2.7] Testing repeat deletion attempt on already anonymized account...")
        res = client.post(f"/admin/users/{at_id}/delete", follow_redirects=True)
        assert res.status_code == 200
        html = res.get_data(as_text=True)
        assert "already been anonymized and deactivated" in html
        print("      ✓ PASSED: Repeat deletion handled gracefully without corrupting state.")

        # Clean up test entities
        db.session.delete(course_check)
        db.session.delete(anonymized_teacher)
        db.session.delete(pay_check)
        db.session.delete(anonymized_user)
        db.session.commit()


def test_admin_users_page():
    print("\n=== TEST 3: Admin Users List Page Rendering ===")
    with app.app_context():
        admin = User.query.filter_by(role="admin").first()
        assert admin is not None

        client = app.test_client()
        login_as(client, admin)

        res = client.get("/admin/users")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        html = res.get_data(as_text=True)
        assert "Platform Users" in html
        assert "Delete" in html
        print("  ✓ PASSED: Admin users page renders with Delete actions.")


def test_anonymized_login_rejection():
    print("\n=== TEST 4: Login Rejection for Anonymized Account ===")
    with app.app_context():
        email = f"anon_check_{uuid.uuid4().hex[:8]}@example.com"
        u = User(full_name="Tester", email=email, role="learner", is_active=True)
        u.set_password("SecretPass123!")
        db.session.add(u)
        db.session.commit()
        uid = u.id

        # Anonymize
        u.full_name = "Deleted User"
        u.email = f"deleted_user_{u.id}@skillbridge.local"
        u.is_active = False
        u.password_hash = None
        db.session.commit()

        # Login attempt with original credentials
        with app.test_client() as unauth_client:
            res = unauth_client.post("/auth/login", data={"email": email, "password": "SecretPass123!"}, follow_redirects=True)
            html = res.get_data(as_text=True)
            assert "Invalid email or password" in html
            print("  ✓ PASSED: Attempting to sign in with original email fails.")

        # Cleanup
        db.session.delete(u)
        db.session.commit()


if __name__ == "__main__":
    test_footer_credit()
    test_admin_delete_safeties()
    test_admin_users_page()
    test_anonymized_login_rejection()
    print("\n" + "="*60)
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("="*60)

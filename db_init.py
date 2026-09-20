"""
db_init.py — One-time script to create all database tables.
Run once before first use, or after adding new models.

Usage:
    python db_init.py

The script creates the 'skillbridge' database if it doesn't exist (local MySQL),
then calls db.create_all() to build every table defined in app/models.py.
"""

import sys
import pymysql
from sqlalchemy import inspect, text
from app import create_app, db


def ensure_database_exists(uri: str) -> None:
    """
    For local MySQL, create the database schema if it's absent.
    Skips this step for Aiven (database is pre-created on the server).
    """
    if "localhost" not in uri and "127.0.0.1" not in uri:
        print("[db_init] Remote database — skipping auto-create schema step.")
        return

    # Parse host, port, db name from URI: mysql+pymysql://user:pass@host:port/dbname
    try:
        parts = uri.split("/")
        db_name = parts[-1].split("?")[0]  # strip SSL params
        host_part = uri.split("@")[-1].split("/")[0]
        host = host_part.split(":")[0]
        port = int(host_part.split(":")[1]) if ":" in host_part else 3306
        user_part = uri.split("@")[0].split("://")[1]
        user = user_part.split(":")[0]
        password = user_part.split(":")[1] if ":" in user_part else ""

        conn = pymysql.connect(host=host, port=port, user=user, password=password)
        cursor = conn.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        )
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[db_init] Database '{db_name}' is ready.")
    except Exception as exc:
        print(f"[db_init] WARNING: Could not auto-create database: {exc}")
        print("[db_init] Please create the database manually and retry.")
        sys.exit(1)


def migrate_payout_columns(app_ctx):
    """
    Idempotent migration: add 4 payout columns to the `payments` table
    if they do not already exist, then backfill existing successful/refunded
    payments with their 20% platform fee / 80% teacher payout split.

    Safe to run multiple times — no-op on subsequent executions.
    """
    from decimal import Decimal
    from app.models import Payment

    inspector = inspect(db.engine)
    existing_columns = {col["name"] for col in inspector.get_columns("payments")}
    statements = []
    if "platform_fee_amount" not in existing_columns:
        statements.append("ALTER TABLE payments ADD COLUMN platform_fee_amount NUMERIC(10,2) NULL")
    if "teacher_payout_amount" not in existing_columns:
        statements.append("ALTER TABLE payments ADD COLUMN teacher_payout_amount NUMERIC(10,2) NULL")
    if "payout_status" not in existing_columns:
        statements.append("ALTER TABLE payments ADD COLUMN payout_status ENUM('pending','released') NOT NULL DEFAULT 'pending'")
    if "payout_released_at" not in existing_columns:
        statements.append("ALTER TABLE payments ADD COLUMN payout_released_at DATETIME NULL")

    for stmt in statements:
        db.session.execute(text(stmt))
    if statements:
        db.session.commit()
        print(f"[db_init] Added {len(statements)} new column(s) to payments table.")
    else:
        print("[db_init] payments table already has commission columns — skipping.")

    # ── Backfill commission split onto existing successful or refunded payments ──
    commission_percent = Decimal(str(app_ctx.config.get("PLATFORM_COMMISSION_PERCENT", 20)))
    to_backfill = Payment.query.filter(
        Payment.status.in_(["success", "refunded"]),
        Payment.platform_fee_amount.is_(None)
    ).all()
    for p in to_backfill:
        p.platform_fee_amount = (p.amount * commission_percent / 100).quantize(Decimal("0.01"))
        p.teacher_payout_amount = p.amount - p.platform_fee_amount
        if not p.payout_status:
            p.payout_status = "pending"
    if to_backfill:
        db.session.commit()
        print(f"[db_init] Backfilled commission split for {len(to_backfill)} existing payment(s).")
    else:
        print("[db_init] Backfill no-op — no payment rows needed updating.")


def main():
    app = create_app()
    uri = app.config["SQLALCHEMY_DATABASE_URI"]

    ensure_database_exists(uri)

    with app.app_context():
        # Import models so SQLAlchemy knows about all tables
        import app.models  # noqa: F401

        db.create_all()
        print("[db_init] ✅ All tables created successfully.")
        print("[db_init] Tables in database:")
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        for table in inspector.get_table_names():
            print(f"          • {table}")

        # ── Idempotent payout column migration ───────────────────────────────
        print("\n[db_init] Running payout column migration...")
        from flask import current_app as _flask_app
        migrate_payout_columns(_flask_app._get_current_object())

        # ── Seed default admin account (idempotent) ──────────────────────────
        from app.models import User
        admin_email = "admin@skillbridge.com"
        existing_admin = User.query.filter_by(email=admin_email).first()
        if not existing_admin:
            admin = User(full_name="Admin", email=admin_email, role="admin")
            admin.set_password("Admin@123")
            db.session.add(admin)
            db.session.commit()
            print(f"\n[db_init] ✅ Default admin account created.")
            print(f"          email:    {admin_email}")
            print(f"          password: Admin@123")
            print("[db_init] ⚠️  Change this password immediately after first login.")
        else:
            print("\n[db_init] Admin account already exists — skipping seed.")


if __name__ == "__main__":
    main()

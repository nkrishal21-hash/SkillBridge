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
    inspector = inspect(db.engine)
    existing_cols = {c["name"] for c in inspector.get_columns("payments")}

    commission_pct = app_ctx.config.get("PLATFORM_COMMISSION_PERCENT", 20)

    new_columns = [
        ("platform_fee_amount",  "NUMERIC(10,2) NULL"),
        ("teacher_payout_amount","NUMERIC(10,2) NULL"),
        ("payout_status",        "ENUM('pending','released') NULL DEFAULT 'pending'"),
        ("payout_released_at",   "DATETIME NULL"),
    ]

    added = []
    for col_name, col_def in new_columns:
        if col_name not in existing_cols:
            sql = f"ALTER TABLE payments ADD COLUMN {col_name} {col_def};"
            db.session.execute(text(sql))
            added.append(col_name)
            print(f"[db_init]   + Added column: payments.{col_name}")
        else:
            print(f"[db_init]   ✓ Column already present: payments.{col_name}")

    if added:
        db.session.commit()
        print(f"[db_init] ✅ Migration complete — {len(added)} column(s) added.")
    else:
        print("[db_init] ✅ Migration no-op — all payout columns already present.")

    # ── Backfill existing rows that have NULL platform_fee_amount ────────────
    backfill_sql = text("""
        UPDATE payments
        SET
            platform_fee_amount  = ROUND(amount * :pct / 100, 2),
            teacher_payout_amount = amount - ROUND(amount * :pct / 100, 2),
            payout_status         = 'pending'
        WHERE status IN ('success', 'refunded')
          AND platform_fee_amount IS NULL;
    """)
    result = db.session.execute(backfill_sql, {"pct": commission_pct})
    db.session.commit()
    rows_updated = result.rowcount
    if rows_updated:
        print(f"[db_init] ✅ Backfilled {rows_updated} existing payment row(s) with {commission_pct}%/{100-commission_pct}% split.")
    else:
        print("[db_init] ✅ Backfill no-op — no rows needed updating.")


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

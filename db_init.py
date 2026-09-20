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

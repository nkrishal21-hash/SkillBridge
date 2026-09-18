"""
app/notifications/utils.py — Notification Dispatch Helper
Provides a lightweight, synchronous utility to create in-app notification records.
"""

from app import db
from app.models import Notification


def notify(user_id: int, title: str, body: str = None, notif_type: str = None, link: str = None) -> Notification:
    """
    Create and persist an in-app Notification record for a user.
    Synchronous and lightweight; rolls back gracefully if an error occurs.
    
    :param user_id: ID of the recipient User
    :param title: Notification headline
    :param body: Optional body description
    :param notif_type: Category (e.g. 'booking', 'payment', 'review', 'course', 'system')
    :param link: Optional relative or absolute URL to navigate to when clicked
    :return: The created Notification instance
    """
    try:
        notif = Notification(
            user_id=user_id,
            title=title.strip(),
            body=body.strip() if body else None,
            notif_type=notif_type.strip() if notif_type else None,
            link=link.strip() if link else None,
            is_read=False,
        )
        db.session.add(notif)
        db.session.commit()
        return notif
    except Exception as exc:
        db.session.rollback()
        # Non-fatal: log and continue without disrupting main request flow
        print(f"[SkillBridge Notifications] Failed to create notification for user {user_id}: {exc}")
        return None

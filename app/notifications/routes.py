"""
app/notifications/routes.py — Notification Routes
Provides inbox listing, single-item mark-as-read, and bulk mark-all-read endpoints.
"""

from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    request,
    abort,
)
from flask_login import login_required, current_user
from app import db
from app.models import Notification
from app.notifications import notifications_bp


@notifications_bp.route("/")
@login_required
def index():
    """
    Display paginated list of the current user's notifications, newest first.
    """
    page = request.args.get("page", 1, type=int)
    filter_status = request.args.get("filter", "all").strip().lower()

    query = Notification.query.filter_by(user_id=current_user.id)

    if filter_status == "unread":
        query = query.filter_by(is_read=False)

    query = query.order_by(Notification.created_at.desc())
    pagination = query.paginate(page=page, per_page=15, error_out=False)

    unread_count = Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).count()

    return render_template(
        "notifications/index.html",
        pagination=pagination,
        notifications=pagination.items,
        unread_count=unread_count,
        filter_status=filter_status,
    )


@notifications_bp.route("/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_read(notification_id: int):
    """
    Mark a notification as read and redirect to its attached link (if present),
    or back to the notifications index.
    """
    notif = Notification.query.get_or_404(notification_id)

    # Ownership check
    if notif.user_id != current_user.id:
        abort(403)

    if not notif.is_read:
        notif.is_read = True
        db.session.commit()

    # If the notification has an actionable target link, redirect there
    if notif.link:
        return redirect(notif.link)

    return redirect(url_for("notifications.index"))


@notifications_bp.route("/mark-all-read", methods=["POST"])
@login_required
def mark_all_read():
    """
    Bulk mark all unread notifications for the current user as read.
    """
    Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).update({"is_read": True})
    db.session.commit()

    flash("All notifications marked as read.", "info")
    return redirect(url_for("notifications.index"))

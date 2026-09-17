"""
app/chat/routes.py — Chat Blueprint Routes
Provides inbox list and 1-on-1 conversation views with persistent history.
"""

from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user
from sqlalchemy import or_, desc
from app import db
from app.models import User, Message

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/")
@login_required
def inbox():
    """
    Inbox view: list all distinct conversation partners for current_user,
    with their latest message snippet, timestamp, and unread count.
    """
    # Find all distinct user IDs that current_user has exchanged messages with
    sent_partners = db.session.query(Message.receiver_id).filter(
        Message.sender_id == current_user.id
    )
    received_partners = db.session.query(Message.sender_id).filter(
        Message.receiver_id == current_user.id
    )
    partner_ids_query = sent_partners.union(received_partners).distinct()
    partner_ids = [
        row[0] for row in partner_ids_query.all() if row[0] != current_user.id
    ]

    conversations = []
    for pid in partner_ids:
        partner = User.query.get(pid)
        if not partner:
            continue

        # Get latest message between current_user and this partner
        last_msg = (
            Message.query.filter(
                or_(
                    (Message.sender_id == current_user.id) & (Message.receiver_id == pid),
                    (Message.sender_id == pid) & (Message.receiver_id == current_user.id),
                )
            )
            .order_by(desc(Message.sent_at))
            .first()
        )

        # Count unread messages sent by this partner to current_user
        unread_count = Message.query.filter_by(
            sender_id=pid, receiver_id=current_user.id, is_read=False
        ).count()

        if last_msg:
            conversations.append(
                {
                    "partner": partner,
                    "last_message": last_msg,
                    "unread_count": unread_count,
                }
            )

    # Order conversations by most recent message sent_at descending
    conversations.sort(
        key=lambda c: c["last_message"].sent_at if c["last_message"] else None,
        reverse=True,
    )

    return render_template("chat/inbox.html", conversations=conversations)


@chat_bp.route("/<int:user_id>")
@login_required
def conversation(user_id: int):
    """
    Conversation view with specific user: full message history (oldest to newest),
    mark messages from other user as read, render SocketIO chat interface.
    """
    if user_id == current_user.id:
        abort(404)

    partner = User.query.get_or_404(user_id)

    # Mark all unread messages from this partner to current_user as read
    Message.query.filter_by(
        sender_id=user_id, receiver_id=current_user.id, is_read=False
    ).update({Message.is_read: True})
    db.session.commit()

    # Load full message history in chronological order
    messages = (
        Message.query.filter(
            or_(
                (Message.sender_id == current_user.id) & (Message.receiver_id == user_id),
                (Message.sender_id == user_id) & (Message.receiver_id == current_user.id),
            )
        )
        .order_by(Message.sent_at.asc())
        .all()
    )

    return render_template(
        "chat/conversation.html", partner=partner, messages=messages
    )

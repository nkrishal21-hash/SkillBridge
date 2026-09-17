"""
app/chat/events.py — SocketIO Event Handlers for Real-Time Chat
Handles client connections, room routing, message persistence to MySQL,
and read-receipt events.
"""

from datetime import datetime
from flask_login import current_user
from flask_socketio import emit, join_room, disconnect
from app import db, socketio
from app.models import User, Message


def get_conversation_room(user_a_id: int, user_b_id: int) -> str:
    """Generate a deterministic room name for a 1-on-1 conversation."""
    return f"conv_{min(user_a_id, user_b_id)}_{max(user_a_id, user_b_id)}"


@socketio.on("connect")
def handle_connect():
    """Reject unauthenticated socket connections."""
    if not current_user.is_authenticated:
        return False


@socketio.on("join")
def handle_join(data):
    """
    Join a deterministic conversation room between current_user and other_user.
    Payload: {"other_user_id": <int>}
    """
    if not current_user.is_authenticated:
        disconnect()
        return

    other_id_raw = data.get("other_user_id") if isinstance(data, dict) else None
    if not other_id_raw:
        return

    try:
        other_id = int(other_id_raw)
    except (ValueError, TypeError):
        return

    # User cannot join a room with themselves
    if other_id == current_user.id:
        return

    # Verify other user exists
    other_user = User.query.get(other_id)
    if not other_user:
        return

    room = get_conversation_room(current_user.id, other_id)
    join_room(room)
    emit("joined_room", {"room": room, "status": "ok"})


@socketio.on("send_message")
def handle_send_message(data):
    """
    Persist chat message to database and broadcast to conversation room.
    Payload: {"receiver_id": <int>, "body": <str>}
    """
    if not current_user.is_authenticated:
        disconnect()
        return

    if not isinstance(data, dict):
        return

    receiver_id_raw = data.get("receiver_id")
    body_raw = data.get("body")

    if not receiver_id_raw or not body_raw:
        return

    try:
        receiver_id = int(receiver_id_raw)
    except (ValueError, TypeError):
        return

    # Prevent messaging self
    if receiver_id == current_user.id:
        return

    body = str(body_raw).strip()
    if not body or len(body) > 2000:
        return

    # Verify receiver exists
    receiver = User.query.get(receiver_id)
    if not receiver:
        return

    # Persist message to database
    msg = Message(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        body=body,
        is_read=False,
        sent_at=datetime.utcnow(),
    )
    db.session.add(msg)
    db.session.commit()

    room = get_conversation_room(current_user.id, receiver_id)
    payload = {
        "id": msg.id,
        "sender_id": current_user.id,
        "sender_name": current_user.full_name,
        "receiver_id": receiver_id,
        "body": msg.body,
        "sent_at": msg.sent_at.strftime("%b %d, %Y %I:%M %p"),
        "sent_at_time": msg.sent_at.strftime("%I:%M %p"),
        "is_read": msg.is_read,
    }
    emit("new_message", payload, to=room)


@socketio.on("mark_read")
def handle_mark_read(data):
    """
    Mark messages from other_user to current_user as read in DB.
    Payload: {"other_user_id": <int>}
    """
    if not current_user.is_authenticated:
        disconnect()
        return

    if not isinstance(data, dict):
        return

    other_id_raw = data.get("other_user_id")
    if not other_id_raw:
        return

    try:
        other_id = int(other_id_raw)
    except (ValueError, TypeError):
        return

    updated_count = Message.query.filter_by(
        sender_id=other_id,
        receiver_id=current_user.id,
        is_read=False,
    ).update({Message.is_read: True})

    if updated_count > 0:
        db.session.commit()
        room = get_conversation_room(current_user.id, other_id)
        emit(
            "messages_read",
            {"reader_id": current_user.id, "sender_id": other_id},
            to=room,
        )

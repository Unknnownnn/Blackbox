from flask import Blueprint, jsonify, request, abort
from flask_login import login_required, current_user
from models.notification import Notification
from models.notification_read import NotificationRead
from models import db
from services.websocket import WebSocketService

notifications_bp = Blueprint('notifications', __name__, url_prefix='/api')


@notifications_bp.route('/notifications')
@login_required
def get_notifications():
    """Return recent notifications and user's unread count"""
    notifs = Notification.query.order_by(Notification.created_at.desc()).limit(50).all()

    # Compute unread count for current user
    read_ids = db.session.query(NotificationRead.notification_id).filter_by(user_id=current_user.id).all()
    read_ids = {r[0] for r in read_ids}

    notif_dicts = []
    unread = 0
    for n in notifs:
        d = n.to_dict()
        d['read'] = n.id in read_ids
        if not d['read']:
            unread += 1
        notif_dicts.append(d)

    return jsonify({'success': True, 'notifications': notif_dicts, 'unread': unread})


@notifications_bp.route('/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    """Mark a notification as read for the current user"""
    notif = Notification.query.get_or_404(notif_id)

    existing = NotificationRead.query.filter_by(notification_id=notif_id, user_id=current_user.id).first()
    if not existing:
        nr = NotificationRead(notification_id=notif_id, user_id=current_user.id)
        db.session.add(nr)
        db.session.commit()

    return jsonify({'success': True})


@notifications_bp.route('/notifications/<int:notif_id>/delete', methods=['POST'])
@login_required
def delete_notification(notif_id):
    """Allow admins to delete notifications and notify clients"""
    if not current_user.is_admin:
        return abort(403)

    notif = Notification.query.get_or_404(notif_id)
    db.session.delete(notif)
    db.session.commit()

    # Notify connected clients to remove this notification
    try:
        WebSocketService.emit_notification_deleted(notif_id)
    except Exception:
        pass

    return jsonify({'success': True})

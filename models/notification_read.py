from datetime import datetime
from models import db


class NotificationRead(db.Model):
    __tablename__ = 'notification_reads'

    id = db.Column(db.Integer, primary_key=True)
    notification_id = db.Column(db.Integer, db.ForeignKey('notifications.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    read_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('notification_id', 'user_id', name='uix_notification_user'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'notification_id': self.notification_id,
            'user_id': self.user_id,
            'read_at': self.read_at.isoformat() if self.read_at else None
        }

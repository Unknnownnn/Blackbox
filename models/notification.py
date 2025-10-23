from datetime import datetime
from models import db


class Notification(db.Model):
	__tablename__ = 'notifications'

	id = db.Column(db.Integer, primary_key=True)
	title = db.Column(db.String(255), nullable=False)
	body = db.Column(db.Text, nullable=False)
	created_at = db.Column(db.DateTime, default=datetime.utcnow)
	sent_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
	play_sound = db.Column(db.Boolean, default=True, nullable=False)

	def to_dict(self):
		return {
			'id': self.id,
			'title': self.title,
			'body': self.body,
			'created_at': self.created_at.isoformat() if self.created_at else None,
			'sent_by': self.sent_by,
			'play_sound': bool(self.play_sound)
		}

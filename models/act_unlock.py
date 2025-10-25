from datetime import datetime
from models import db

class ActUnlock(db.Model):
    """Track which ACTs are unlocked for users/teams"""
    __tablename__ = 'act_unlocks'
    
    id = db.Column(db.Integer, primary_key=True)
    act = db.Column(db.String(20), nullable=False, index=True)
    
    # Either user_id or team_id will be set
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id', ondelete='CASCADE'), nullable=True, index=True)
    
    # Which challenge unlocked this act
    unlocked_by_challenge_id = db.Column(db.Integer, db.ForeignKey('challenges.id', ondelete='SET NULL'), nullable=True)
    
    unlocked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = db.relationship('User', backref='act_unlocks')
    team = db.relationship('Team', backref='act_unlocks')
    challenge = db.relationship('Challenge', backref='act_unlocks')
    
    @staticmethod
    def is_act_unlocked(act, user_id=None, team_id=None):
        """Check if an ACT is unlocked for a user or team"""
        # ACT I is always unlocked
        if act == 'ACT I':
            return True
        
        if team_id:
            return ActUnlock.query.filter_by(act=act, team_id=team_id).first() is not None
        elif user_id:
            return ActUnlock.query.filter_by(act=act, user_id=user_id).first() is not None
        
        return False
    
    @staticmethod
    def unlock_act(act, user_id=None, team_id=None, challenge_id=None):
        """Unlock an ACT for a user or team"""
        from models import db
        
        # Check if already unlocked
        if ActUnlock.is_act_unlocked(act, user_id=user_id, team_id=team_id):
            return False
        
        # Create unlock record
        unlock = ActUnlock(
            act=act,
            user_id=user_id,
            team_id=team_id,
            unlocked_by_challenge_id=challenge_id
        )
        db.session.add(unlock)
        db.session.commit()
        return True
    
    @staticmethod
    def get_unlocked_acts(user_id=None, team_id=None):
        """Get list of unlocked ACTs for a user or team"""
        # ACT I is always unlocked
        unlocked = ['ACT I']
        
        if team_id:
            acts = ActUnlock.query.filter_by(team_id=team_id).order_by(ActUnlock.unlocked_at).all()
        elif user_id:
            acts = ActUnlock.query.filter_by(user_id=user_id).order_by(ActUnlock.unlocked_at).all()
        else:
            return unlocked
        
        for act_unlock in acts:
            if act_unlock.act not in unlocked:
                unlocked.append(act_unlock.act)
        
        return unlocked
    
    def __repr__(self):
        return f'<ActUnlock {self.act} for {"team_" + str(self.team_id) if self.team_id else "user_" + str(self.user_id)}>'

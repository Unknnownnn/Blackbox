from app import app
from models.user import User
from models.team import Team
from models.submission import Solve
from models.settings import Settings
from services.scoring import ScoringService

with app.app_context():
    teams = Team.query.all()
    users = User.query.all()
    solves = Solve.query.all()
    teams_enabled = Settings.get('teams_enabled', default=True, type='bool')
    ctf_started = Settings.is_ctf_started()
    scoreboard_visible = Settings.get('scoreboard_visible', default=True, type='bool')
    
    print(f"Teams Enabled: {teams_enabled}")
    print(f"CTF Started: {ctf_started}")
    print(f"Scoreboard Visible: {scoreboard_visible}")
    print(f"Teams count: {len(teams)}")
    print(f"Users count: {len(users)}")
    print(f"Solves count: {len(solves)}")
    
    for u in users:
        print(f"User: {u.username}, Admin: {u.is_admin}, Active: {u.is_active}, Team_id: {u.team_id}")
    
    for t in teams:
        print(f"Team: {t.name}, Active: {t.is_active}")
        
    print("Scoreboard output:", ScoringService.get_scoreboard(team_based=teams_enabled))

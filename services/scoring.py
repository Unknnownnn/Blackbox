import math
from models.challenge import Challenge
from models.submission import Solve
from models.team import Team
from models.user import User

class ScoringService:
    """Service for managing challenge scoring and calculations"""
    
    @staticmethod
    def calculate_dynamic_points(challenge, solve_count=None):
        """
        Calculate dynamic points for a challenge based on solve count
        Uses logarithmic decay function
        """
        if not challenge.is_dynamic:
            return challenge.initial_points
        
        if solve_count is None:
            solve_count = challenge.get_solves_count()
        
        if solve_count == 0:
            return challenge.initial_points
        
        # If we've reached the decay threshold, return minimum
        if solve_count >= challenge.decay_solves:
            return challenge.minimum_points
        
        # Logarithmic decay formula
        # Points decrease logarithmically as more teams solve
        max_points = challenge.initial_points
        min_points = challenge.minimum_points
        decay = challenge.decay_solves
        
        # Calculate using natural log for smooth decay
        points = max_points - (max_points - min_points) * \
                 (math.log(solve_count + 1) / math.log(decay + 1))
        
        return max(int(points), min_points)
    
    @staticmethod
    def get_scoreboard(team_based=True, limit=None):
        """
        Get scoreboard with rankings
        
        Args:
            team_based: If True, return team scores. If False, return individual scores
            limit: Maximum number of entries to return
        
        Returns:
            List of dictionaries with score information
        """
        if team_based:
            # Get all teams with their scores
            teams = Team.query.filter_by(is_active=True).all()
            
            scoreboard = []
            for team in teams:
                score = team.get_score()
                solves = team.get_solves_count()
                last_solve = team.get_last_solve_time()
                
                scoreboard.append({
                    'id': team.id,
                    'name': team.name,
                    'score': score,
                    'solves': solves,
                    'last_solve': last_solve.isoformat() if last_solve else None,
                    'affiliation': team.affiliation
                })
            
            # Sort by score (descending), then by last solve time (ascending - earlier is better)
            scoreboard.sort(key=lambda x: (-x['score'], x['last_solve'] or '9999'))
            
        else:
            # Get ALL individual user scores (teams mode disabled = solo competition)
            users = User.query.filter_by(is_active=True).all()
            
            scoreboard = []
            for user in users:
                score = user.get_score()
                solves = user.get_solves_count()
                
                # Get last solve time
                last_solve = user.solves.order_by(Solve.solved_at.desc()).first()
                last_solve_time = last_solve.solved_at if last_solve else None
                
                scoreboard.append({
                    'id': user.id,
                    'name': user.username,
                    'score': score,
                    'solves': solves,
                    'last_solve': last_solve_time.isoformat() if last_solve_time else None,
                    'affiliation': user.full_name or ''  # Use full_name as affiliation
                })
            
            # Sort by score (descending), then by last solve time (ascending)
            scoreboard.sort(key=lambda x: (-x['score'], x['last_solve'] or '9999'))
        
        # Add rankings
        for rank, entry in enumerate(scoreboard, 1):
            entry['rank'] = rank
        
        # Apply limit if specified
        if limit:
            scoreboard = scoreboard[:limit]
        
        return scoreboard
    
    @staticmethod
    def get_challenge_statistics():
        """Get statistics for all challenges"""
        challenges = Challenge.query.filter_by(is_visible=True).all()
        
        stats = []
        for challenge in challenges:
            solves = challenge.get_solves_count()
            submissions = challenge.get_submissions_count()
            
            stats.append({
                'id': challenge.id,
                'name': challenge.name,
                'category': challenge.category,
                'points': challenge.get_current_points(),
                'solves': solves,
                'submissions': submissions,
                'solve_rate': (solves / submissions * 100) if submissions > 0 else 0
            })
        
        return stats
    
    @staticmethod
    def get_user_progress(user_id):
        """Get detailed progress for a user"""
        user = User.query.get(user_id)
        if not user:
            return None
        
        solves = Solve.query.filter_by(user_id=user_id).all()
        
        progress = {
            'total_score': user.get_score(),
            'challenges_solved': len(solves),
            'solves': []
        }
        
        for solve in solves:
            progress['solves'].append({
                'challenge_id': solve.challenge_id,
                'challenge_name': solve.challenge.name,
                'category': solve.challenge.category,
                'points_earned': solve.points_earned,
                'solved_at': solve.solved_at.isoformat()
            })
        
        return progress
    
    @staticmethod
    def get_team_progress(team_id):
        """Get detailed progress for a team"""
        team = Team.query.get(team_id)
        if not team:
            return None
        
        solves = Solve.query.filter_by(team_id=team_id).all()
        
        progress = {
            'total_score': team.get_score(),
            'challenges_solved': len(solves),
            'solves': []
        }
        
        for solve in solves:
            solver = User.query.get(solve.user_id)
            progress['solves'].append({
                'challenge_id': solve.challenge_id,
                'challenge_name': solve.challenge.name,
                'category': solve.challenge.category,
                'points_earned': solve.points_earned,
                'solved_at': solve.solved_at.isoformat(),
                'solved_by': solver.username if solver else 'Unknown'
            })
        
        return progress

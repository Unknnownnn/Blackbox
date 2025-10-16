"""
Database initialization script
Creates all tables and optionally populates with sample data
"""

from app import create_app
from models import db
from models.user import User
from models.team import Team
from models.challenge import Challenge
from models.submission import Submission, Solve
from models.file import ChallengeFile
from models.settings import Settings
from models.hint import Hint, HintUnlock
from models.branching import ChallengeFlag, ChallengePrerequisite, ChallengeUnlock
import sys

def init_database(with_sample_data=True):
    """Initialize the database"""
    app = create_app()
    
    with app.app_context():
        print("Creating database tables...")
        
        # Instead of drop_all which fails with circular dependencies,
        # we'll check if tables exist and only drop if needed
        try:
            # Try to drop all tables - handle circular dependency gracefully
            inspector = db.inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            if existing_tables:
                print(f"  Found existing tables: {', '.join(existing_tables)}")
                print("  Dropping foreign key constraints first...")
                
                # Drop tables in reverse dependency order
                with db.engine.begin() as conn:
                    # Disable foreign key checks temporarily
                    if db.engine.dialect.name == 'mysql':
                        conn.execute(db.text('SET FOREIGN_KEY_CHECKS = 0'))
                    elif db.engine.dialect.name == 'postgresql':
                        conn.execute(db.text('SET CONSTRAINTS ALL DEFERRED'))
                    
                    # Drop all tables
                    db.metadata.drop_all(bind=conn)
                    
                    # Re-enable foreign key checks
                    if db.engine.dialect.name == 'mysql':
                        conn.execute(db.text('SET FOREIGN_KEY_CHECKS = 1'))
                
                print("  ✓ Existing tables dropped")
        except Exception as e:
            print(f"  Note: {e}")
            print("  Proceeding with table creation...")
        
        # Create all tables
        db.create_all()
        
        print("✓ Database tables created successfully")
        
        # Initialize default settings
        print("\nInitializing default settings...")
        Settings.set('ctf_start_time', None, 'datetime', 'CTF start time')
        Settings.set('ctf_end_time', None, 'datetime', 'CTF end time')
        Settings.set('is_paused', False, 'bool', 'Is CTF paused')
        Settings.set('teams_enabled', True, 'bool', 'Enable teams feature (for solo competitions)')
        Settings.set('first_blood_bonus', 15, 'int', 'Bonus points for first blood (first solve)')
        Settings.set('allow_registration', True, 'bool', 'Allow new user registrations')
        Settings.set('team_mode', False, 'bool', 'Require teams to solve challenges')
        print("✓ Default settings initialized")
        
        if with_sample_data:
            print("\nAdding sample data...")
            add_sample_data()
            print("✓ Sample data added successfully")
        
        print("\n✓ Database initialization complete!")


def add_sample_data():
    """Add sample data for testing"""
    
    # Create admin user
    admin = User(
        username='admin',
        email='admin@ctf.local',
        full_name='Admin User',
        is_admin=True
    )
    admin.set_password('admin123')
    db.session.add(admin)
    
    # Create sample users
    users_data = [
        ('alice', 'alice@example.com', 'Alice Johnson', 'password123'),
        ('bob', 'bob@example.com', 'Bob Smith', 'password123'),
        ('charlie', 'charlie@example.com', 'Charlie Brown', 'password123'),
        ('dave', 'dave@example.com', 'Dave Wilson', 'password123'),
        ('eve', 'eve@example.com', 'Eve Davis', 'password123'),
        ('frank', 'frank@example.com', 'Frank Miller', 'password123'),
    ]
    
    users = []
    for username, email, full_name, password in users_data:
        user = User(username=username, email=email, full_name=full_name)
        user.set_password(password)
        users.append(user)
        db.session.add(user)
    
    db.session.commit()
    print("  - Created admin and 6 sample users")
    
    # Create sample teams
    team1 = Team(
        name='HackerSquad',
        affiliation='Tech University',
        country='USA',
        captain_id=users[0].id
    )
    db.session.add(team1)
    
    team2 = Team(
        name='CyberNinjas',
        affiliation='Security Corp',
        country='UK',
        captain_id=users[2].id
    )
    team2.set_password('team123')
    db.session.add(team2)
    
    team3 = Team(
        name='CodeBreakers',
        affiliation='InfoSec Institute',
        country='Canada',
        captain_id=users[4].id
    )
    db.session.add(team3)
    
    db.session.commit()
    
    # Assign users to teams
    users[0].team_id = team1.id
    users[0].is_team_captain = True
    users[1].team_id = team1.id
    
    users[2].team_id = team2.id
    users[2].is_team_captain = True
    users[3].team_id = team2.id
    
    users[4].team_id = team3.id
    users[4].is_team_captain = True
    users[5].team_id = team3.id
    
    db.session.commit()
    print("  - Created 3 sample teams with members")
    
    # Create sample challenges
    challenges_data = [
        {
            'name': 'Warm Up',
            'category': 'misc',
            'description': 'Welcome to the CTF! Find the flag in the description.\n\nFlag: flag{welcome_to_ctf}',
            'flag': 'flag{welcome_to_ctf}',
            'initial_points': 100,
            'minimum_points': 25,
            'difficulty': 'easy'
        },
        {
            'name': 'Basic XSS',
            'category': 'web',
            'description': 'Find and exploit the XSS vulnerability in this web application.\n\nURL: http://challenge.ctf.local:8001',
            'flag': 'flag{xss_is_dangerous}',
            'initial_points': 300,
            'minimum_points': 75,
            'difficulty': 'medium'
        },
        {
            'name': 'SQL Injection 101',
            'category': 'web',
            'description': 'Bypass the login using SQL injection.\n\nURL: http://challenge.ctf.local:8002',
            'flag': 'flag{sqli_master}',
            'initial_points': 400,
            'minimum_points': 100,
            'difficulty': 'medium'
        },
        {
            'name': 'Caesar Cipher',
            'category': 'crypto',
            'description': 'Decrypt this message: uynl{prfne_vf_gbb_rnfl}',
            'flag': 'flag{caesar_is_too_easy}',
            'initial_points': 200,
            'minimum_points': 50,
            'difficulty': 'easy'
        },
        {
            'name': 'RSA Beginner',
            'category': 'crypto',
            'description': 'Break this RSA encryption with small primes.\n\nn = 143\ne = 7\nc = 28',
            'flag': 'flag{weak_rsa_keys}',
            'initial_points': 500,
            'minimum_points': 125,
            'difficulty': 'hard'
        },
        {
            'name': 'Buffer Overflow',
            'category': 'pwn',
            'description': 'Exploit the buffer overflow vulnerability.\n\nDownload: vuln.c',
            'flag': 'flag{stack_smashing_detected}',
            'initial_points': 600,
            'minimum_points': 150,
            'difficulty': 'hard'
        },
        {
            'name': 'Hidden Flag',
            'category': 'forensics',
            'description': 'Find the hidden flag in this image.\n\nDownload: image.png',
            'flag': 'flag{steganography_fun}',
            'initial_points': 350,
            'minimum_points': 85,
            'difficulty': 'medium'
        },
        {
            'name': 'Reverse Me',
            'category': 'reverse',
            'description': 'Reverse engineer this binary to find the flag.\n\nDownload: crackme',
            'flag': 'flag{reverse_engineering_rocks}',
            'initial_points': 450,
            'minimum_points': 110,
            'difficulty': 'hard'
        },
    ]
    
    for challenge_data in challenges_data:
        challenge = Challenge(**challenge_data)
        db.session.add(challenge)
    
    db.session.commit()
    print("  - Created 8 sample challenges across different categories")
    
    # Add some sample solves for testing scoreboard
    from datetime import datetime, timedelta
    import random
    
    challenges = Challenge.query.all()
    
    # Team 1 solves first 3 challenges (gets first blood on all 3)
    for i, challenge in enumerate(challenges[:3]):
        solve = Solve(
            user_id=users[0].id,
            team_id=team1.id,
            challenge_id=challenge.id,
            points_earned=challenge.get_current_points(),
            is_first_blood=(i == 0),  # First challenge gets first blood
            solved_at=datetime.utcnow() - timedelta(hours=random.randint(1, 24))
        )
        db.session.add(solve)
        
        submission = Submission(
            user_id=users[0].id,
            team_id=team1.id,
            challenge_id=challenge.id,
            submitted_flag=challenge.flag,
            is_correct=True
        )
        db.session.add(submission)
    
    # Team 2 solves first 2 challenges (no first blood, team 1 was first)
    for i, challenge in enumerate(challenges[:2]):
        solve = Solve(
            user_id=users[2].id,
            team_id=team2.id,
            challenge_id=challenge.id,
            points_earned=challenge.get_current_points(),
            is_first_blood=False,
            solved_at=datetime.utcnow() - timedelta(hours=random.randint(1, 20))
        )
        db.session.add(solve)
        
        submission = Submission(
            user_id=users[2].id,
            team_id=team2.id,
            challenge_id=challenge.id,
            submitted_flag=challenge.flag,
            is_correct=True
        )
        db.session.add(submission)
    
    # Team 3 solves first challenge (no first blood)
    challenge = challenges[0]
    solve = Solve(
        user_id=users[4].id,
        team_id=team3.id,
        challenge_id=challenge.id,
        points_earned=challenge.get_current_points(),
        is_first_blood=False,
        solved_at=datetime.utcnow() - timedelta(hours=random.randint(1, 18))
    )
    db.session.add(solve)
    
    submission = Submission(
        user_id=users[4].id,
        team_id=team3.id,
        challenge_id=challenge.id,
        submitted_flag=challenge.flag,
        is_correct=True
    )
    db.session.add(submission)
    
    db.session.commit()
    print("  - Added sample solves for scoreboard testing")


if __name__ == '__main__':
    # Check command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == '--no-sample-data':
        init_database(with_sample_data=False)
    else:
        init_database(with_sample_data=True)
    
    print("\n" + "="*50)
    print("Default admin credentials:")
    print("  Username: admin")
    print("  Password: admin123")
    print("="*50)
    print("\nSample user credentials:")
    print("  Username: alice, bob, charlie, dave, eve, frank")
    print("  Password: password123")
    print("="*50)

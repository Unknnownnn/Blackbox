from app import app
from models import db
from models.challenge import Challenge

with app.app_context():
    c = Challenge.query.filter_by(id=2).first()
    if c:
        print(f"Challenge ID: {c.id}")
        print(f"Name: {c.name}")
        print(f"Docker Image: {c.docker_image}")
        print(f"Docker Enabled: {c.docker_enabled}")
        print(f"Docker Flag Path: {c.docker_flag_path}")
    else:
        print("Challenge 2 not found")

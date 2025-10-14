from flask import Blueprint, render_template, redirect, url_for, flash, request
from models import db
from models.user import User
from models.settings import Settings
import os

setup_bp = Blueprint('setup', __name__, url_prefix='/setup')

def is_setup_complete():
    """Check if initial setup has been completed"""
    try:
        # Check if any admin user exists
        admin_exists = User.query.filter_by(is_admin=True).first() is not None
        return admin_exists
    except:
        # If database doesn't exist yet, setup is not complete
        return False

@setup_bp.route('/', methods=['GET', 'POST'])
def initial_setup():
    """Initial setup page - create first admin user"""
    
    # If setup is already complete, redirect to home
    if is_setup_complete():
        flash('Setup has already been completed', 'info')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        ctf_name = request.form.get('ctf_name', 'CTF Platform')
        submission_mode = request.form.get('submission_mode', 'individual')
        
        # Validation
        if not all([username, email, password, confirm_password]):
            flash('Please fill in all required fields', 'error')
            return render_template('setup.html')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('setup.html')
        
        if len(password) < 8:
            flash('Password must be at least 8 characters long', 'error')
            return render_template('setup.html')
        
        try:
            # Create first admin user
            admin = User(
                username=username,
                email=email,
                full_name='Administrator',
                is_admin=True,
                is_active=True
            )
            admin.set_password(password)
            
            db.session.add(admin)
            db.session.commit()
            
            # Save CTF settings
            Settings.set('ctf_name', ctf_name, 'string')
            Settings.set('require_team_for_challenges', submission_mode == 'team_required', 'bool')
            
            flash('Admin account created successfully! Please login.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating admin account: {str(e)}', 'error')
            return render_template('setup.html')
    
    return render_template('setup.html')

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from models import db
from models.user import User
from datetime import datetime
from utils.audit import log_audit_event
import re
from utils.email import send_email, generate_confirmation_token, verify_token
from flask import current_app

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and handler"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember', False)
        
        if not username or not password:
            flash('Please fill in all fields', 'error')
            return render_template('login.html')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been deactivated', 'error')
                return render_template('login.html')
                
            from models.settings import Settings
            require_verification = Settings.get('require_email_verification', True)
            
            if require_verification and not getattr(user, 'is_verified', True):
                flash('Please verify your email address before logging in. Check your inbox.', 'error')
                return render_template('login.html', unverified_email=user.email)
            
            login_user(user, remember=remember)
            user.last_login = datetime.utcnow()
            user.last_ip_address = request.remote_addr
            db.session.commit()
            
            log_audit_event(user_id=user.id, team_id=user.team_id, action='LOGIN_SUCCESS')
            
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            
            # Redirect based on admin status
            if user.is_admin:
                return redirect(url_for('admin.dashboard'))
            else:
                return redirect(url_for('challenges.list_challenges'))
        else:
            log_audit_event(action='LOGIN_FAILED', details={'username': username})
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page and handler"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    # Check if registration is enabled (check database settings first, then config)
    from models.settings import Settings
    registration_enabled = Settings.get('allow_registration', True)
    
    if not registration_enabled:
        flash('Registration is currently disabled. Please contact an administrator.', 'error')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        full_name = request.form.get('full_name')
        
        # Validation
        if not all([username, email, password, confirm_password]):
            flash('Please fill in all required fields', 'error')
            return render_template('register.html')
            
        # Validate username (alphanumeric and underscore only, 3-30 chars)
        if not re.match(r'^[a-zA-Z0-9_]{3,30}$', username):
            flash('Username must be 3-30 characters long and contain only letters, numbers, and underscores', 'error')
            return render_template('register.html')
            
        # Validate email format
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            flash('Please enter a valid email address', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long', 'error')
            return render_template('register.html')
        
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            flash('Username already taken', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('register.html')
        
        # Create new user
        user = User(
            username=username,
            email=email,
            full_name=full_name
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        # Send verification email if required
        from models.settings import Settings
        require_verification = Settings.get('require_email_verification', True)
        if require_verification:
            try:
                token = generate_confirmation_token(user.email)
                base_url = Settings.get('base_url', '')
                if base_url:
                    verify_url = f"{base_url.rstrip('/')}{url_for('auth.verify_email', token=token)}"
                else:
                    verify_url = url_for('auth.verify_email', token=token, _external=True)
                    
                html = f'<p>Welcome to {current_app.config.get("CTF_NAME", "the CTF")}!</p><p>Please verify your email by clicking the link below:</p><p><a href="{verify_url}" style="display:inline-block;padding:10px 20px;background-color:#667eea;color:white;text-decoration:none;border-radius:5px;font-weight:bold;">Verify Email Address</a></p>'
                
                from utils.email import send_email_async
                import gevent
                app = current_app._get_current_object()
                gevent.spawn(send_email_async, app, user.email, 'Verify your email address', html)
                
                flash('Registration successful! A verification email is being sent to your address. Please verify before logging in.', 'success')
            except Exception as e:
                current_app.logger.error(f"Error preparing verification email: {e}")
                flash('Registration successful, but there was an unexpected error preparing the email system.', 'warning')
        else:
            flash('Registration successful! Please login.', 'success')
        
        log_audit_event(user_id=user.id, action='REGISTER')
        
        # Clear any stale session cookies. This prevents an issue where testing with 
        # database resets causes old session cookies to instantly log the user in 
        # (since the new user gets the same database ID as the old deleted one).
        logout_user()
        
        return redirect(url_for('auth.login'))
    
    return render_template('register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Logout handler"""
    _user_id = current_user.id
    _team_id = current_user.team_id
    logout_user()
    log_audit_event(user_id=_user_id, team_id=_team_id, action='LOGOUT')
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))


@auth_bp.route('/profile')
@login_required
def profile():
    """User profile page"""
    from services.scoring import ScoringService
    
    progress = ScoringService.get_user_progress(current_user.id)
    
    return render_template('profile.html', user=current_user, progress=progress)


@auth_bp.route('/verify-email/<token>')
def verify_email(token):
    email = verify_token(token, salt='email-confirm-salt')
    if not email:
        flash('The verification link is invalid or has expired.', 'error')
        return redirect(url_for('auth.login'))
        
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('auth.login'))
        
    if getattr(user, 'is_verified', False):
        flash('Account already verified. Please login.', 'success')
    else:
        user.is_verified = True
        db.session.commit()
        log_audit_event(user_id=user.id, action='EMAIL_VERIFIED')
        flash('You have successfully verified your email! You can now login.', 'success')
        
    return redirect(url_for('auth.login'))


@auth_bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    email = request.form.get('email')
    user = User.query.filter_by(email=email).first()
    if user and not getattr(user, 'is_verified', True):
        token = generate_confirmation_token(user.email)
        from models.settings import Settings
        base_url = Settings.get('base_url', '')
        if base_url:
            verify_url = f"{base_url.rstrip('/')}{url_for('auth.verify_email', token=token)}"
        else:
            verify_url = url_for('auth.verify_email', token=token, _external=True)
            
        html = f'<p>Please verify your email by clicking the link below:</p><p><a href="{verify_url}" style="display:inline-block;padding:10px 20px;background-color:#667eea;color:white;text-decoration:none;border-radius:5px;font-weight:bold;">Verify Email Address</a></p>'
        
        from utils.email import send_email_async
        import gevent
        app = current_app._get_current_object()
        gevent.spawn(send_email_async, app, user.email, 'Verify your email address', html)
        
        flash('Verification email is being resent. Please check your inbox shortly.', 'success')
    else:
        flash('Invalid request or user already verified.', 'error')
    return redirect(url_for('auth.login'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            token = generate_confirmation_token(user.email)
            from models.settings import Settings
            base_url = Settings.get('base_url', '')
            if base_url:
                reset_url = f"{base_url.rstrip('/')}{url_for('auth.reset_password', token=token)}"
            else:
                reset_url = url_for('auth.reset_password', token=token, _external=True)
                
            html = f'<p>To reset your password, click the link below:</p><p><a href="{reset_url}" style="display:inline-block;padding:10px 20px;background-color:#667eea;color:white;text-decoration:none;border-radius:5px;font-weight:bold;">Reset Password</a></p>'
            from utils.email import send_email_async
            import gevent
            app = current_app._get_current_object()
            gevent.spawn(send_email_async, app, user.email, 'Password Reset Request', html)
        
        flash('If an account exists with that email, a password reset link has been sent.', 'info')
        return redirect(url_for('auth.login'))
        
    return render_template('forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    email = verify_token(token, salt='email-confirm-salt')
    if not email:
        flash('The password reset link is invalid or has expired.', 'error')
        return redirect(url_for('auth.login'))
        
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not password or password != confirm_password:
            flash('Passwords do not match or are empty', 'error')
            return render_template('reset_password.html', token=token)
            
        if len(password) < 6:
            flash('Password must be at least 6 characters long', 'error')
            return render_template('reset_password.html', token=token)
            
        user = User.query.filter_by(email=email).first()
        if user:
            user.set_password(password)
            db.session.commit()
            log_audit_event(user_id=user.id, action='PASSWORD_RESET')
            flash('Your password has been updated! You can now login.', 'success')
            return redirect(url_for('auth.login'))
            
    return render_template('reset_password.html', token=token)

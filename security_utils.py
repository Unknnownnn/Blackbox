"""
Security utilities for CTF Platform
Provides CSRF protection, input validation, rate limiting, and security headers
"""

import re
import html
from functools import wraps
from flask import request, jsonify, current_app, session
import secrets
import hashlib
import time

class SecurityHeaders:
    """Security headers middleware"""
    
    @staticmethod
    def add_security_headers(response):
        """Add security headers to response"""
        # Prevent clickjacking
        response.headers['X-Frame-Options'] = 'DENY'
        
        # Prevent MIME type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # Enable XSS protection
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Referrer policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Content Security Policy (adjust based on your needs)
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdn.socket.io; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https:; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "connect-src 'self' ws: wss:; "
            "frame-ancestors 'none';"
        )
        response.headers['Content-Security-Policy'] = csp
        
        # HSTS (HTTP Strict Transport Security) - only in production with HTTPS
        if not current_app.debug:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        return response


class InputValidator:
    """Input validation utilities"""
    
    # Regex patterns
    USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{3,32}$')
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    TEAM_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9\s_-]{3,50}$')
    FLAG_PATTERN = re.compile(r'^.{1,255}$')  # Basic length check
    
    @staticmethod
    def validate_username(username):
        """Validate username format"""
        if not username or not isinstance(username, str):
            return False, "Username is required"
        
        if not InputValidator.USERNAME_PATTERN.match(username):
            return False, "Username must be 3-32 characters (letters, numbers, _, -)"
        
        return True, None
    
    @staticmethod
    def validate_email(email):
        """Validate email format"""
        if not email or not isinstance(email, str):
            return False, "Email is required"
        
        if not InputValidator.EMAIL_PATTERN.match(email):
            return False, "Invalid email format"
        
        if len(email) > 255:
            return False, "Email too long"
        
        return True, None
    
    @staticmethod
    def validate_password(password):
        """Validate password strength"""
        if not password or not isinstance(password, str):
            return False, "Password is required"
        
        if len(password) < 6:
            return False, "Password must be at least 6 characters"
        
        if len(password) > 128:
            return False, "Password too long"
        
        # Check for basic complexity
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        
        if not (has_upper and has_lower and has_digit):
            return False, "Password must contain uppercase, lowercase, and digit"
        
        return True, None
    
    @staticmethod
    def validate_team_name(team_name):
        """Validate team name format"""
        if not team_name or not isinstance(team_name, str):
            return False, "Team name is required"
        
        if not InputValidator.TEAM_NAME_PATTERN.match(team_name):
            return False, "Team name must be 3-50 characters (letters, numbers, spaces, _, -)"
        
        return True, None
    
    @staticmethod
    def validate_flag(flag):
        """Validate flag format"""
        if not flag or not isinstance(flag, str):
            return False, "Flag is required"
        
        if not InputValidator.FLAG_PATTERN.match(flag):
            return False, "Flag format invalid"
        
        return True, None
    
    @staticmethod
    def sanitize_string(value, max_length=None):
        """Sanitize string input (HTML escape)"""
        if value is None:
            return None
        
        value = str(value).strip()
        
        if max_length and len(value) > max_length:
            value = value[:max_length]
        
        return html.escape(value)
    
    @staticmethod
    def validate_integer(value, min_val=None, max_val=None):
        """Validate integer input"""
        try:
            val = int(value)
            
            if min_val is not None and val < min_val:
                return False, f"Value must be at least {min_val}"
            
            if max_val is not None and val > max_val:
                return False, f"Value must be at most {max_val}"
            
            return True, val
        except (ValueError, TypeError):
            return False, "Invalid integer value"


class CSRFProtection:
    """CSRF protection utilities"""
    
    @staticmethod
    def generate_csrf_token():
        """Generate a new CSRF token"""
        if '_csrf_token' not in session:
            session['_csrf_token'] = secrets.token_hex(32)
        return session['_csrf_token']
    
    @staticmethod
    def validate_csrf_token(token):
        """Validate CSRF token"""
        if '_csrf_token' not in session:
            return False
        
        # Use secrets.compare_digest for timing-attack safe comparison
        return secrets.compare_digest(session['_csrf_token'], token)
    
    @staticmethod
    def csrf_protect():
        """Decorator to protect routes with CSRF validation"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                # Skip CSRF for GET, HEAD, OPTIONS
                if request.method in ['GET', 'HEAD', 'OPTIONS']:
                    return f(*args, **kwargs)
                
                # Get token from form or header
                token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
                
                if not token or not CSRFProtection.validate_csrf_token(token):
                    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({'success': False, 'message': 'CSRF token invalid'}), 403
                    else:
                        from flask import abort
                        abort(403, 'CSRF token invalid')
                
                return f(*args, **kwargs)
            return decorated_function
        return decorator


class RateLimiter:
    """Simple in-memory rate limiter (for non-Redis deployments)"""
    
    _limits = {}
    _cleanup_interval = 60  # Clean up old entries every 60 seconds
    _last_cleanup = time.time()
    
    @staticmethod
    def check_rate_limit(key, limit=10, window=60):
        """
        Check if rate limit is exceeded
        
        Args:
            key: Unique identifier for the rate limit (e.g., user_id:action)
            limit: Maximum number of requests
            window: Time window in seconds
        
        Returns:
            Tuple of (allowed: bool, remaining: int)
        """
        now = time.time()
        
        # Periodic cleanup
        if now - RateLimiter._last_cleanup > RateLimiter._cleanup_interval:
            RateLimiter._cleanup()
        
        # Initialize or get existing entry
        if key not in RateLimiter._limits:
            RateLimiter._limits[key] = []
        
        # Remove expired timestamps
        RateLimiter._limits[key] = [
            ts for ts in RateLimiter._limits[key]
            if now - ts < window
        ]
        
        # Check limit
        current_count = len(RateLimiter._limits[key])
        
        if current_count >= limit:
            return False, 0
        
        # Add new timestamp
        RateLimiter._limits[key].append(now)
        
        return True, limit - current_count - 1
    
    @staticmethod
    def _cleanup():
        """Clean up old rate limit entries"""
        now = time.time()
        keys_to_delete = []
        
        for key, timestamps in RateLimiter._limits.items():
            # Remove timestamps older than 5 minutes
            RateLimiter._limits[key] = [
                ts for ts in timestamps
                if now - ts < 300
            ]
            
            # Mark empty entries for deletion
            if not RateLimiter._limits[key]:
                keys_to_delete.append(key)
        
        for key in keys_to_delete:
            del RateLimiter._limits[key]
        
        RateLimiter._last_cleanup = now
    
    @staticmethod
    def rate_limit(limit=10, window=60, key_func=None):
        """
        Decorator for rate limiting routes
        
        Args:
            limit: Maximum requests
            window: Time window in seconds
            key_func: Function to generate rate limit key (default: uses IP)
        """
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                # Generate key
                if key_func:
                    key = key_func()
                else:
                    key = f"ip:{request.remote_addr}:{f.__name__}"
                
                # Check rate limit
                allowed, remaining = RateLimiter.check_rate_limit(key, limit, window)
                
                if not allowed:
                    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({
                            'success': False,
                            'message': 'Rate limit exceeded. Please try again later.'
                        }), 429
                    else:
                        from flask import abort
                        abort(429, 'Rate limit exceeded')
                
                return f(*args, **kwargs)
            return decorated_function
        return decorator


class SQLInjectionProtection:
    """SQL Injection protection utilities"""
    
    @staticmethod
    def is_sql_injection_attempt(value):
        """
        Basic SQL injection pattern detection
        Note: This is a secondary defense. Primary defense is parameterized queries.
        """
        if not isinstance(value, str):
            return False
        
        # Common SQL injection patterns
        patterns = [
            r"(\bUNION\b.*\bSELECT\b)",
            r"(\bSELECT\b.*\bFROM\b)",
            r"(\bINSERT\b.*\bINTO\b)",
            r"(\bUPDATE\b.*\bSET\b)",
            r"(\bDELETE\b.*\bFROM\b)",
            r"(\bDROP\b.*\bTABLE\b)",
            r"(;.*--)",
            r"(\/\*.*\*\/)",
            r"(\bEXEC\b|\bEXECUTE\b)",
            r"(\bxp_\w+)",
            r"(\bsp_\w+)",
        ]
        
        value_upper = value.upper()
        
        for pattern in patterns:
            if re.search(pattern, value_upper, re.IGNORECASE):
                current_app.logger.warning(f"Potential SQL injection attempt detected: {value[:50]}")
                return True
        
        return False
    
    @staticmethod
    def validate_safe_input(value, field_name="input"):
        """
        Validate input doesn't contain SQL injection patterns
        """
        if SQLInjectionProtection.is_sql_injection_attempt(value):
            return False, f"Invalid {field_name}: contains forbidden patterns"
        
        return True, None


class XSSProtection:
    """XSS protection utilities"""
    
    @staticmethod
    def sanitize_html(value, allowed_tags=None):
        """
        Sanitize HTML content (basic implementation)
        For production, consider using bleach library
        """
        if not value:
            return value
        
        # If no tags allowed, escape everything
        if allowed_tags is None:
            return html.escape(value)
        
        # Basic implementation - for production use bleach
        return html.escape(value)
    
    @staticmethod
    def validate_no_scripts(value):
        """Check for script tags or javascript: URLs"""
        if not isinstance(value, str):
            return True, None
        
        dangerous_patterns = [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',  # Event handlers like onclick=
            r'<iframe',
            r'<object',
            r'<embed',
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return False, "Input contains potentially dangerous content"
        
        return True, None


def init_security(app):
    """Initialize security features for the Flask app"""
    
    # Add security headers to all responses
    @app.after_request
    def add_security_headers(response):
        return SecurityHeaders.add_security_headers(response)
    
    # Make CSRF token available in templates
    @app.context_processor
    def inject_csrf_token():
        return dict(csrf_token=CSRFProtection.generate_csrf_token)
    
    # Log security events
    @app.before_request
    def log_security_events():
        # Log suspicious requests
        if request.method == 'POST':
            # Check for SQL injection in form data
            for key, value in request.form.items():
                if isinstance(value, str) and SQLInjectionProtection.is_sql_injection_attempt(value):
                    app.logger.warning(
                        f"Potential SQL injection from {request.remote_addr} "
                        f"in field '{key}' on {request.path}"
                    )
    
    app.logger.info("Security features initialized")

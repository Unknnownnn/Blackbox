import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app
from itsdangerous import URLSafeTimedSerializer

def get_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])

def generate_confirmation_token(email):
    serializer = get_serializer()
    return serializer.dumps(email, salt='email-confirm-salt')

def verify_token(token, salt, expiration=3600):
    serializer = get_serializer()
    try:
        email = serializer.loads(token, salt=salt, max_age=expiration)
        return email
    except:
        return False

def send_email(to_email, subject, html_content):
    from models.settings import Settings
    import logging
    logger = logging.getLogger(__name__)
    
    sender_email = Settings.get('mail_username')
    sender_password = Settings.get('mail_password')
    smtp_server = Settings.get('mail_server') or 'smtp.gmail.com'
    smtp_port = int(Settings.get('mail_port') or 587)
    
    logger.info(f"[EMAIL] Attempting to send '{subject}' to {to_email}")
    logger.info(f"[EMAIL] SMTP server: {smtp_server}:{smtp_port}")
    logger.info(f"[EMAIL] Sender configured: {bool(sender_email)} | Password configured: {bool(sender_password)}")
    
    if not sender_email or not sender_password:
        logger.error("[EMAIL] FAILED: Email credentials not configured in Settings table")
        return False
        
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = to_email
    
    part = MIMEText(html_content, 'html')
    msg.attach(part)
    
    try:
        logger.info(f"[EMAIL] Connecting to {smtp_server}:{smtp_port} ...")
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)
        logger.info("[EMAIL] Connected. Starting TLS...")
        server.starttls()
        logger.info("[EMAIL] TLS started. Logging in...")
        server.login(sender_email, sender_password)
        logger.info("[EMAIL] Logged in. Sending message...")
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        logger.info(f"[EMAIL] SUCCESS: Email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"[EMAIL] FAILED to send to {to_email}: {type(e).__name__}: {str(e)}")
        return False

def send_email_async(app, to_email, subject, html_content):
    """Send email asynchronously (gevent greenlet) to avoid blocking the web request"""
    import logging
    logger = logging.getLogger(__name__)
    try:
        with app.app_context():
            send_email(to_email, subject, html_content)
    except Exception as e:
        logger.error(f"[EMAIL ASYNC] Unhandled exception in greenlet: {type(e).__name__}: {str(e)}")


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
    
    sender_email = Settings.get('mail_username')
    sender_password = Settings.get('mail_password')
    
    if not sender_email or not sender_password:
        current_app.logger.error("Email credentials not configured")
        return False
        
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = to_email
    
    part = MIMEText(html_content, 'html')
    msg.attach(part)
    
    try:
        smtp_server = Settings.get('mail_server', 'smtp.gmail.com')
        smtp_port = int(Settings.get('mail_port', 587))
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return False

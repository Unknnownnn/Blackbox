# Gunicorn configuration file
import multiprocessing
import os

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
workers = int(os.getenv('WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = 'eventlet'
worker_connections = 1000
timeout = 120
keepalive = 5

# Logging
accesslog = os.getenv('ACCESS_LOG', '-')
errorlog = os.getenv('ERROR_LOG', '-')
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = 'ctf_platform'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (if needed)
# keyfile = None
# certfile = None

# Performance
preload_app = True
max_requests = 10000  # Increased from 1000 to prevent frequent restarts
max_requests_jitter = 500  # Increased jitter for better spread

# Restart workers gracefully
graceful_timeout = 30

def on_starting(server):
    """Called just before the master process is initialized."""
    print("Starting CTF Platform server...")

def on_reload(server):
    """Called to recycle workers during a reload."""
    print("Reloading CTF Platform server...")

def when_ready(server):
    """Called just after the server is started."""
    print(f"CTF Platform is ready. Listening on {bind}")

def on_exit(server):
    """Called just before exiting."""
    print("CTF Platform server shutting down...")

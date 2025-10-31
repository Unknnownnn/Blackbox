# Gunicorn configuration file
import multiprocessing
import os

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
# For 200+ users: Use more workers to handle concurrent load
# Eventlet is async, so each worker handles many connections
workers = int(os.getenv('WORKERS', max(8, multiprocessing.cpu_count() * 2)))
worker_class = 'eventlet'
worker_connections = 2000  # Increased from 1000 to handle more concurrent connections per worker
timeout = 300  # Increased from 120 to prevent worker timeout under high load
keepalive = 10  # Increased to reduce connection overhead

# CRITICAL: Graceful worker restart to prevent deadlocks
graceful_timeout = 60  # Force kill workers after 60s if they don't exit gracefully
worker_tmp_dir = '/dev/shm'  # Use shared memory for worker heartbeat (prevents false timeouts)

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
max_requests = 50000  # Increased to reduce frequent worker restarts (was 10000)
max_requests_jitter = 5000  # Increased jitter to spread restarts better

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

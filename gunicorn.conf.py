# Gunicorn configuration file
import multiprocessing
import os

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
# For 200+ users: Use more workers to handle concurrent load
# Using gevent instead of eventlet - more stable under high database load
workers = int(os.getenv('WORKERS', max(8, multiprocessing.cpu_count() * 2)))
worker_class = 'gevent'  # Changed from eventlet to gevent for better stability
worker_connections = 2000  # Increased from 1000 to handle more concurrent connections per worker
timeout = 300  # Increased from 120 to prevent worker timeout under high load
keepalive = 10  # Increased to reduce connection overhead
max_requests = 5000  # Reduced from 50000 - restart workers more frequently to prevent memory leaks
max_requests_jitter = 500  # Jitter for graceful restart spread

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

# Worker lifecycle callbacks for debugging
def worker_int(worker):
    """Called when a worker receives SIGINT or SIGQUIT"""
    print(f"Worker {worker.pid} received interrupt signal")

def worker_abort(worker):
    """Called when a worker times out"""
    print(f"Worker {worker.pid} timed out and is being killed")
    import traceback
    import sys
    traceback.print_stack(file=sys.stderr)

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

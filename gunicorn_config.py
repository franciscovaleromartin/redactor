"""Gunicorn configuration for memory optimization"""
import multiprocessing
import os

# Bind to the port provided by Render
bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"

# Worker configuration optimized for low memory
workers = 1  # Use only 1 worker to minimize memory usage
worker_class = 'sync'
threads = 2  # Use 2 threads per worker

# Memory optimization
max_requests = 100  # Restart workers after 100 requests to prevent memory leaks
max_requests_jitter = 20  # Add randomness to prevent all workers restarting at once
worker_tmp_dir = '/dev/shm'  # Use shared memory for worker heartbeat

# Timeout configuration
timeout = 300  # 5 minutes timeout for long article generation
graceful_timeout = 30
keepalive = 5

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

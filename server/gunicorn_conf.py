# -*- coding: utf-8 -*-
"""
Gunicorn configuration (optional, for production deployment)
"""
import os

# Workers
workers = int(os.getenv("GUNICORN_WORKERS", "2"))
worker_class = "uvicorn.workers.UvicornWorker"

# Timeout
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))

# Binding
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

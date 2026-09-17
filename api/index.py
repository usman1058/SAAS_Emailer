"""
Vercel Serverless Function Entry Point for Django

This file is the entry point for Vercel's Python serverless function.
Vercel automatically detects and uses this as the WSGI application.
"""
import os
import sys
from pathlib import Path

from django.core.wsgi import get_wsgi_application

# Add project root to Python path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Get WSGI application
app = get_wsgi_application()

# Export for Vercel (some versions expect 'app', others 'application')
application = app
handler = app
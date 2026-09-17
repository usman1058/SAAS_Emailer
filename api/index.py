"""
Vercel Serverless Function Entry Point for Django
"""
import os
import sys
from pathlib import Path

# Add project root to Python path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Import Django WSGI application
from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()

# Vercel handler
def handler(request, context):
    """Vercel serverless function handler."""
    return application(request.environ, lambda status, headers: None)
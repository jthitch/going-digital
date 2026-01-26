"""
WSGI config for photocourses project.
"""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'photocourses.settings')

application = get_wsgi_application()

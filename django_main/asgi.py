import os
from django.core.asgi import get_asgi_application
from django.conf import settings
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_main.settings")

django_asgi_app = get_asgi_application()

# Serve /static in DEBUG when running under Uvicorn
application = ASGIStaticFilesHandler(django_asgi_app) if settings.DEBUG else django_asgi_app

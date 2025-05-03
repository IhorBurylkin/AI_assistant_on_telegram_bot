import os
import django
from django.core.asgi import get_asgi_application
from django.core.management.utils import get_random_secret_key

secret_key = os.environ.get("SECRET_KEY")
if not secret_key:
    secret_key = get_random_secret_key()
    os.environ["SECRET_KEY"] = secret_key

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

application = get_asgi_application()

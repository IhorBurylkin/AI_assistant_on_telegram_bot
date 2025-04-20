from asgiref.wsgi import WsgiToAsgi
from app import app as flask_app
from services.db_utils import create_pool

# Define the init function but don't run it immediately
async def init_db():
    await create_pool()

# Create an ASGI middleware that initializes the pool on first request
class DatabaseInitMiddleware:
    def __init__(self, app):
        self.app = app
        self.initialized = False

    async def __call__(self, scope, receive, send):
        if not self.initialized and scope["type"] == "http":
            await init_db()
            self.initialized = True
        await self.app(scope, receive, send)

# Create the base ASGI app
base_asgi_app = WsgiToAsgi(flask_app)

# Wrap it with our middleware
asgi_app = DatabaseInitMiddleware(base_asgi_app)
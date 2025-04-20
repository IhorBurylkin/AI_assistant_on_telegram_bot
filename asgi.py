from asgiref.wsgi import WsgiToAsgi
from app import app as flask_app
import asyncio
from services.db_utils import create_pool

# Create a function to initialize the database pool
async def init_db():
    await create_pool()

# Run the initialization
loop = asyncio.get_event_loop()
loop.run_until_complete(init_db())

# Then create the ASGI application
asgi_app = WsgiToAsgi(flask_app)

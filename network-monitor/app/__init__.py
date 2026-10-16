'''
App
'''
from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI
import app.app_routers as app_routers
import app.utils as utils

# FastAPI object customization
FASTAPI_TITLE = "iPerf network performance orcestrator"
FASTAPI_DESCRIPTION = "Orchestrate network performance based on iPerf"
FASTAPI_VERSION = "0.109.0"
FASTAPI_OPEN_API_URL = "/"
FASTAPI_DOCS_URL = "/docs"

logger = utils.get_app_logger()


##### Run it on boot ########################
@asynccontextmanager
async def lifespan(lcm_app: FastAPI):
    """Lifecycle management for the FastAPI app."""
    # print("FastAPI app is starting up...")
    # await asyncio.sleep(10)
    # asyncio.create_task(utils.exp_runner())  # Run caller() as a background task
    yield  # Ensure app initializes and registers endpoints
    # print("FastAPI app is shutting down...")


# Create FastAPI app and use lifespan
_app = FastAPI(title=FASTAPI_TITLE,
               description=FASTAPI_DESCRIPTION,
               version=FASTAPI_VERSION,
               docs_url=FASTAPI_DOCS_URL,
               openapi_url=FASTAPI_OPEN_API_URL,
               lifespan=lifespan)

_app.include_router(router=app_routers.router)

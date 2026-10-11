import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.db import SessionLocal, init_db
from app.mcp import init_manager
from app.services.seed import seed_demo_data
from app.services.sources import rotate_stored_secrets

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def _seed_with_retry() -> None:
    delay = 1
    last_error: Exception | None = None
    for attempt in range(1, 9):
        try:
            seed_demo_data()
            return
        except Exception as exc:
            last_error = exc
            logger.warning("Demo seed attempt %s failed: %s", attempt, exc)
            time.sleep(delay)
            delay = min(delay * 2, 5)
    logger.error("Demo data was not seeded. You can still add connections. Last error: %s", last_error)


def _rotate_secrets() -> None:
    with SessionLocal() as db:
        rotated = rotate_stored_secrets(db)
    if rotated:
        logger.info("Re-encrypted %s stored secrets with the current APP_SECRET_KEY.", rotated)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _rotate_secrets()
    init_manager()
    if get_settings().seed_demo_data:
        _seed_with_retry()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")

    @app.get("/")
    def root() -> dict:
        return {"service": "meridian", "health": "/api/health", "docs": "/docs"}

    return app


app = create_app()

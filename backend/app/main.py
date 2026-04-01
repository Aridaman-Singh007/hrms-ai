import logging

from fastapi import FastAPI

from app.api.router import router as api_router
from app.core.config import get_settings
from app.core.logging import setup_logging

settings = get_settings()
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)
app.include_router(api_router)


@app.on_event("startup")
def on_startup() -> None:
    logger.info(
        "Starting %s in %s mode",
        settings.app_name,
        settings.environment,
    )


@app.on_event("shutdown")
def on_shutdown() -> None:
    logger.info("Shutting down %s", settings.app_name)

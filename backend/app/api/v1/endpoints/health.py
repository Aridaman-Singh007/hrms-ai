import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.health import HealthResponse
from app.services.health_service import get_health_status

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        db_status = "failed"
        logger.exception("Database health check failed")
    except Exception:
        db_status = "failed"
        logger.exception("Unexpected error during database health check")

    data = get_health_status(db_status=db_status)
    return HealthResponse(**data)

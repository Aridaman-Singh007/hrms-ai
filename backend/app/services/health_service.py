from app.core.config import get_settings


def get_health_status(db_status: str) -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
        "db_status": db_status,
    }

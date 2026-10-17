from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.schemas.health import HealthOut

# /health برا v1 لأنه مش جزء من الـ API نفسه، ده للـ monitoring بس
router = APIRouter(tags=["health"])

SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/health", response_model=HealthOut)
def health(settings: SettingsDep) -> HealthOut:
    return HealthOut(
        status="ok",
        version=settings.app_version,
        environment=settings.environment,
    )

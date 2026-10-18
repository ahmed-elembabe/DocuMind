from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.schemas.health import HealthOut

# المسار ده برا النسخة الأولى لأنه مش جزء من الواجهة نفسها، ده للمراقبة بس
# /health is outside /api/v1
router = APIRouter(tags=["health"])

SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/health", response_model=HealthOut)
def health(settings: SettingsDep) -> HealthOut:
    return HealthOut(
        status="ok",
        version=settings.app_version,
        environment=settings.environment,
    )

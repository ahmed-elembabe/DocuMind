from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # بيقرا القيم من environment variables، ولو مش موجودة بيدوّر في ملف .env
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "DocuMind API"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False


# lru_cache: الإعدادات بتتقري مرة واحدة بس، وبعد كده نفس الـ object بيرجع
@lru_cache
def get_settings() -> Settings:
    return Settings()

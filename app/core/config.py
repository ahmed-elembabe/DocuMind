from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class OrgConfig(BaseModel):
    id: str
    name: str
    # لو الإعدادات اتطبعت في السجل هيظهر نجوم بدل المفتاح نفسه
    # SecretStr
    api_key: SecretStr


class Settings(BaseSettings):
    # بيقرا القيم من متغيرات البيئة، ولو مش موجودة بيدوّر في ملف الإعدادات
    # environment variables -> .env
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "DocuMind API"
    app_version: str = "0.2.2"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    # أقصى حجم للملف المرفوع 2 ميجا
    max_upload_bytes: int = 2 * 1024 * 1024

    # أقصى عدد أسئلة لكل شركة في اليوم
    daily_question_quota: int = 20

    # الشركات المسموح لها تستخدم الواجهة، مؤقتاً لحد ما يبقى عندنا داتابيز
    # بتتكتب في ملف الإعدادات بصيغة جيسون، زي المثال ده
    # ORGS='[{"id": "...", "name": "...", "api_key": "..."}]'
    orgs: list[OrgConfig] = []

    @field_validator("orgs")
    @classmethod
    def api_keys_must_be_unique(cls, orgs: list[OrgConfig]) -> list[OrgConfig]:
        # لو شركتين ليهم نفس المفتاح، مش هنعرف الطلب جاي من مين
        keys = [org.api_key.get_secret_value() for org in orgs]
        if len(keys) != len(set(keys)):
            raise ValueError("كل شركة لازم يبقى ليها API key مختلف")
        return orgs


# الإعدادات بتتقري مرة واحدة بس، وبعد كده نفس النسخة بترجع
# lru_cache
@lru_cache
def get_settings() -> Settings:
    return Settings()

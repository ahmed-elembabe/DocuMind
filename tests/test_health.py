from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app


def test_health_returns_version_and_environment():
    # بنبدّل الإعدادات بقيم ثابتة عشان التست ميعتمدش على ملف الإعدادات بتاع الجهاز
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_version="9.9.9", environment="staging", _env_file=None
    )
    try:
        response = TestClient(app).get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "9.9.9", "environment": "staging"}


def test_settings_read_from_environment(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("APP_VERSION", "1.2.3")

    settings = Settings(_env_file=None)

    assert settings.environment == "production"
    assert settings.app_version == "1.2.3"

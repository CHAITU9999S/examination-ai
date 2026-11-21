import asyncio

import pytest

from app import main


def test_production_does_not_start_with_sqlite_database(monkeypatch):
    monkeypatch.setattr(main, "APP_ENV", "production")
    monkeypatch.setattr(main, "JWT_SECRET_KEY", "a-strong-production-secret-with-more-than-32-characters")
    monkeypatch.setattr(main, "DATABASE_URL", "sqlite:///./examguard_dev.db")

    async def start_app():
        async with main.lifespan(None):
            pass

    with pytest.raises(RuntimeError, match="PostgreSQL DATABASE_URL"):
        asyncio.run(start_app())

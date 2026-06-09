from __future__ import annotations

import os

# Đặt cấu hình TRƯỚC khi import bất kỳ module nào của bot (get_settings dùng lru_cache).
os.environ.setdefault("BOT_TOKEN", "123:TEST")
os.environ.setdefault("ADMIN_IDS", "1")
os.environ.setdefault("BANK_ACCOUNT", "0123456789")
os.environ.setdefault("BANK_CODE", "MB")
os.environ.setdefault("ORDER_EXPIRY_MINUTES", "5")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("WEB_SECRET", "test-web-secret")
os.environ.setdefault("PUBLIC_BASE_URL", "https://example.test")

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from bot.db.models import Base


@pytest_asyncio.fixture
async def session():
    # In-memory SQLite dùng chung 1 connection (StaticPool) để giữ bảng giữa các lần dùng.
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()

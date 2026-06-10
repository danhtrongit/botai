from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.config import get_settings
from bot.db.models import Base

_settings = get_settings()

engine = create_async_engine(_settings.database_url, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# SQLite chỉ cho 1 writer tại 1 thời điểm. Với app chạy chung 1 process (bot polling +
# web admin + expire_loop), 2 thao tác ghi cùng lúc (vd duyệt 2 đơn) sẽ văng
# "database is locked". Bật WAL (reader không chặn writer) + busy_timeout (writer chờ
# tới 5s thay vì lỗi ngay) để xử lý ghi đồng thời an toàn. Chỉ áp dụng cho SQLite.
if _settings.database_url.startswith("sqlite"):

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _record):  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


async def init_db() -> None:
    """Tạo bảng nếu chưa có + migrate cột mới."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate(conn)


async def _migrate(conn) -> None:
    """Thêm cột mới vào DB cũ (SQLite create_all không tự thêm cột)."""
    await _add_column_if_missing(
        conn, "stock_items", "cost", "ALTER TABLE stock_items ADD COLUMN cost INTEGER NOT NULL DEFAULT 0"
    )
    await _add_column_if_missing(
        conn, "products", "kind",
        "ALTER TABLE products ADD COLUMN kind VARCHAR(20) NOT NULL DEFAULT 'account'",
    )
    await _add_column_if_missing(
        conn, "orders", "buyer_email", "ALTER TABLE orders ADD COLUMN buyer_email VARCHAR(255)"
    )
    await _add_column_if_missing(
        conn, "orders", "cost", "ALTER TABLE orders ADD COLUMN cost INTEGER NOT NULL DEFAULT 0"
    )


async def _add_column_if_missing(conn, table: str, column: str, ddl: str) -> None:
    rows = (await conn.exec_driver_sql(f"PRAGMA table_info({table})")).fetchall()
    columns = {r[1] for r in rows}
    if column not in columns:
        await conn.exec_driver_sql(ddl)

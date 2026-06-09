from __future__ import annotations

from bot.config import Settings


def _make(admin_ids: str) -> Settings:
    # Dùng tên field (init kwargs có ưu tiên cao hơn env của conftest).
    return Settings(
        _env_file=None,
        bot_token="x",
        bank_account="1",
        bank_code="MB",
        admin_ids=admin_ids,
    )


def test_admin_ids_single():
    # Hồi quy: pydantic-settings không được JSON-decode field list -> mất admin.
    s = _make("7905436368")
    assert s.admin_ids == [7905436368]
    assert s.is_admin(7905436368) is True
    assert s.is_admin(123) is False


def test_admin_ids_multiple():
    s = _make("111, 222 ,333")
    assert s.admin_ids == [111, 222, 333]

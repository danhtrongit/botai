from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str
    # NoDecode: ngăn pydantic-settings tự JSON-decode -> validator nhận chuỗi gốc "id1,id2".
    admin_ids: Annotated[list[int], NoDecode] = []

    # Tài khoản nhận tiền (sinh QR VietQR + hướng dẫn CK)
    bank_account: str
    bank_code: str  # mã VietQR/Napas, vd VietinBank = ICB, MBBank = MB
    bank_account_name: str = ""

    # Khóa Fernet để mã hoá thông tin đăng nhập MBBank khi lưu DB (44 ký tự base64)
    encryption_key: str
    # Chu kỳ quét lịch sử giao dịch MBBank (giây)
    mb_poll_interval: int = 25

    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8000
    webhook_path: str = "/webhook"

    # URL công khai (tunnel/domain) để sinh link đăng nhập web admin
    public_base_url: str = ""
    # Khóa ký cookie/token phiên web admin
    web_secret: str = "dev-secret-change-me"

    order_expiry_minutes: int = 15

    # Link liên hệ hỗ trợ (Telegram)
    support_url: str = "https://t.me/ncp_ai"

    database_url: str = "sqlite+aiosqlite:///bot.db"

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _parse_admin_ids(cls, v: object) -> list[int]:
        if isinstance(v, str):
            return [int(x) for x in v.replace(" ", "").split(",") if x]
        if isinstance(v, (list, tuple)):
            return [int(x) for x in v]
        return []

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids


@lru_cache
def get_settings() -> Settings:
    return Settings()

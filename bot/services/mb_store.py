from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import repo
from bot.services import crypto

# Các key lưu trong app_settings (giá trị đã mã hoá Fernet).
KEY_USERNAME = "mb_username"
KEY_PASSWORD = "mb_password"
KEY_ACCOUNT = "mb_account_no"


@dataclass
class MBCredentials:
    username: str
    password: str
    account_no: str  # có thể rỗng -> tự dò tài khoản đầu tiên


async def save_credentials(session: AsyncSession, username: str, password: str, account_no: str = "") -> None:
    await repo.set_setting(session, KEY_USERNAME, crypto.encrypt(username))
    await repo.set_setting(session, KEY_PASSWORD, crypto.encrypt(password))
    await repo.set_setting(session, KEY_ACCOUNT, crypto.encrypt(account_no or ""))
    await session.commit()


async def get_credentials(session: AsyncSession) -> MBCredentials | None:
    enc_user = await repo.get_setting(session, KEY_USERNAME)
    enc_pass = await repo.get_setting(session, KEY_PASSWORD)
    if not enc_user or not enc_pass:
        return None
    enc_acct = await repo.get_setting(session, KEY_ACCOUNT)
    return MBCredentials(
        username=crypto.decrypt(enc_user),
        password=crypto.decrypt(enc_pass),
        account_no=crypto.decrypt(enc_acct) if enc_acct else "",
    )


async def is_configured(session: AsyncSession) -> bool:
    return (await repo.get_setting(session, KEY_USERNAME)) is not None

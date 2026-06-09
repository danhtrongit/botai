from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import AsyncMock

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import bot.services.mbbank_poll as poll
from bot.db import models, repo
from bot.services import mb_store, poll_signal
from bot.services import orders as order_service


@pytest_asyncio.fixture
async def maker(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
    m = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(poll, "async_session", m)
    yield m
    await engine.dispose()


async def _seed_order(maker):
    async with maker() as session:
        product = await repo.create_product(session, name="Netflix", price=10000)
        await session.flush()
        await repo.add_stock(session, product.id, ["u1|p1", "u2|p2"])
        await session.commit()
        created = await order_service.create_order(
            session, buyer_tg_id=42, buyer_username="bob", product_id=product.id, quantity=2
        )
        return created.order.code, created.order.id


async def _seed_upgrade_order(maker):
    async with maker() as session:
        product = await repo.create_product(
            session, name="Nâng cấp", price=20000, kind=models.KIND_UPGRADE
        )
        await session.commit()
        created = await order_service.create_order(
            session, buyer_tg_id=42, buyer_username="bob", product_id=product.id,
            quantity=1, buyer_email="me@mail.com",
        )
        return created.order.code, created.order.id


def _tx(description, ref="FT777", credit="20000"):
    return {"refNo": ref, "creditAmount": credit, "debitAmount": "0",
            "description": description, "addDescription": ""}


async def test_process_delivers_and_idempotent(maker):
    code, order_id = await _seed_order(maker)
    bot = AsyncMock()
    txns = [_tx(f"NGUYEN VAN A {code} chuyen tien")]

    n = await poll.process_transactions(bot, txns)
    assert n == 1
    async with maker() as session:
        order = await repo.get_order(session, order_id)
        assert order.status == models.DELIVERED
        assert order.payment_tx_id == "FT777"
    # Giao hàng bằng file .txt đính kèm
    assert bot.send_document.await_count == 1
    sent = bot.send_document.await_args
    assert sent.kwargs["document"].filename == f"{code}.txt"

    # Quét lại cùng giao dịch -> idempotent, không giao thêm
    n2 = await poll.process_transactions(bot, txns)
    assert n2 == 0
    assert bot.send_document.await_count == 1


async def test_process_delivers_when_code_split_by_bank(maker):
    """Ngân hàng tự chèn khoảng trắng vào mã đơn -> vẫn đối soát & giao đúng."""
    code, order_id = await _seed_order(maker)
    bot = AsyncMock()
    # Chèn khoảng trắng vào giữa mã (vd "ABCDEFGHIJ" -> "ABCD EFGHIJ").
    split_code = code[:4] + " " + code[4:]
    txns = [_tx(f"NGUYEN VAN A {split_code} chuyen tien", ref="FTSPLIT")]

    n = await poll.process_transactions(bot, txns)
    assert n == 1
    async with maker() as session:
        order = await repo.get_order(session, order_id)
        assert order.status == models.DELIVERED
        assert order.payment_tx_id == "FTSPLIT"


async def test_process_ignores_debit_and_unknown(maker):
    code, order_id = await _seed_order(maker)
    bot = AsyncMock()
    txns = [
        {"refNo": "D1", "creditAmount": "0", "debitAmount": "20000",
         "description": f"{code} tien ra", "addDescription": ""},   # tiền ra -> bỏ
        _tx("BOT999999 khong co don", ref="X1"),                     # mã đơn không tồn tại
    ]
    n = await poll.process_transactions(bot, txns)
    assert n == 0
    async with maker() as session:
        assert (await repo.get_order(session, order_id)).status == models.PENDING


async def test_process_upgrade_sets_awaiting_and_notifies(maker):
    code, order_id = await _seed_upgrade_order(maker)
    bot = AsyncMock()
    n = await poll.process_transactions(bot, [_tx(f"khach chuyen {code}", ref="FTUP")])
    assert n == 1
    async with maker() as session:
        order = await repo.get_order(session, order_id)
        assert order.status == models.AWAITING_UPGRADE
        assert order.payment_tx_id == "FTUP"
    # Đơn nâng cấp: KHÔNG gửi file tài khoản, chỉ nhắn tin (khách + admin)
    assert bot.send_document.await_count == 0
    assert bot.send_message.await_count >= 1


async def test_poll_loop_skips_mbbank_when_no_pending(maker, monkeypatch):
    poll_signal._wake.clear()
    async with maker() as session:
        await mb_store.save_credentials(session, "u", "p", "123")
    calls = []
    monkeypatch.setattr(poll, "_fetch_transactions_sync", lambda *a, **k: calls.append(1) or [])

    task = asyncio.create_task(poll.poll_loop(AsyncMock(), interval=0.01))
    await asyncio.sleep(0.05)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert calls == []  # không đăng nhập/quét MBBank khi không có đơn chờ


async def test_poll_loop_scans_when_pending(maker, monkeypatch):
    poll_signal._wake.clear()
    async with maker() as session:
        await mb_store.save_credentials(session, "u", "p", "123")
    await _seed_order(maker)  # tạo 1 đơn pending
    calls = []
    monkeypatch.setattr(poll, "_fetch_transactions_sync", lambda *a, **k: calls.append(1) or [])

    task = asyncio.create_task(poll.poll_loop(AsyncMock(), interval=0.01))
    await asyncio.sleep(0.05)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert calls  # có đơn chờ -> có quét MBBank


async def test_mb_store_encrypts_at_rest(maker):
    async with maker() as session:
        await mb_store.save_credentials(session, "myuser", "mypass", "12345")

    # Giá trị lưu trong DB phải là ciphertext (không chứa plaintext)
    async with maker() as session:
        raw_user = await repo.get_setting(session, mb_store.KEY_USERNAME)
        raw_pass = await repo.get_setting(session, mb_store.KEY_PASSWORD)
        assert "myuser" not in raw_user
        assert "mypass" not in raw_pass
        creds = await mb_store.get_credentials(session)
    assert creds.username == "myuser"
    assert creds.password == "mypass"
    assert creds.account_no == "12345"

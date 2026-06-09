from __future__ import annotations

import pytest

from bot.db import models, repo
from bot.services import wallet


async def test_topup_pending_then_confirm(session):
    req = await wallet.request_topup(session, tg_id=10, username="a", amount=100_000)
    assert req.tx.status == models.TX_PENDING
    # Chưa cộng số dư khi còn pending.
    user = await repo.get_user(session, 10)
    assert user.balance == 0

    tx = await wallet.confirm_topup(session, req.code, admin_id=1)
    assert tx is not None and tx.status == models.TX_CONFIRMED
    user = await repo.get_user(session, 10)
    assert user.balance == 100_000


async def test_topup_confirm_idempotent(session):
    req = await wallet.request_topup(session, tg_id=11, username=None, amount=50_000)
    await wallet.confirm_topup(session, req.code, admin_id=1)
    # Duyệt lần 2 không cộng thêm.
    again = await wallet.confirm_topup(session, req.code, admin_id=1)
    assert again is None
    user = await repo.get_user(session, 11)
    assert user.balance == 50_000


async def test_topup_reject_no_balance(session):
    req = await wallet.request_topup(session, tg_id=12, username=None, amount=80_000)
    tx = await wallet.reject_topup(session, req.code)
    assert tx is not None and tx.status == models.TX_REJECTED
    user = await repo.get_user(session, 12)
    assert user.balance == 0
    # Đã reject thì không confirm được nữa.
    assert await wallet.confirm_topup(session, req.code, admin_id=1) is None


async def test_topup_invalid_amount(session):
    with pytest.raises(wallet.InvalidAmount):
        await wallet.request_topup(session, tg_id=13, username=None, amount=5_000)
    with pytest.raises(wallet.InvalidAmount):
        await wallet.request_topup(session, tg_id=13, username=None, amount=99_000_000)


async def test_admin_adjust_credit_and_debit(session):
    ok, user = await wallet.admin_adjust(session, tg_id=20, amount=200_000, note="thưởng")
    assert ok and user.balance == 200_000

    ok, user = await wallet.admin_adjust(session, tg_id=20, amount=-50_000, note="phạt")
    assert ok and user.balance == 150_000


async def test_admin_debit_blocked_when_insufficient(session):
    await wallet.admin_adjust(session, tg_id=21, amount=30_000)
    ok, user = await wallet.admin_adjust(session, tg_id=21, amount=-40_000)
    assert ok is False
    assert user.balance == 30_000  # không đổi


async def test_wallet_ledger_records(session):
    await wallet.admin_adjust(session, tg_id=22, amount=100_000, note="nạp tay")
    await wallet.admin_adjust(session, tg_id=22, amount=-25_000)
    txs = await repo.list_wallet_txs(session, 22)
    assert len(txs) == 2
    # Mới nhất trước.
    assert txs[0].type == models.TX_ADMIN_DEBIT
    assert txs[0].balance_after == 75_000
    assert txs[1].type == models.TX_ADMIN_CREDIT
    assert txs[1].balance_after == 100_000

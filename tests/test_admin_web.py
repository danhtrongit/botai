from __future__ import annotations

from unittest.mock import AsyncMock

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import webhook.admin as admin_web
from bot.db import models, repo
from bot.services import orders as order_service
from bot.services import webauth
from webhook.server import create_app


@pytest_asyncio.fixture
async def client(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(admin_web, "async_session", maker)

    app = create_app(AsyncMock())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as c:
        yield c, maker
    await engine.dispose()


async def test_dashboard_requires_login(client):
    c, _ = client
    resp = await c.get("/admin")
    assert resp.status_code == 401


async def test_auth_sets_cookie_and_dashboard_loads(client):
    c, _ = client
    token = webauth.make_token(1)  # ADMIN_IDS trong conftest = "1"
    resp = await c.get(f"/admin/auth?token={token}")
    assert resp.status_code == 303
    cookie = resp.cookies.get(webauth.COOKIE_NAME)
    assert cookie

    dash = await c.get("/admin", cookies={webauth.COOKIE_NAME: cookie})
    assert dash.status_code == 200
    assert "Tổng quan" in dash.text


async def test_bad_token_rejected(client):
    c, _ = client
    resp = await c.get("/admin/auth?token=khong-hop-le")
    assert resp.status_code == 401


async def test_add_product_and_stock(client):
    c, maker = client
    cookie = webauth.make_token(1)

    r1 = await c.post(
        "/admin/products",
        data={"name": "Netflix", "price": "10000", "description": "1 thang"},
        cookies={webauth.COOKIE_NAME: cookie},
    )
    assert r1.status_code == 303

    async with maker() as session:
        products = await repo.list_products(session, only_active=False)
        assert len(products) == 1
        pid = products[0].id

    r2 = await c.post(
        "/admin/stock",
        data={"product_id": str(pid), "items": "u1|p1\nu2|p2\n\nu3|p3", "cost": "5000"},
        cookies={webauth.COOKIE_NAME: cookie},
    )
    assert r2.status_code == 303

    async with maker() as session:
        assert await repo.count_available(session, pid) == 3
        items = await repo.list_stock_items(session, pid)
        assert all(it.cost == 5000 for it in items)  # cả lô chung giá vốn


async def test_edit_product(client):
    c, maker = client
    cookie = webauth.make_token(1)
    async with maker() as session:
        p = await repo.create_product(session, name="Old", price=1000, description="x")
        await session.commit()
        pid = p.id

    # form sửa hiển thị giá trị hiện tại
    form = await c.get(f"/admin/products/{pid}/edit", cookies={webauth.COOKIE_NAME: cookie})
    assert form.status_code == 200
    assert "Old" in form.text

    r = await c.post(
        f"/admin/products/{pid}/edit",
        data={"name": "New Name", "price": "25000", "description": "mô tả mới", "is_active": "0"},
        cookies={webauth.COOKIE_NAME: cookie},
    )
    assert r.status_code == 303
    async with maker() as session:
        p = await repo.get_product(session, pid)
        assert p.name == "New Name"
        assert p.price == 25000
        assert p.is_active is False


async def test_delete_product(client):
    c, maker = client
    cookie = webauth.make_token(1)
    async with maker() as session:
        p1 = await repo.create_product(session, name="Free delete", price=1000)
        p2 = await repo.create_product(session, name="Has order", price=2000)
        await session.flush()
        await repo.add_stock(session, p2.id, ["a|b"])
        await session.commit()
        # p2 có đơn -> không được xoá
        created = await order_service.create_order(
            session, buyer_tg_id=1, buyer_username=None, product_id=p2.id, quantity=1
        )
        pid1, pid2 = p1.id, p2.id
        assert created  # noqa

    headers = {webauth.COOKIE_NAME: cookie}
    r1 = await c.post(f"/admin/products/{pid1}/delete", cookies=headers)
    assert r1.status_code == 303
    r2 = await c.post(f"/admin/products/{pid2}/delete", cookies=headers)
    assert r2.status_code == 303

    async with maker() as session:
        assert await repo.get_product(session, pid1) is None      # đã xoá
        assert await repo.get_product(session, pid2) is not None  # bị chặn vì có đơn


async def test_stock_edit_and_delete(client):
    c, maker = client
    cookie = webauth.make_token(1)
    headers = {webauth.COOKIE_NAME: cookie}
    async with maker() as session:
        p = await repo.create_product(session, name="Disney", price=3000)
        await session.flush()
        await repo.add_stock(session, p.id, ["old|pw", "del|me"])
        await session.commit()
        items = await repo.list_stock_items(session, p.id)
        pid = p.id
        edit_id = items[-1].id   # "old|pw"
        del_id = items[0].id     # "del|me"

    # trang kho hiển thị tài khoản
    page = await c.get(f"/admin/products/{pid}/stock", cookies=headers)
    assert page.status_code == 200 and "old|pw" in page.text

    # sửa payload + đổi trạng thái sang sold
    r = await c.post(
        f"/admin/stock/{edit_id}/edit",
        data={"payload": "new|pw", "status": "sold"}, cookies=headers,
    )
    assert r.status_code == 303
    async with maker() as session:
        it = await repo.get_stock_item(session, edit_id)
        assert it.payload == "new|pw" and it.status == models.SOLD

    # xoá 1 tài khoản
    r2 = await c.post(f"/admin/stock/{del_id}/delete", cookies=headers)
    assert r2.status_code == 303
    async with maker() as session:
        assert await repo.get_stock_item(session, del_id) is None


async def test_add_upgrade_product_and_admin_flow(client):
    c, maker = client
    cookie = webauth.make_token(1)
    headers = {webauth.COOKIE_NAME: cookie}

    # thêm SP loại nâng cấp qua web (kèm field kind)
    r = await c.post(
        "/admin/products",
        data={"name": "Up Spotify", "price": "50000", "kind": "upgrade"},
        cookies=headers,
    )
    assert r.status_code == 303

    async with maker() as session:
        prod = (await repo.list_products(session, only_active=False))[0]
        assert prod.kind == models.KIND_UPGRADE
        created = await order_service.create_order(
            session, buyer_tg_id=7, buyer_username=None, product_id=prod.id,
            quantity=1, buyer_email="me@mail.com",
        )
        await order_service.confirm_payment(
            session, created.order, payment_tx_id="FTUP", transfer_amount=50000
        )
        oid = created.order.id
        assert created.order.status == models.AWAITING_UPGRADE

    # trang chi tiết hiện email + nút hoàn tất nâng cấp
    detail = await c.get(f"/admin/orders/{oid}", cookies=headers)
    assert detail.status_code == 200
    assert "me@mail.com" in detail.text
    assert "Hoàn tất nâng cấp" in detail.text

    # bấm hoàn tất kèm giá vốn -> đơn chuyển delivered + lưu cost
    done = await c.post(
        f"/admin/orders/{oid}/complete-upgrade", data={"cost": "12000"}, cookies=headers
    )
    assert done.status_code == 303
    async with maker() as session:
        o = await repo.get_order(session, oid)
        assert o.status == models.DELIVERED
        assert o.cost == 12000

    # sửa lại giá vốn sau khi đã giao
    upd = await c.post(
        f"/admin/orders/{oid}/complete-upgrade", data={"cost": "9000"}, cookies=headers
    )
    assert upd.status_code == 303
    async with maker() as session:
        assert (await repo.get_order(session, oid)).cost == 9000


async def test_orders_and_sold_pages(client):
    c, maker = client
    cookie = webauth.make_token(1)
    # tạo đơn + giao hàng để có dữ liệu "đã bán"
    async with maker() as session:
        p = await repo.create_product(session, name="Spotify", price=5000)
        await session.flush()
        await repo.add_stock(session, p.id, ["acc1|pw1"])
        await session.commit()
        created = await order_service.create_order(
            session, buyer_tg_id=9, buyer_username="kh", product_id=p.id, quantity=1
        )
        await order_service.confirm_payment(session, created.order, payment_tx_id="FT9", transfer_amount=5000)
        code, oid = created.order.code, created.order.id

    headers = {webauth.COOKIE_NAME: cookie}
    orders = await c.get("/admin/orders", cookies=headers)
    assert orders.status_code == 200 and code in orders.text

    detail = await c.get(f"/admin/orders/{oid}", cookies=headers)
    assert detail.status_code == 200
    assert "acc1|pw1" in detail.text and "FT9" in detail.text

    sold = await c.get("/admin/sold", cookies=headers)
    assert sold.status_code == 200
    assert "acc1|pw1" in sold.text and "Spotify" in sold.text

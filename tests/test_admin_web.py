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


def _auth(cookie=None):
    return {webauth.COOKIE_NAME: cookie or webauth.make_token(1)}  # ADMIN_IDS=1 trong conftest


# ---------- Auth ----------

async def test_api_requires_login(client):
    c, _ = client
    resp = await c.get("/admin/api/overview")
    assert resp.status_code == 401


async def test_auth_sets_cookie(client):
    c, _ = client
    token = webauth.make_token(1)
    resp = await c.get(f"/admin/auth?token={token}")
    assert resp.status_code == 303
    assert resp.cookies.get(webauth.COOKIE_NAME)


async def test_session_and_overview(client):
    c, _ = client
    s = await c.get("/admin/api/session", cookies=_auth())
    assert s.status_code == 200 and s.json()["authenticated"] is True

    ov = await c.get("/admin/api/overview", cookies=_auth())
    assert ov.status_code == 200
    body = ov.json()
    assert "stats" in body and "recent_orders" in body


async def test_bad_token_rejected(client):
    c, _ = client
    resp = await c.get("/admin/auth?token=khong-hop-le")
    assert resp.status_code == 401


# ---------- Products & stock ----------

async def test_product_crud_and_stock(client):
    c, maker = client
    headers = _auth()

    # create
    r = await c.post("/admin/api/products", json={"name": "Netflix", "price": 10000, "description": "1 thang"}, cookies=headers)
    assert r.status_code == 200
    pid = r.json()["product"]["id"]

    # list
    lst = await c.get("/admin/api/products", cookies=headers)
    assert lst.status_code == 200 and len(lst.json()["products"]) == 1

    # update
    up = await c.patch(f"/admin/api/products/{pid}", json={"name": "New Name", "price": 25000, "is_active": False}, cookies=headers)
    assert up.status_code == 200
    async with maker() as session:
        p = await repo.get_product(session, pid)
        assert p.name == "New Name" and p.price == 25000 and p.is_active is False

    # toggle
    tg = await c.post(f"/admin/api/products/{pid}/toggle", cookies=headers)
    assert tg.status_code == 200 and tg.json()["product"]["is_active"] is True

    # add stock
    st = await c.post("/admin/api/stock", json={"product_id": pid, "items": "u1|p1\nu2|p2\n\nu3|p3", "cost": 5000}, cookies=headers)
    assert st.status_code == 200 and st.json()["added"] == 3
    async with maker() as session:
        assert await repo.count_available(session, pid) == 3

    # stock list + edit + delete
    sl = await c.get(f"/admin/api/products/{pid}/stock", cookies=headers)
    assert sl.status_code == 200
    items = sl.json()["items"]
    eid = items[0]["id"]
    ed = await c.patch(f"/admin/api/stock/{eid}", json={"payload": "new|pw", "status": "sold", "cost": 1}, cookies=headers)
    assert ed.status_code == 200 and ed.json()["item"]["payload"] == "new|pw"
    dl = await c.delete(f"/admin/api/stock/{eid}", cookies=headers)
    assert dl.status_code == 200
    async with maker() as session:
        assert await repo.get_stock_item(session, eid) is None


async def test_delete_product_blocked_when_has_orders(client):
    c, maker = client
    headers = _auth()
    async with maker() as session:
        p1 = await repo.create_product(session, name="Free delete", price=1000)
        p2 = await repo.create_product(session, name="Has order", price=2000)
        await session.flush()
        await repo.add_stock(session, p2.id, ["a|b"])
        await session.commit()
        await order_service.create_order(
            session, buyer_tg_id=1, buyer_username=None, product_id=p2.id, quantity=1
        )
        pid1, pid2 = p1.id, p2.id

    r1 = await c.delete(f"/admin/api/products/{pid1}", cookies=headers)
    assert r1.status_code == 200
    r2 = await c.delete(f"/admin/api/products/{pid2}", cookies=headers)
    assert r2.status_code == 409  # bị chặn vì có đơn

    async with maker() as session:
        assert await repo.get_product(session, pid1) is None
        assert await repo.get_product(session, pid2) is not None


# ---------- Upgrade flow ----------

async def test_upgrade_product_and_complete(client):
    c, maker = client
    headers = _auth()

    r = await c.post("/admin/api/products", json={"name": "Up Spotify", "price": 50000, "kind": "upgrade"}, cookies=headers)
    assert r.status_code == 200

    async with maker() as session:
        prod = (await repo.list_products(session, only_active=False))[0]
        assert prod.kind == models.KIND_UPGRADE
        created = await order_service.create_order(
            session, buyer_tg_id=7, buyer_username=None, product_id=prod.id,
            quantity=1, buyer_email="me@mail.com",
        )
        await order_service.approve_order(session, created.order, admin_id=1)
        oid = created.order.id
        assert created.order.status == models.AWAITING_UPGRADE

    detail = await c.get(f"/admin/api/orders/{oid}", cookies=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["is_upgrade"] is True and body["order"]["buyer_email"] == "me@mail.com"

    done = await c.post(f"/admin/api/orders/{oid}/complete-upgrade", json={"cost": 12000}, cookies=headers)
    assert done.status_code == 200
    async with maker() as session:
        o = await repo.get_order(session, oid)
        assert o.status == models.DELIVERED and o.cost == 12000

    # cập nhật lại giá vốn sau khi đã giao
    upd = await c.post(f"/admin/api/orders/{oid}/complete-upgrade", json={"cost": 9000}, cookies=headers)
    assert upd.status_code == 200
    async with maker() as session:
        assert (await repo.get_order(session, oid)).cost == 9000


# ---------- Orders & sold ----------

async def test_orders_and_sold(client):
    c, maker = client
    headers = _auth()
    async with maker() as session:
        p = await repo.create_product(session, name="Spotify", price=5000)
        await session.flush()
        await repo.add_stock(session, p.id, ["acc1|pw1"])
        await session.commit()
        created = await order_service.create_order(
            session, buyer_tg_id=9, buyer_username="kh", product_id=p.id, quantity=1
        )
        await order_service.approve_order(session, created.order, admin_id=1)
        code, oid = created.order.code, created.order.id

    orders = await c.get("/admin/api/orders", cookies=headers)
    assert orders.status_code == 200
    assert any(o["code"] == code for o in orders.json()["orders"])

    detail = await c.get(f"/admin/api/orders/{oid}", cookies=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["order"]["payment_tx_id"] == "manual:1"
    assert any(it["payload"] == "acc1|pw1" for it in body["items"])

    sold = await c.get("/admin/api/sold", cookies=headers)
    assert sold.status_code == 200
    rows = sold.json()["sold"]
    assert any(r["payload"] == "acc1|pw1" and r["product_name"] == "Spotify" for r in rows)

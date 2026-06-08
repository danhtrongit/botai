from __future__ import annotations

import html
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from bot.db import models, repo
from bot.db.database import async_session
from bot.services import mb_store, webauth

logger = logging.getLogger(__name__)

BOOTSTRAP = "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist"

THEME_CSS = """
<style>
 :root{--brand:#0e9f6e;--brand-d:#0b7d57;--ink:#0c1b15;--muted:#6b7c74;--bg:#eef2f0;--line:#e3eae7}
 body{font-family:'Manrope',system-ui,sans-serif;color:var(--ink);min-height:100vh;
   background:radial-gradient(900px 500px at 100% -8%,rgba(14,159,110,.12),transparent 60%),
              radial-gradient(700px 460px at -8% 4%,rgba(14,159,110,.07),transparent 55%),var(--bg)}
 h1,h2,h3,.ff-display,.stat-num{font-family:'Manrope',sans-serif;font-weight:800;letter-spacing:-.02em}
 .navbar{backdrop-filter:blur(12px);background:rgba(255,255,255,.82)!important;border-bottom:1px solid var(--line)}
 .navbar-brand{font-family:'Manrope';font-weight:800}
 .brand-mark{width:34px;height:34px;border-radius:11px;display:grid;place-items:center;color:#fff;
   background:linear-gradient(135deg,var(--brand),#1ec98e);box-shadow:0 6px 16px -6px rgba(14,159,110,.7)}
 .nav-link{color:var(--muted)!important;font-weight:500;display:inline-flex;align-items:center;gap:.4rem}
 .nav-link.active,.nav-link:hover{color:var(--ink)!important}
 .nav-link.active{position:relative}
 .nav-link.active::after{content:'';position:absolute;left:.6rem;right:.6rem;bottom:-6px;height:2px;background:var(--brand);border-radius:2px}
 .card{border:1px solid var(--line);border-radius:20px;background:#fff;
   box-shadow:0 1px 2px rgba(12,27,21,.04),0 18px 40px -26px rgba(12,27,21,.22)}
 .btn-brand{--bs-btn-bg:var(--brand);--bs-btn-border-color:var(--brand);--bs-btn-color:#fff;
   --bs-btn-hover-bg:var(--brand-d);--bs-btn-hover-border-color:var(--brand-d);
   --bs-btn-active-bg:var(--brand-d);--bs-btn-active-border-color:var(--brand-d)}
 .stat-num{font-size:1.8rem;font-weight:700;line-height:1}
 .icon{vertical-align:-.18em}
 code{color:var(--brand-d);background:#eafaf3;padding:.06rem .4rem;border-radius:7px;font-size:.86em}
 .table>:not(caption)>*>*{padding:.62rem .8rem}
 .table thead th{font-size:.72rem;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);font-weight:600;border-bottom-color:var(--line)}
 .cell-input{max-width:18rem}
 .muted{color:var(--muted)}
 .login-wrap{min-height:100vh;display:grid;place-items:center}
</style>
"""

# Inline SVG icons (stroke, feather-style)
_ICONS = {
    "home": '<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/>',
    "box": '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><path d="M3.27 6.96 12 12.01l8.73-5.05"/><path d="M12 22.08V12"/>',
    "receipt": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/>',
    "cart": '<circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>',
    "logout": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>',
    "edit": '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4z"/>',
    "trash": '<polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    "plus": '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
    "save": '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    "toggle": '<rect x="1" y="5" width="22" height="14" rx="7"/><circle cx="16" cy="12" r="3"/>',
    "back": '<line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>',
    "lock": '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>',
    "wallet": '<path d="M21 12V7H5a2 2 0 0 1 0-4h14v4"/><path d="M3 5v14a2 2 0 0 0 2 2h16v-5"/><path d="M18 12a2 2 0 0 0 0 4h4v-4z"/>',
}


def _icon(name: str, size: int = 18) -> str:
    return (
        f'<svg class="icon" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">'
        f'{_ICONS.get(name, "")}</svg>'
    )


_STATUS_BADGE = {
    models.PENDING: "text-bg-warning",
    models.PAID: "text-bg-info",
    models.AWAITING_UPGRADE: "text-bg-primary",
    models.DELIVERED: "text-bg-success",
    models.EXPIRED: "text-bg-secondary",
    models.FAILED: "text-bg-danger",
}
_STOCK_STATUS = [(models.AVAILABLE, "Còn"), (models.RESERVED, "Đang giữ"), (models.SOLD, "Đã bán")]
_KIND_LABEL = {models.KIND_ACCOUNT: "Tài khoản", models.KIND_UPGRADE: "Nâng cấp chính chủ"}


def _kind_badge(kind: str) -> str:
    if kind == models.KIND_UPGRADE:
        return "<span class='badge rounded-pill text-bg-primary'>Nâng cấp</span>"
    return "<span class='badge rounded-pill text-bg-light'>Tài khoản</span>"


def _kind_options(current: str) -> str:
    return "".join(
        f"<option value='{v}' {'selected' if v == current else ''}>{label}</option>"
        for v, label in _KIND_LABEL.items()
    )


def _fmt_vnd(amount: int) -> str:
    return f"{amount:,}đ".replace(",", ".")


def _fmt_dt(dt) -> str:
    return str(dt)[:19] if dt else "—"


def _status_badge(status: str) -> str:
    cls = _STATUS_BADGE.get(status, "text-bg-light")
    return f"<span class='badge rounded-pill {cls}'>{status}</span>"


def _onoff_badge(active: bool) -> str:
    return (
        "<span class='badge rounded-pill text-bg-success'>đang bán</span>"
        if active else "<span class='badge rounded-pill text-bg-secondary'>đã ẩn</span>"
    )


def _stock_status_options(current: str) -> str:
    return "".join(
        f"<option value='{v}' {'selected' if v == current else ''}>{label}</option>"
        for v, label in _STOCK_STATUS
    )


def _head(title: str) -> str:
    return f"""<!doctype html><html lang="vi" data-bs-theme="light"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · NCP Admin</title>
<link href="{BOOTSTRAP}/css/bootstrap.min.css" rel="stylesheet">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet">
{THEME_CSS}</head>"""


def _shell(body: str, active: str = "", title: str = "Quản trị") -> HTMLResponse:
    def link(href: str, key: str, icon: str, label: str) -> str:
        cls = "nav-link active" if key == active else "nav-link"
        return f"<a class='{cls}' href='{href}'>{_icon(icon)}<span>{label}</span></a>"

    nav = f"""
<nav class="navbar navbar-expand-md sticky-top">
  <div class="container-xl">
    <a class="navbar-brand d-flex align-items-center gap-2" href="/admin">
      <span class="brand-mark">{_icon('cart', 19)}</span> NCP Admin
    </a>
    <button class="navbar-toggler" data-bs-toggle="collapse" data-bs-target="#nv"><span class="navbar-toggler-icon"></span></button>
    <div class="collapse navbar-collapse" id="nv">
      <div class="navbar-nav gap-md-2 ms-md-3">
        {link('/admin', 'home', 'home', 'Tổng quan')}
        {link('/admin/products', 'products', 'box', 'Sản phẩm')}
        {link('/admin/orders', 'orders', 'receipt', 'Đơn hàng')}
        {link('/admin/sold', 'sold', 'cart', 'Đã bán')}
      </div>
      <a class="nav-link ms-md-auto text-danger" href="/admin/logout">{_icon('logout')}<span>Đăng xuất</span></a>
    </div>
  </div>
</nav>"""

    return HTMLResponse(
        f"""{_head(title)}<body>{nav}
<main class="container-xl py-4">{body}</main>
<script src="{BOOTSTRAP}/js/bootstrap.bundle.min.js"></script>
</body></html>"""
    )


def _unauthorized() -> HTMLResponse:
    return HTMLResponse(
        f"""{_head('Đăng nhập')}<body><div class="login-wrap">
<div class="card p-5 text-center" style="max-width:420px">
  <div class="brand-mark mx-auto mb-3" style="width:52px;height:52px">{_icon('lock', 26)}</div>
  <h1 class="h4 mb-2">Cần đăng nhập</h1>
  <p class="muted mb-0">Mở bot Telegram và gửi <b>/login</b> để lấy liên kết đăng nhập.</p>
</div></div></body></html>""",
        status_code=401,
    )


def _current_admin(request: Request) -> int | None:
    token = request.cookies.get(webauth.COOKIE_NAME)
    if not token:
        return None
    return webauth.verify_token(token, webauth.COOKIE_MAX_AGE)


def create_admin_router(bot: Bot | None = None) -> APIRouter:
    router = APIRouter(prefix="/admin")

    # ---------- Auth ----------

    @router.get("/auth", response_class=HTMLResponse)
    async def auth(token: str = ""):
        admin_id = webauth.verify_token(token, webauth.LOGIN_LINK_MAX_AGE)
        if admin_id is None:
            return _unauthorized()
        resp = RedirectResponse(url="/admin", status_code=303)
        resp.set_cookie(
            webauth.COOKIE_NAME, webauth.make_token(admin_id),
            max_age=webauth.COOKIE_MAX_AGE, httponly=True, samesite="lax",
        )
        return resp

    @router.get("/logout")
    async def logout():
        resp = RedirectResponse(url="/admin", status_code=303)
        resp.delete_cookie(webauth.COOKIE_NAME)
        return resp

    # ---------- Dashboard ----------

    @router.get("", response_class=HTMLResponse)
    async def dashboard(request: Request):
        if _current_admin(request) is None:
            return _unauthorized()
        async with async_session() as session:
            products = await repo.list_products(session, only_active=False)
            prod_rows = []
            for p in products:
                s = await repo.stock_summary(session, p.id)
                prod_rows.append(
                    f"<tr><td class='muted'>#{p.id}</td><td class='fw-medium'>{html.escape(p.name)}</td>"
                    f"<td>{_fmt_vnd(p.price)}</td>"
                    f"<td>{s[models.AVAILABLE]} / {s[models.RESERVED]} / {s[models.SOLD]}</td>"
                    f"<td>{_onoff_badge(p.is_active)}</td></tr>"
                )
            orders = await repo.list_recent_orders(session, limit=10)
            revenue, cost, profit, count = await repo.profit_summary(session)
            mb_creds = await mb_store.get_credentials(session)

        product_rows = "".join(prod_rows) or "<tr><td colspan='5' class='muted'>Chưa có sản phẩm</td></tr>"
        order_rows = "".join(
            f"<tr><td><a class='text-decoration-none' href='/admin/orders/{o.id}'>{html.escape(o.code)}</a></td>"
            f"<td>{html.escape('@'+o.buyer_username) if o.buyer_username else o.buyer_tg_id}</td>"
            f"<td>{o.quantity}</td><td>{_fmt_vnd(o.total_amount)}</td><td>{_status_badge(o.status)}</td></tr>"
            for o in orders
        ) or "<tr><td colspan='5' class='muted'>Chưa có đơn</td></tr>"

        if mb_creds:
            masked = html.escape(mb_creds.username[:2] + "***") if mb_creds.username else "***"
            acct = html.escape(mb_creds.account_no) if mb_creds.account_no else "tự dò"
            mb_status = f"<span class='badge rounded-pill text-bg-success'>đã cấu hình</span> <span class='muted ms-1'>user <code>{masked}</code> · TK <code>{acct}</code></span>"
        else:
            mb_status = "<span class='badge rounded-pill text-bg-danger'>chưa cấu hình</span> <span class='muted ms-1'>bot chưa thể quét giao dịch</span>"

        body = f"""
<h1 class="h3 mb-4">Tổng quan</h1>
<div class="row g-3 mb-4">
  <div class="col-6 col-lg-3"><div class="card p-3 h-100"><div class="muted small">Doanh thu</div><div class="stat-num mt-1">{_fmt_vnd(revenue)}</div></div></div>
  <div class="col-6 col-lg-3"><div class="card p-3 h-100"><div class="muted small">Giá vốn</div><div class="stat-num mt-1 text-secondary">{_fmt_vnd(cost)}</div></div></div>
  <div class="col-6 col-lg-3"><div class="card p-3 h-100"><div class="muted small">Lợi nhuận</div><div class="stat-num mt-1 text-success">{_fmt_vnd(profit)}</div></div></div>
  <div class="col-6 col-lg-3"><div class="card p-3 h-100"><div class="muted small">Đơn đã giao</div><div class="stat-num mt-1">{count}</div></div></div>
</div>

<div class="card p-4 mb-4">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h2 class="h5 mb-0">Sản phẩm &amp; kho</h2>
    <a class="btn btn-brand btn-sm" href="/admin/products">{_icon('box')} Quản lý sản phẩm</a>
  </div>
  <div class="table-responsive"><table class="table table-hover align-middle mb-0">
    <thead><tr><th>ID</th><th>Tên</th><th>Giá</th><th>Sẵn/Giữ/Bán</th><th>Trạng thái</th></tr></thead>
    <tbody>{product_rows}</tbody></table></div>
</div>

<div class="card p-4 mb-4">
  <h2 class="h5 d-flex align-items-center gap-2">{_icon('wallet')} Kết nối MBBank</h2>
  <p class="mb-2">{mb_status}</p>
  <p class="muted small">TK/MK gửi qua HTTPS và được <b>mã hoá</b> trước khi lưu. Bỏ trống Số TK để tự dò.</p>
  <form method="post" action="/admin/mbbank" autocomplete="off" class="row g-3" style="max-width:560px">
    <div class="col-12"><label class="form-label">Tên đăng nhập MBBank</label><input class="form-control" name="username" autocomplete="off" required></div>
    <div class="col-12"><label class="form-label">Mật khẩu MBBank</label><input class="form-control" name="password" type="password" autocomplete="new-password" required></div>
    <div class="col-12"><label class="form-label">Số tài khoản (tuỳ chọn)</label><input class="form-control" name="account_no"></div>
    <div class="col-12"><button class="btn btn-brand">{_icon('shield')} Lưu &amp; bật quét</button></div>
  </form>
</div>

<div class="card p-4">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h2 class="h5 mb-0">Đơn gần đây</h2>
    <a class="text-decoration-none small" href="/admin/orders">Xem tất cả →</a>
  </div>
  <div class="table-responsive"><table class="table table-hover align-middle mb-0">
    <thead><tr><th>Mã</th><th>Khách</th><th>SL</th><th>Tiền</th><th>Trạng thái</th></tr></thead>
    <tbody>{order_rows}</tbody></table></div>
</div>
"""
        return _shell(body, active="home", title="Tổng quan")

    # ---------- Products ----------

    @router.get("/products", response_class=HTMLResponse)
    async def products_page(request: Request, err: str = ""):
        if _current_admin(request) is None:
            return _unauthorized()
        async with async_session() as session:
            products = await repo.list_products(session, only_active=False)
            rows, options = [], []
            for p in products:
                is_upg = p.kind == models.KIND_UPGRADE
                s = await repo.stock_summary(session, p.id)
                stock_cell = "<span class='muted'>—</span>" if is_upg else f"{s[models.AVAILABLE]} / {s[models.RESERVED]} / {s[models.SOLD]}"
                stock_btn = (
                    "" if is_upg else
                    f"<a class='btn btn-sm btn-outline-secondary' href='/admin/products/{p.id}/stock'>{_icon('box',15)} Kho</a>"
                )
                rows.append(
                    f"<tr><td class='muted'>#{p.id}</td>"
                    f"<td class='fw-medium'>{html.escape(p.name)} {_kind_badge(p.kind)}</td>"
                    f"<td>{_fmt_vnd(p.price)}</td>"
                    f"<td>{stock_cell}</td>"
                    f"<td>{_onoff_badge(p.is_active)}</td>"
                    f"<td><div class='d-flex flex-wrap gap-1'>"
                    f"{stock_btn}"
                    f"<a class='btn btn-sm btn-outline-secondary' href='/admin/products/{p.id}/edit'>{_icon('edit',15)} Sửa</a>"
                    f"<form method='post' action='/admin/products/{p.id}/toggle' class='d-inline'><button class='btn btn-sm btn-outline-secondary'>{_icon('toggle',15)}</button></form>"
                    f"<form method='post' action='/admin/products/{p.id}/delete' class='d-inline' onsubmit=\"return confirm('Xoá sản phẩm #{p.id}?')\"><button class='btn btn-sm btn-outline-danger'>{_icon('trash',15)}</button></form>"
                    f"</div></td></tr>"
                )
                options.append(f"<option value='{p.id}'>#{p.id} — {html.escape(p.name)}</option>")
        product_rows = "".join(rows) or "<tr><td colspan='6' class='muted'>Chưa có sản phẩm</td></tr>"
        option_html = "".join(options)
        alert = ""
        if err == "has_orders":
            alert = "<div class='alert alert-warning'>Không thể xoá sản phẩm đã có đơn hàng. Hãy dùng <b>Ẩn</b> thay thế.</div>"

        body = f"""
<h1 class="h3 mb-4">Sản phẩm</h1>
{alert}
<div class="card p-4 mb-4">
  <div class="table-responsive"><table class="table table-hover align-middle mb-0">
    <thead><tr><th>ID</th><th>Tên</th><th>Giá</th><th>Sẵn/Giữ/Bán</th><th>Trạng thái</th><th>Thao tác</th></tr></thead>
    <tbody>{product_rows}</tbody></table></div>
</div>

<div class="row g-4">
  <div class="col-12 col-lg-6"><div class="card p-4 h-100">
    <h2 class="h5 d-flex align-items-center gap-2">{_icon('plus')} Thêm sản phẩm</h2>
    <form method="post" action="/admin/products" class="row g-3">
      <div class="col-12"><label class="form-label">Tên sản phẩm</label><input class="form-control" name="name" required></div>
      <div class="col-12"><label class="form-label">Loại sản phẩm</label>
        <select class="form-select" name="kind">{_kind_options(models.KIND_ACCOUNT)}</select>
        <div class="form-text">Nâng cấp chính chủ: khách nhập email, không dùng kho, admin xử lý tay.</div></div>
      <div class="col-12"><label class="form-label">Giá (VND)</label><input class="form-control" name="price" type="number" min="0" required></div>
      <div class="col-12"><label class="form-label">Mô tả (tuỳ chọn)</label><textarea class="form-control" name="description" rows="2"></textarea></div>
      <div class="col-12"><button class="btn btn-brand">{_icon('plus')} Thêm sản phẩm</button></div>
    </form>
  </div></div>
  <div class="col-12 col-lg-6"><div class="card p-4 h-100">
    <h2 class="h5 d-flex align-items-center gap-2">{_icon('upload')} Nạp tài khoản vào kho</h2>
    <form method="post" action="/admin/stock" class="row g-3">
      <div class="col-12"><label class="form-label">Sản phẩm</label><select class="form-select" name="product_id" required>{option_html}</select></div>
      <div class="col-12"><label class="form-label">Giá vốn mỗi TK (VND) — cả lô dùng chung</label><input class="form-control" name="cost" type="number" min="0" value="0"></div>
      <div class="col-12"><label class="form-label">Mỗi dòng 1 tài khoản</label><textarea class="form-control" name="items" rows="6" placeholder="user1@mail.com|matkhau1" required></textarea></div>
      <div class="col-12"><button class="btn btn-brand">{_icon('upload')} Nạp kho</button></div>
    </form>
  </div></div>
</div>
"""
        return _shell(body, active="products", title="Sản phẩm")

    @router.get("/products/{product_id}/edit", response_class=HTMLResponse)
    async def edit_product_form(request: Request, product_id: int):
        if _current_admin(request) is None:
            return _unauthorized()
        async with async_session() as session:
            p = await repo.get_product(session, product_id)
            summary = await repo.stock_summary(session, product_id) if p else None
        if not p:
            return _shell("<h1 class='h4'>Không tìm thấy sản phẩm</h1><a href='/admin/products'>← Danh sách</a>", active="products")
        body = f"""
<a class="text-decoration-none muted small d-inline-flex align-items-center gap-1 mb-2" href="/admin/products">{_icon('back',15)} Sản phẩm</a>
<h1 class="h3 mb-3">Sửa sản phẩm #{p.id}</h1>
<div class="card p-4" style="max-width:560px">
  <form method="post" action="/admin/products/{p.id}/edit" class="row g-3">
    <div class="col-12"><label class="form-label">Tên sản phẩm</label><input class="form-control" name="name" value="{html.escape(p.name)}" required></div>
    <div class="col-12"><label class="form-label">Loại sản phẩm</label>
      <select class="form-select" name="kind">{_kind_options(p.kind)}</select>
      <div class="form-text">Nâng cấp chính chủ: khách nhập email, không dùng kho.</div></div>
    <div class="col-12"><label class="form-label">Giá (VND)</label><input class="form-control" name="price" type="number" min="0" value="{p.price}" required></div>
    <div class="col-12"><label class="form-label">Mô tả</label><textarea class="form-control" name="description" rows="3">{html.escape(p.description or '')}</textarea></div>
    <div class="col-12"><label class="form-label">Trạng thái</label>
      <select class="form-select" name="is_active">
        <option value="1" {'selected' if p.is_active else ''}>Đang bán</option>
        <option value="0" {'selected' if not p.is_active else ''}>Ẩn</option>
      </select></div>
    <div class="col-12 d-flex align-items-center gap-3">
      <button class="btn btn-brand">{_icon('save')} Lưu thay đổi</button>
      <a href="/admin/products" class="text-decoration-none muted">Huỷ</a>
    </div>
  </form>
  <hr><p class="muted small mb-0">Kho: {summary[models.AVAILABLE]} sẵn · {summary[models.RESERVED]} giữ · {summary[models.SOLD]} đã bán</p>
</div>
"""
        return _shell(body, active="products", title="Sửa sản phẩm")

    @router.post("/products/{product_id}/edit")
    async def edit_product_save(
        request: Request, product_id: int,
        name: str = Form(...), price: int = Form(...), description: str = Form(""),
        kind: str = Form(models.KIND_ACCOUNT), is_active: str = Form("1"),
    ) -> Response:
        if _current_admin(request) is None:
            return _unauthorized()
        kind = kind if kind in _KIND_LABEL else models.KIND_ACCOUNT
        async with async_session() as session:
            await repo.update_product(
                session, product_id, name=name.strip(), price=price, description=description.strip(), kind=kind
            )
            await repo.set_product_active(session, product_id, is_active == "1")
            await session.commit()
        return RedirectResponse(url="/admin/products", status_code=303)

    @router.post("/products")
    async def add_product(
        request: Request, name: str = Form(...), price: int = Form(...),
        description: str = Form(""), kind: str = Form(models.KIND_ACCOUNT),
    ) -> Response:
        if _current_admin(request) is None:
            return _unauthorized()
        kind = kind if kind in _KIND_LABEL else models.KIND_ACCOUNT
        async with async_session() as session:
            await repo.create_product(session, name=name.strip(), price=price, description=description.strip(), kind=kind)
            await session.commit()
        return RedirectResponse(url="/admin/products", status_code=303)

    @router.post("/products/{product_id}/toggle")
    async def toggle_product(request: Request, product_id: int) -> Response:
        if _current_admin(request) is None:
            return _unauthorized()
        async with async_session() as session:
            product = await repo.get_product(session, product_id)
            if product:
                product.is_active = not product.is_active
                await session.commit()
        return RedirectResponse(url="/admin/products", status_code=303)

    @router.post("/products/{product_id}/delete")
    async def delete_product(request: Request, product_id: int) -> Response:
        if _current_admin(request) is None:
            return _unauthorized()
        async with async_session() as session:
            result = await repo.delete_product(session, product_id)
            await session.commit()
        url = "/admin/products" + ("?err=has_orders" if result == "has_orders" else "")
        return RedirectResponse(url=url, status_code=303)

    @router.post("/stock")
    async def add_stock(
        request: Request, product_id: int = Form(...), items: str = Form(...), cost: int = Form(0)
    ) -> Response:
        if _current_admin(request) is None:
            return _unauthorized()
        lines = [line.strip() for line in items.splitlines() if line.strip()]
        target = "/admin/products"
        if lines:
            async with async_session() as session:
                if await repo.get_product(session, product_id):
                    await repo.add_stock(session, product_id, lines, cost=max(0, cost))
                    await session.commit()
                    target = f"/admin/products/{product_id}/stock"
        return RedirectResponse(url=target, status_code=303)

    # ---------- Stock per product ----------

    @router.get("/products/{product_id}/stock", response_class=HTMLResponse)
    async def stock_page(request: Request, product_id: int):
        if _current_admin(request) is None:
            return _unauthorized()
        async with async_session() as session:
            product = await repo.get_product(session, product_id)
            if not product:
                return _shell("<h1 class='h4'>Không tìm thấy sản phẩm</h1><a href='/admin/products'>← Danh sách</a>", active="products")
            items = await repo.list_stock_items(session, product_id)
            summary = await repo.stock_summary(session, product_id)

        rows = "".join(
            f"<tr><td class='muted'>#{it.id}</td>"
            f"<td><form method='post' action='/admin/stock/{it.id}/edit' class='d-flex flex-wrap gap-2 align-items-center mb-0'>"
            f"<input class='form-control form-control-sm cell-input' name='payload' value=\"{html.escape(it.payload)}\">"
            f"<input class='form-control form-control-sm' style='width:8rem' name='cost' type='number' min='0' value='{it.cost}' title='Giá vốn'>"
            f"<select class='form-select form-select-sm' style='width:auto' name='status'>{_stock_status_options(it.status)}</select>"
            f"<button class='btn btn-sm btn-outline-secondary'>{_icon('save',15)} Lưu</button></form></td>"
            f"<td>{('<a class=\"text-decoration-none\" href=\"/admin/orders/'+str(it.order_id)+'\">#'+str(it.order_id)+'</a>') if it.order_id else '<span class=\"muted\">—</span>'}</td>"
            f"<td><form method='post' action='/admin/stock/{it.id}/delete' class='mb-0' onsubmit=\"return confirm('Xoá tài khoản #{it.id}?')\"><button class='btn btn-sm btn-outline-danger'>{_icon('trash',15)}</button></form></td></tr>"
            for it in items
        ) or "<tr><td colspan='4' class='muted'>Kho trống</td></tr>"

        body = f"""
<a class="text-decoration-none muted small d-inline-flex align-items-center gap-1 mb-2" href="/admin/products">{_icon('back',15)} Sản phẩm</a>
<h1 class="h3 mb-1 d-flex align-items-center gap-2">{_icon('box',22)} Kho — {html.escape(product.name)}</h1>
<p class="muted">{summary[models.AVAILABLE]} còn · {summary[models.RESERVED]} đang giữ · {summary[models.SOLD]} đã bán</p>

<div class="card p-4 mb-4">
  <div class="table-responsive"><table class="table table-hover align-middle mb-0">
    <thead><tr><th>ID</th><th>Tài khoản · giá vốn · trạng thái</th><th>Đơn</th><th></th></tr></thead>
    <tbody>{rows}</tbody></table></div>
  <p class="muted small mt-2 mb-0">Tối đa 500 mục mới nhất · đổi trạng thái về "Còn" sẽ gỡ gắn đơn.</p>
</div>

<div class="card p-4" style="max-width:620px">
  <h2 class="h5 d-flex align-items-center gap-2">{_icon('upload')} Nạp thêm tài khoản</h2>
  <form method="post" action="/admin/stock" class="row g-3">
    <input type="hidden" name="product_id" value="{product_id}">
    <div class="col-12"><label class="form-label">Giá vốn mỗi TK (VND) — cả lô dùng chung</label><input class="form-control" name="cost" type="number" min="0" value="0"></div>
    <div class="col-12"><label class="form-label">Mỗi dòng 1 tài khoản</label><textarea class="form-control" name="items" rows="5" placeholder="user1@mail.com|matkhau1" required></textarea></div>
    <div class="col-12"><button class="btn btn-brand">{_icon('upload')} Nạp kho</button></div>
  </form>
</div>
"""
        return _shell(body, active="products", title=f"Kho — {product.name}")

    @router.post("/stock/{item_id}/edit")
    async def edit_stock_item(
        request: Request, item_id: int,
        payload: str = Form(...), status: str = Form(...), cost: int = Form(0),
    ) -> Response:
        if _current_admin(request) is None:
            return _unauthorized()
        if status not in (models.AVAILABLE, models.RESERVED, models.SOLD):
            status = models.AVAILABLE
        async with async_session() as session:
            item = await repo.get_stock_item(session, item_id)
            product_id = item.product_id if item else None
            if item:
                await repo.update_stock_item(
                    session, item_id, payload=payload.strip(), status=status, cost=max(0, cost)
                )
                await session.commit()
        target = f"/admin/products/{product_id}/stock" if product_id else "/admin/products"
        return RedirectResponse(url=target, status_code=303)

    @router.post("/stock/{item_id}/delete")
    async def delete_stock_item(request: Request, item_id: int) -> Response:
        if _current_admin(request) is None:
            return _unauthorized()
        async with async_session() as session:
            product_id = await repo.delete_stock_item(session, item_id)
            await session.commit()
        target = f"/admin/products/{product_id}/stock" if product_id else "/admin/products"
        return RedirectResponse(url=target, status_code=303)

    @router.post("/mbbank")
    async def save_mbbank(
        request: Request, username: str = Form(...), password: str = Form(...), account_no: str = Form("")
    ) -> Response:
        if _current_admin(request) is None:
            return _unauthorized()
        async with async_session() as session:
            await mb_store.save_credentials(session, username.strip(), password, account_no.strip())
        return RedirectResponse(url="/admin", status_code=303)

    # ---------- Orders ----------

    @router.get("/orders", response_class=HTMLResponse)
    async def orders_list(request: Request, status: str = ""):
        if _current_admin(request) is None:
            return _unauthorized()
        async with async_session() as session:
            orders = await repo.list_orders(session, limit=200, status=status or None)
            products = {p.id: p.name for p in await repo.list_products(session, only_active=False)}

        rows = "".join(
            f"<tr><td><a class='text-decoration-none' href='/admin/orders/{o.id}'>{html.escape(o.code)}</a></td>"
            f"<td>{html.escape(products.get(o.product_id, '#'+str(o.product_id)))}</td>"
            f"<td>{html.escape('@'+o.buyer_username) if o.buyer_username else o.buyer_tg_id}</td>"
            f"<td>{o.quantity}</td><td>{_fmt_vnd(o.total_amount)}</td>"
            f"<td>{_status_badge(o.status)}</td><td class='muted small'>{_fmt_dt(o.created_at)}</td></tr>"
            for o in orders
        ) or "<tr><td colspan='7' class='muted'>Không có đơn</td></tr>"

        def chip(s, label):
            active = status == s
            cls = "btn btn-sm btn-brand" if active else "btn btn-sm btn-outline-secondary"
            href = "/admin/orders" + (f"?status={s}" if s else "")
            return f"<a class='{cls}' href='{href}'>{label}</a>"
        filters = "".join([
            chip("", "Tất cả"), chip(models.PENDING, "Chờ TT"),
            chip(models.AWAITING_UPGRADE, "Chờ nâng cấp"), chip(models.DELIVERED, "Đã giao"),
            chip(models.EXPIRED, "Hết hạn"), chip(models.FAILED, "Lỗi"),
        ])

        body = f"""
<h1 class="h3 mb-3">Lịch sử đơn hàng</h1>
<div class="d-flex flex-wrap gap-2 mb-3">{filters}</div>
<div class="card p-4">
  <div class="table-responsive"><table class="table table-hover align-middle mb-0">
    <thead><tr><th>Mã</th><th>Sản phẩm</th><th>Khách</th><th>SL</th><th>Tiền</th><th>TT</th><th>Tạo lúc</th></tr></thead>
    <tbody>{rows}</tbody></table></div>
  <p class="muted small mt-2 mb-0">Tối đa 200 đơn mới nhất.</p>
</div>
"""
        return _shell(body, active="orders", title="Đơn hàng")

    @router.get("/orders/{order_id}", response_class=HTMLResponse)
    async def order_detail(request: Request, order_id: int):
        if _current_admin(request) is None:
            return _unauthorized()
        async with async_session() as session:
            order = await repo.get_order(session, order_id)
            if not order:
                return _shell("<h1 class='h4'>Không tìm thấy đơn</h1><a href='/admin/orders'>← Danh sách</a>", active="orders")
            product = await repo.get_product(session, order.product_id)
            items = await repo.get_order_items(session, order_id)

        is_upgrade = bool(product) and product.kind == models.KIND_UPGRADE
        buyer = f"@{order.buyer_username}" if order.buyer_username else str(order.buyer_tg_id)
        order_cost = (order.cost or 0) if is_upgrade else sum(it.cost or 0 for it in items)
        order_profit = order.total_amount - order_cost
        pcls = "text-success" if order_profit >= 0 else "text-danger"

        email_row = (
            f"<div class='col-md-6'><span class='muted'>Email nâng cấp:</span> <code>{html.escape(order.buyer_email or '—')}</code></div>"
            if is_upgrade else ""
        )

        if is_upgrade:
            if order.status == models.AWAITING_UPGRADE:
                btn_label = f"{_icon('save')} Hoàn tất nâng cấp"
                hint = "Nhập <b>giá vốn</b> bạn bỏ ra cho lần nâng cấp này rồi bấm hoàn tất để chuyển đơn sang <b>đã giao</b>."
            else:
                btn_label = f"{_icon('save')} Lưu giá vốn"
                hint = "Cập nhật <b>giá vốn</b> của đơn nâng cấp này (dùng để tính lợi nhuận)."
            fulfil = f"""
<div class="card p-4">
  <h2 class="h5 mb-2 d-flex align-items-center gap-2">{_icon('shield')} Nâng cấp chính chủ</h2>
  <p class="mb-1"><span class="muted">Email khách:</span> <code>{html.escape(order.buyer_email or '—')}</code></p>
  <p class="muted small mb-3">{hint}</p>
  <form method="post" action="/admin/orders/{order.id}/complete-upgrade" class="row g-3" style="max-width:420px">
    <div class="col-12"><label class="form-label">Giá vốn (VND)</label>
      <input class="form-control" name="cost" type="number" min="0" value="{order.cost or 0}"></div>
    <div class="col-12"><button class="btn btn-brand">{btn_label}</button></div>
  </form>
</div>
"""
        else:
            item_rows = "".join(
                f"<tr><td class='muted'>#{it.id}</td><td><code>{html.escape(it.payload)}</code></td>"
                f"<td class='muted'>{_fmt_vnd(it.cost or 0)}</td><td>{it.status}</td></tr>"
                for it in items
            ) or "<tr><td colspan='4' class='muted'>Chưa cấp phát tài khoản</td></tr>"
            fulfil = f"""
<div class="card p-4">
  <h2 class="h5 mb-3">Tài khoản trong đơn</h2>
  <div class="table-responsive"><table class="table table-hover align-middle mb-0">
    <thead><tr><th>ID</th><th>Tài khoản</th><th>Giá vốn</th><th>TT</th></tr></thead>
    <tbody>{item_rows}</tbody></table></div>
</div>
"""

        body = f"""
<a class="text-decoration-none muted small d-inline-flex align-items-center gap-1 mb-2" href="/admin/orders">{_icon('back',15)} Danh sách đơn</a>
<h1 class="h3 mb-3">Đơn {html.escape(order.code)} {_status_badge(order.status)}</h1>
<div class="card p-4 mb-4">
  <div class="row g-2 small">
    <div class="col-md-6"><span class="muted">Sản phẩm:</span> <b>{html.escape(product.name) if product else '#'+str(order.product_id)}</b> {_kind_badge(product.kind) if product else ''}</div>
    <div class="col-md-6"><span class="muted">Khách:</span> {html.escape(buyer)} (id {order.buyer_tg_id})</div>
    {email_row}
    <div class="col-md-6"><span class="muted">Số lượng:</span> {order.quantity}</div>
    <div class="col-md-6"><span class="muted">Tổng tiền:</span> <b>{_fmt_vnd(order.total_amount)}</b></div>
    <div class="col-md-6"><span class="muted">Giá vốn:</span> {_fmt_vnd(order_cost)}</div>
    <div class="col-md-6"><span class="muted">Lợi nhuận:</span> <b class="{pcls}">{_fmt_vnd(order_profit)}</b></div>
    <div class="col-md-6"><span class="muted">Mã giao dịch:</span> <code>{html.escape(order.payment_tx_id or '—')}</code></div>
    <div class="col-12 muted">Tạo: {_fmt_dt(order.created_at)} · TT: {_fmt_dt(order.paid_at)} · Hết hạn: {_fmt_dt(order.expires_at)}</div>
  </div>
</div>
{fulfil}
"""
        return _shell(body, active="orders", title=f"Đơn {order.code}")

    @router.post("/orders/{order_id}/complete-upgrade")
    async def complete_upgrade(request: Request, order_id: int, cost: int = Form(0)) -> Response:
        if _current_admin(request) is None:
            return _unauthorized()
        cost = max(0, cost)
        notify = None
        async with async_session() as session:
            order = await repo.get_order(session, order_id)
            if order and order.status == models.AWAITING_UPGRADE:
                await repo.complete_upgrade(session, order, cost=cost)
                await session.commit()
                notify = (order.buyer_tg_id, order.code, order.buyer_email)
            elif order:  # đã giao -> chỉ cập nhật giá vốn
                await repo.set_order_cost(session, order, cost)
                await session.commit()
        if notify and bot is not None:
            tg_id, code, email = notify
            try:
                await bot.send_message(
                    tg_id,
                    f"🎉 Đơn <code>{code}</code> đã <b>nâng cấp xong</b> cho email "
                    f"<code>{html.escape(email or '')}</code>. Cảm ơn bạn đã mua hàng!",
                )
            except TelegramAPIError as exc:
                logger.error("Báo khách hoàn tất nâng cấp đơn %s thất bại: %s", code, exc)
        return RedirectResponse(url=f"/admin/orders/{order_id}", status_code=303)

    # ---------- Sold ----------

    @router.get("/sold", response_class=HTMLResponse)
    async def sold_list(request: Request):
        if _current_admin(request) is None:
            return _unauthorized()
        async with async_session() as session:
            rows_data = await repo.list_sold_items(session, limit=300)

        def _row(item, order, prod):
            unit_sale = order.total_amount // order.quantity if order.quantity else 0
            unit_profit = unit_sale - (item.cost or 0)
            pcls = "text-success" if unit_profit >= 0 else "text-danger"
            return (
                f"<tr><td class='fw-medium'>{html.escape(prod.name)}</td>"
                f"<td><code>{html.escape(item.payload)}</code></td>"
                f"<td><a class='text-decoration-none' href='/admin/orders/{order.id}'>{html.escape(order.code)}</a></td>"
                f"<td>{_fmt_vnd(unit_sale)}</td>"
                f"<td class='muted'>{_fmt_vnd(item.cost or 0)}</td>"
                f"<td class='{pcls} fw-medium'>{_fmt_vnd(unit_profit)}</td>"
                f"<td class='muted small'>{_fmt_dt(order.paid_at)}</td></tr>"
            )
        rows = "".join(_row(*r) for r in rows_data) or "<tr><td colspan='7' class='muted'>Chưa bán tài khoản nào</td></tr>"

        body = f"""
<h1 class="h3 mb-3 d-flex align-items-center gap-2">{_icon('cart',22)} Tài khoản đã bán</h1>
<div class="card p-4">
  <div class="table-responsive"><table class="table table-hover align-middle mb-0">
    <thead><tr><th>Sản phẩm</th><th>Tài khoản đã giao</th><th>Đơn</th><th>Giá bán</th><th>Giá vốn</th><th>Lợi nhuận</th><th>Bán lúc</th></tr></thead>
    <tbody>{rows}</tbody></table></div>
  <p class="muted small mt-2 mb-0">Tối đa 300 mục mới nhất. Giá bán = tiền đơn ÷ số lượng.</p>
</div>
"""
        return _shell(body, active="sold", title="Đã bán")

    return router

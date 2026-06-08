from __future__ import annotations

import logging

from aiogram import Bot
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)


def create_app(bot: Bot) -> FastAPI:
    app = FastAPI(title="NCP Store + Admin")

    from webhook.admin import create_admin_router

    app.include_router(create_admin_router(bot))

    @app.get("/", response_class=HTMLResponse)
    async def home() -> str:
        return """<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NCP Store</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;800&display=swap" rel="stylesheet">
<style>
 body{min-height:100vh;display:grid;place-items:center;font-family:'Manrope',system-ui,sans-serif;padding:24px;
   background:radial-gradient(900px 540px at 100% -8%,rgba(14,159,110,.18),transparent 60%),
              radial-gradient(680px 460px at -8% 6%,rgba(14,159,110,.12),transparent 55%),#0c1b15;color:#eafaf3}
 .glass{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:24px;
   padding:54px 40px;max-width:480px;text-align:center;backdrop-filter:blur(10px)}
 .mark{width:64px;height:64px;border-radius:18px;display:grid;place-items:center;margin:0 auto 18px;
   background:linear-gradient(135deg,#0e9f6e,#1ec98e);box-shadow:0 14px 30px -10px rgba(14,159,110,.7)}
 h1{font-family:'Manrope',sans-serif;font-weight:800;letter-spacing:-.02em}
 .muted{color:rgba(234,250,243,.7)}
</style></head>
<body><div class="glass">
 <div class="mark">
   <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
   <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/></svg>
 </div>
 <h1 class="mb-2">Xin chào!</h1>
 <p class="muted mb-0 fs-5">Chào mừng bạn đến với cửa hàng tài khoản digital.<br>Hệ thống đang hoạt động bình thường.</p>
</div></body></html>"""

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app

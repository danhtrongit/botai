from __future__ import annotations

import re
from urllib.parse import urlencode

from bot.config import get_settings

# Mã đơn dạng BOT + chữ/số (không dấu, không khoảng trắng) để không bị cắt khi qua nội dung CK.
ORDER_CODE_PREFIX = "BOT"
ORDER_CODE_RE = re.compile(rf"{ORDER_CODE_PREFIX}[A-Z0-9]+")

# VietQR.io: ảnh QR miễn phí, không phụ thuộc SePay.
VIETQR_TEMPLATE = "compact2"


def build_order_code(order_id: int) -> str:
    """Hệ thống tự sinh mã đơn duy nhất từ order_id."""
    return f"{ORDER_CODE_PREFIX}{order_id:06d}"


def build_qr_url(amount: int, code: str) -> str:
    """Sinh URL ảnh QR VietQR kèm số tiền + nội dung là mã đơn."""
    settings = get_settings()
    base = f"https://img.vietqr.io/image/{settings.bank_code}-{settings.bank_account}-{VIETQR_TEMPLATE}.png"
    params = {"amount": amount, "addInfo": code}
    if settings.bank_account_name:
        params["accountName"] = settings.bank_account_name
    return f"{base}?{urlencode(params)}"


def extract_order_code(*fields: str | None) -> str | None:
    """Tìm mã đơn (BOT......) trong các field (vd description) của webhook. Trả mã viết hoa."""
    for field in fields:
        if not field:
            continue
        match = ORDER_CODE_RE.search(field.upper())
        if match:
            return match.group(0)
    return None

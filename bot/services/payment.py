from __future__ import annotations

import hashlib
import secrets
from urllib.parse import urlencode

from bot.config import get_settings

# Bảng ký tự sinh mã đơn: chữ HOA + số, BỎ các ký tự dễ nhầm (0/O, 1/I) để khách đọc/gõ
# nội dung chuyển khoản không bị sai.
ORDER_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ORDER_CODE_LENGTH = 10

# Lời nhắn thân thiện ghép trước mã đơn cho nội dung CK trông tự nhiên (không dấu để
# tránh ngân hàng bỏ dấu). Chỉ mang tính trang trí — mã đơn vẫn nằm trong nội dung nên
# đối soát không đổi.
ORDER_NOTE_PREFIXES = (
    "gui cafe",
    "gui uong nuoc",
    "gui ly tra sua",
    "gui ban cafe",
    "ung ho cafe",
    "gui chut cafe",
    "cam on shop",
    "gui banh mi",
)

# VietQR.io: ảnh QR miễn phí, không phụ thuộc SePay.
VIETQR_TEMPLATE = "compact2"


def generate_order_code(length: int = ORDER_CODE_LENGTH) -> str:
    """Sinh mã đơn ngẫu nhiên (chữ HOA + số, bỏ ký tự dễ nhầm).

    Mã không theo thứ tự id nên không lộ số lượng đơn; tính duy nhất được đảm bảo ở
    tầng tạo đơn (orders.create_order) bằng cách thử lại nếu trùng.
    """
    return "".join(secrets.choice(ORDER_CODE_ALPHABET) for _ in range(length))


def order_note(code: str) -> str:
    """Nội dung chuyển khoản thân thiện: "<lời nhắn> <mã đơn>" (vd "gui cafe K7QXM4P9RT").

    Lời nhắn chọn ổn định theo mã (cùng mã -> cùng lời nhắn) để QR và tin nhắn hướng dẫn
    luôn trùng nhau, giúp admin dễ tra cứu khi đối chiếu sao kê thủ công.
    """
    digest = int(hashlib.md5(code.encode("utf-8")).hexdigest(), 16)
    prefix = ORDER_NOTE_PREFIXES[digest % len(ORDER_NOTE_PREFIXES)]
    return f"{prefix} {code}"


def build_qr_url(amount: int, code: str) -> str:
    """Sinh URL ảnh QR VietQR kèm số tiền + nội dung là lời nhắn thân thiện + mã đơn."""
    settings = get_settings()
    base = f"https://img.vietqr.io/image/{settings.bank_code}-{settings.bank_account}-{VIETQR_TEMPLATE}.png"
    params = {"amount": amount, "addInfo": order_note(code)}
    if settings.bank_account_name:
        params["accountName"] = settings.bank_account_name
    return f"{base}?{urlencode(params)}"

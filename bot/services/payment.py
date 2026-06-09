from __future__ import annotations

import re
import secrets
from urllib.parse import urlencode

from bot.config import get_settings

# Bảng ký tự sinh mã đơn: chữ HOA + số, BỎ các ký tự dễ nhầm (0/O, 1/I) để khách đọc/gõ
# nội dung chuyển khoản không bị sai.
ORDER_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ORDER_CODE_LENGTH = 10

# Mọi ký tự không phải chữ/số đều bị loại khi chuẩn hoá (dùng để "nối lại" chuỗi bị tách).
_NON_ALNUM_RE = re.compile(r"[^A-Z0-9]")

# VietQR.io: ảnh QR miễn phí, không phụ thuộc SePay.
VIETQR_TEMPLATE = "compact2"


def generate_order_code(length: int = ORDER_CODE_LENGTH) -> str:
    """Sinh mã đơn ngẫu nhiên (chữ HOA + số, bỏ ký tự dễ nhầm).

    Mã không theo thứ tự id nên không lộ số lượng đơn; tính duy nhất được đảm bảo ở
    tầng tạo đơn (orders.create_order) bằng cách thử lại nếu trùng.
    """
    return "".join(secrets.choice(ORDER_CODE_ALPHABET) for _ in range(length))


def normalize_ref(text: str | None) -> str:
    """Chuẩn hoá nội dung chuyển khoản: viết HOA + bỏ mọi ký tự không phải chữ/số.

    Đây là bước "tự nối ký tự": nhiều ngân hàng tự chèn khoảng trắng/dấu vào nội dung
    (vd "MDKLNC11CC" -> "MDKL NC11CC"), nên ta gộp lại trước khi so khớp mã đơn.
    """
    return _NON_ALNUM_RE.sub("", (text or "").upper())


def build_qr_url(amount: int, code: str) -> str:
    """Sinh URL ảnh QR VietQR kèm số tiền + nội dung là mã đơn."""
    settings = get_settings()
    base = f"https://img.vietqr.io/image/{settings.bank_code}-{settings.bank_account}-{VIETQR_TEMPLATE}.png"
    params = {"amount": amount, "addInfo": code}
    if settings.bank_account_name:
        params["accountName"] = settings.bank_account_name
    return f"{base}?{urlencode(params)}"


def match_order_code(candidate_codes, *fields: str | None) -> str | None:
    """Tìm mã đơn khớp trong nội dung giao dịch, chịu được việc bị tách ký tự.

    Gộp tất cả field về một chuỗi đã chuẩn hoá rồi kiểm tra từng mã đơn ứng viên có
    phải chuỗi con không. So khớp theo chuỗi con để bắt được trường hợp mã bị tách ở
    bất kỳ vị trí nào. Trả về mã khớp đầu tiên, hoặc None.
    """
    haystack = "".join(normalize_ref(f) for f in fields)
    if not haystack:
        return None
    for code in candidate_codes:
        norm = normalize_ref(code)
        if norm and norm in haystack:
            return code
    return None

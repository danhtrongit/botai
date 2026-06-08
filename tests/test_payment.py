from __future__ import annotations

from bot.services import payment


def test_build_order_code():
    assert payment.build_order_code(1) == "BOT000001"
    assert payment.build_order_code(123456) == "BOT123456"


def test_build_qr_url_vietqr():
    url = payment.build_qr_url(100000, "BOT000007")
    assert url.startswith("https://img.vietqr.io/image/MB-0123456789-")
    assert "amount=100000" in url
    assert "addInfo=BOT000007" in url


def test_extract_order_code_from_description():
    assert payment.extract_order_code("BOT000007 chuyen tien") == "BOT000007"
    assert payment.extract_order_code("NGUYEN VAN A ck bot000042 ne") == "BOT000042"


def test_extract_order_code_none_when_missing():
    assert payment.extract_order_code("chuyen tien khong co ma") is None
    assert payment.extract_order_code(None) is None

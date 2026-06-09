from __future__ import annotations

from bot.services import payment


def test_generate_order_code_format():
    code = payment.generate_order_code()
    assert len(code) == payment.ORDER_CODE_LENGTH
    assert all(c in payment.ORDER_CODE_ALPHABET for c in code)
    # Không chứa ký tự dễ nhầm.
    assert not (set("01OI") & set(code))


def test_generate_order_code_custom_length_and_random():
    assert len(payment.generate_order_code(14)) == 14
    # Hai lần sinh gần như chắc chắn khác nhau.
    assert payment.generate_order_code() != payment.generate_order_code()


def test_build_qr_url_vietqr():
    url = payment.build_qr_url(100000, "K7QXM4P9RT")
    assert url.startswith("https://img.vietqr.io/image/MB-0123456789-")
    assert "amount=100000" in url
    assert "addInfo=K7QXM4P9RT" in url


def test_normalize_ref_joins_split_chars():
    # Ngân hàng tự tách: "MDKLNC11CC" -> "MDKL NC11CC".
    assert payment.normalize_ref("MDKL NC11CC") == "MDKLNC11CC"
    assert payment.normalize_ref("mdkl-nc11cc") == "MDKLNC11CC"
    assert payment.normalize_ref("  k7qx m4p9 rt ") == "K7QXM4P9RT"
    assert payment.normalize_ref(None) == ""


def test_match_order_code_tolerates_splitting():
    codes = ["K7QXM4P9RT", "ABCD234XYZ"]
    # Mã bị chèn khoảng trắng vẫn khớp.
    assert payment.match_order_code(codes, "NGUYEN VAN A K7QX M4P9RT chuyen tien") == "K7QXM4P9RT"
    # Mã nằm trong addDescription.
    assert payment.match_order_code(codes, "ck", "ma ABCD 234 XYZ") == "ABCD234XYZ"


def test_match_order_code_none_when_missing():
    codes = ["K7QXM4P9RT"]
    assert payment.match_order_code(codes, "chuyen tien khong co ma") is None
    assert payment.match_order_code(codes, None) is None
    assert payment.match_order_code([], "K7QXM4P9RT") is None


def test_match_order_code_still_matches_legacy_bot_codes():
    # Đơn cũ dạng BOT000042 vẫn nhận diện được.
    assert payment.match_order_code(["BOT000042"], "ck bot000042 ne") == "BOT000042"

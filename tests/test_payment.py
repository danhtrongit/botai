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
    # addInfo = lời nhắn + mã (mã vẫn xuất hiện nguyên vẹn trong nội dung).
    assert "K7QXM4P9RT" in url
    assert "addInfo=" in url


def test_order_note_friendly_and_stable():
    code = "K7QXM4P9RT"
    note = payment.order_note(code)
    # Có chứa mã đơn nguyên vẹn.
    assert code in note
    # Bắt đầu bằng một lời nhắn trong danh sách.
    assert any(note.startswith(p + " ") for p in payment.ORDER_NOTE_PREFIXES)
    # Ổn định: cùng mã -> cùng lời nhắn.
    assert payment.order_note(code) == note

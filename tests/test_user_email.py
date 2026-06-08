from __future__ import annotations

from bot.handlers.user import valid_email


def test_valid_email_accepts_common_forms():
    assert valid_email("a@b.com")
    assert valid_email("user.name+tag@mail.co.uk")
    assert valid_email("  spaced@mail.com  ")  # tự trim


def test_valid_email_rejects_bad_forms():
    assert not valid_email("nope")
    assert not valid_email("a@b")          # thiếu TLD
    assert not valid_email("a b@mail.com")  # có khoảng trắng
    assert not valid_email("@mail.com")
    assert not valid_email("")
    assert not valid_email(None)  # type: ignore[arg-type]

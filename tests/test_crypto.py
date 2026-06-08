from __future__ import annotations

from bot.services import crypto


def test_encrypt_decrypt_roundtrip():
    secret = "my-mbbank-password-123"
    token = crypto.encrypt(secret)
    assert token != secret  # đã mã hoá, không phải plaintext
    assert crypto.decrypt(token) == secret


def test_ciphertext_differs_each_time():
    a = crypto.encrypt("same")
    b = crypto.encrypt("same")
    assert a != b  # Fernet có IV ngẫu nhiên
    assert crypto.decrypt(a) == crypto.decrypt(b) == "same"

from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from bot.config import get_settings

# Link đăng nhập (gửi qua bot) sống ngắn; cookie phiên sau khi đăng nhập sống dài hơn.
LOGIN_LINK_MAX_AGE = 3600  # 1 giờ
COOKIE_MAX_AGE = 7 * 24 * 3600  # 7 ngày
COOKIE_NAME = "admin_session"
_SALT = "admin-session"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().web_secret, salt=_SALT)


def make_token(admin_id: int) -> str:
    return _serializer().dumps({"admin_id": admin_id})


def verify_token(token: str, max_age: int) -> int | None:
    """Trả admin_id nếu token hợp lệ & chưa hết hạn, đồng thời còn nằm trong ADMIN_IDS."""
    try:
        data = _serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired, Exception):  # noqa: BLE001
        return None
    admin_id = data.get("admin_id") if isinstance(data, dict) else None
    if admin_id is None or not get_settings().is_admin(admin_id):
        return None
    return admin_id

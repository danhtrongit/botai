from __future__ import annotations

import asyncio

"""Tín hiệu đánh thức bộ quét MBBank khi có đơn mới.

Tách riêng để `orders` và `mbbank_poll` cùng dùng mà không vòng import. Khi có đơn pending
mới, `signal_new_order()` set event; poller đang ngủ sẽ thức dậy đăng nhập & quét. Lúc không có
đơn nào, poller ngủ trên event này nên không gọi MBBank (giảm rủi ro khoá tài khoản)."""

# Event tạo ở mức module: từ Python 3.10 không còn gắn loop lúc khởi tạo nên an toàn.
_wake = asyncio.Event()


def signal_new_order() -> None:
    """Báo cho poller biết vừa có đơn pending mới -> nên quét MBBank."""
    _wake.set()


async def wait_for_order() -> None:
    """Ngủ tới khi có đơn mới. Trả về ngay nếu cờ đã được set từ trước."""
    await _wake.wait()
    _wake.clear()


async def wait_or_timeout(timeout: float) -> bool:
    """Ngủ tối đa `timeout` giây, thức sớm nếu có đơn mới. Trả True nếu bị đánh thức."""
    try:
        await asyncio.wait_for(_wake.wait(), timeout=timeout)
        _wake.clear()
        return True
    except asyncio.TimeoutError:
        return False

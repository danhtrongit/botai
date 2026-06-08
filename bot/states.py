from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class BuyFlow(StatesGroup):
    choosing_product = State()
    choosing_quantity = State()
    entering_email = State()  # SP nâng cấp chính chủ: nhập email khách
    awaiting_payment = State()

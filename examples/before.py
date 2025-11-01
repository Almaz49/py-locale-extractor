# handlers/proxy_handlers.py

import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from aiogram.types import (CallbackQuery, Message)


from data_base.telegram_bot_logic import *
from filters.filters import StatusFilter
from FSMs.FSMs import (FSMTextMailing)
from keyboards.keyboards import (return_to_main_menu_markup)
from services.services import (send_notification_to_followers)
from utils import log_handler_call

# Настройка логирования
logger = logging.getLogger(__name__)


# Инициализируем роутер уровня модуля
router = Router()
router.message.filter(StatusFilter(required_status=["proxy"]))
router.callback_query.filter(StatusFilter(required_status=["proxy"]))

@router.callback_query(StateFilter(default_state), F.data == "mailing_followers")
@log_handler_call
async def mailing_list_start_proxy(callback: CallbackQuery, state: FSMContext, data:dict) -> None:
    """
    Хендлер нажатия кнопки "Рассылка" для представителя
    """
    if not callback.message: return
    await callback.answer()
    await callback.message.answer(text="Введите текст рассылки:", reply_markup=return_to_main_menu_markup)
    await state.set_state(FSMTextMailing.fill_text)

@router.message(F.text, FSMTextMailing.fill_text)
@log_handler_call
async def fill_mailing_text_for_followers(message: Message, state: FSMContext, data: dict):
    """
    Хэндлер для отправки текста рассылки
    """
    if not message.text:
        await message.answer("Текст не может быть пустым. Попробуйте ещё раз:")
        return
    if len(message.text) > 4000:
        await message.answer(
            text = "Сообщение слишком длинное (макс. 4000 символов). попробуйте снова",
            reply_markup=return_to_main_menu_markup)
        return
    message_text = message.text
    bot = message.bot
    proxy = data.get("member_id")
    if not bot:
        raise ValueError("Бот не найден")
    if not proxy: raise ValueError("Пользователь не найден")
    club_id = data["club_id"]
    text = await send_notification_to_followers(bot, club_id, message_text, proxy)

    await message.answer(text=text, reply_markup=return_to_main_menu_markup)
    await state.clear()

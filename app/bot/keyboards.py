"""Reply keyboards used by the upload workflow."""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

upload_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Upload Excel")],
    ],
    resize_keyboard=True,
)

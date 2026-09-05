from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="🛒 خرید اشتراک جدید")],
        [KeyboardButton(text="🎁 دریافت تست رایگان")],
        [KeyboardButton(text="📦 سرویس‌های من"), KeyboardButton(text="💰 کیف پول و شارژ")],
        [KeyboardButton(text="💼 پنل نمایندگی (همکاری)")],
        [KeyboardButton(text="🎧 پشتیبانی"), KeyboardButton(text="📜 قوانین و راهنما")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

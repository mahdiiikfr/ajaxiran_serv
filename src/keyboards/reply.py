from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="🎁 تست سرویس عادی (تانل/مستقیم)"), KeyboardButton(text="🎁 تست سرویس گیمینگ")],
        [KeyboardButton(text="🛒 خرید اشتراک عادی (تانل/مستقیم)"), KeyboardButton(text="🎮 خرید اشتراک گیمینگ")],
        [KeyboardButton(text="💼 خرید و مدیریت پنل نمایندگی")],
        [KeyboardButton(text="💰 کیف پول / شارژ"), KeyboardButton(text="📦 سرویس‌های من")],
        [KeyboardButton(text="🎧 پشتیبانی و قوانین")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

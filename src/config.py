import os
from typing import List

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
ADMIN_IDS: List[int] = [int(x) for x in os.getenv("ADMIN_IDS", "123456789").split(",")]

# PasarGuard API configuration
PASARGUARD_BASE_URL = os.getenv("PASARGUARD_BASE_URL", "https://lemina.digistoretg.ir:8000")
PASARGUARD_USERNAME = os.getenv("PASARGUARD_USERNAME", "admin")
PASARGUARD_PASSWORD = os.getenv("PASARGUARD_PASSWORD", "password")

# Groups configuration for PasarGuard
PASARGUARD_GROUP_NORMAL = "همه"
PASARGUARD_GROUP_GAMING = "برای پایداری کانفیگ این تیک را نزنید."

# Payment config
CARD_NUMBER = os.getenv("CARD_NUMBER", "5022291572821799")
CARD_HOLDER = os.getenv("CARD_HOLDER", "م.م")

ZARINPAL_MERCHANT_ID = os.getenv("ZARINPAL_MERCHANT_ID", "YOUR_MERCHANT_ID")
CALLBACK_URL = os.getenv("CALLBACK_URL", "https://example.com/verify")

# SMS API config
SMS_API_KEY = os.getenv("SMS_API_KEY", "YOUR_SMS_API_KEY")
SMS_TEMPLATE_ID = os.getenv("SMS_TEMPLATE_ID", "100000")

# Database path
DB_PATH = "bot_database.sqlite3"

# Other
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "ajaxiran_sup")
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@AjaxIran_ir")

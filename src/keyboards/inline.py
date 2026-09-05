from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

def get_charge_methods() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🌐 پرداخت آنلاین (زرین‌پال)", callback_data="pay_zarinpal")
    builder.button(text="💳 کارت به کارت", callback_data="pay_cart")
    builder.adjust(1)
    return builder.as_markup()

def get_charge_amounts() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    amounts_toman = [50000, 100000, 200000, 500000]

    for amount in amounts_toman:
        builder.button(text=f"{amount:,} تومان", callback_data=f"charge_amount_{amount}")

    builder.button(text="مبلغ دلخواه", callback_data="charge_amount_custom")
    builder.adjust(2, 2, 1)
    return builder.as_markup()

def get_admin_receipt_approval(payment_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ تایید", callback_data=f"receipt_approve_{payment_id}")
    builder.button(text="❌ رد", callback_data=f"receipt_reject_{payment_id}")
    builder.adjust(2)
    return builder.as_markup()

def get_admin_card_approval(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 ثبت و تایید کارت", callback_data=f"card_approve_{user_id}")
    builder.button(text="❌ رد", callback_data=f"card_reject_{user_id}")
    builder.adjust(2)
    return builder.as_markup()

def get_rules_acceptance() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ قوانین را می‌پذیرم", callback_data="accept_rules")
    return builder.as_markup()

def get_service_type_selection(flow_prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🌍 سرویس عادی", callback_data=f"{flow_prefix}_type_normal")
    builder.button(text="🎮 سرویس گیمینگ", callback_data=f"{flow_prefix}_type_gaming")
    builder.adjust(2)
    return builder.as_markup()

def get_vpn_packages(type_prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    packages = [10, 20, 50, 100]
    for gb in packages:
        builder.button(text=f"{gb} گیگابایت", callback_data=f"buy_vpn_{type_prefix}_{gb}")
    builder.button(text="حجم دلخواه", callback_data=f"buy_vpn_{type_prefix}_custom")
    builder.adjust(2, 2, 1)
    return builder.as_markup()

def get_panel_packages(type_prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    packages = [100, 300, 500, 1000]
    for gb in packages:
        builder.button(text=f"{gb} گیگابایت", callback_data=f"buy_panel_{type_prefix}_{gb}")
    builder.button(text="حجم دلخواه", callback_data=f"buy_panel_{type_prefix}_custom")
    builder.adjust(2, 2, 1)
    return builder.as_markup()

def get_verify_payment_button(payment_id: int, authority: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    url = f"https://payment.zarinpal.com/pg/StartPay/{authority}"
    builder.button(text="پرداخت در زرین‌پال", url=url)
    builder.button(text="بررسی وضعیت پرداخت", callback_data=f"verify_payment_{payment_id}")
    builder.adjust(1)
    return builder.as_markup()

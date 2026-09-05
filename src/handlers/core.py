import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart

from keyboards.reply import get_main_menu
from keyboards.inline import get_rules_acceptance
from database.crud import create_user, get_user, update_user_rules_accepted, get_wallet
from config import REQUIRED_CHANNEL

logger = logging.getLogger(__name__)
router = Router()

async def check_channel_membership(bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        if member.status in ['creator', 'administrator', 'member']:
            return True
    except Exception as e:
        logger.error(f"Channel Check Error: {e}")
        return True # Default to true if bot is not in channel or error
    return False

async def show_start_menu(bot, chat_id: int, user_id: int):
    # Check Channel
    if not await check_channel_membership(bot, user_id):
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.button(text="📢 عضویت در کانال", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@', '')}")
        builder.button(text="✅ عضو شدم", callback_data="check_join")
        builder.adjust(1)
        await bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ <b>جهت استفاده از ربات، ابتدا در کانال ما عضو شوید:</b>\n\n🆔 {REQUIRED_CHANNEL}",
            reply_markup=builder.as_markup()
        )
        return

    balance = await get_wallet(user_id)
    msg = (
        f"🚀 به ربات هوشمند ما خوش آمدید!\n\n"
        f"ما اینجاییم تا یک اتصال پرسرعت، امن و بدون قطعی را برای شما فراهم کنیم. 🌐\n\n"
        f"💳 موجودی فعلی شما: <code>{balance:,}</code> تومان\n\n"
        f"🎯 برای شروع، یکی از گزینه‌های منوی زیر را انتخاب کنید: 👇"
    )
    await bot.send_message(chat_id=chat_id, text=msg, reply_markup=get_main_menu())

@router.message(CommandStart())
async def start_handler(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username

    # Initialize user in DB
    await create_user(user_id, username)
    user = await get_user(user_id)

    if not user['rules_accepted']:
        rules_text = (
            "📜 <b>قوانین و مقررات استفاده از ربات</b>\n\n"
            "۱. بازگشت وجه پس از ساخت سرویس امکان‌پذیر نیست.\n"
            "۲. استفاده از سرویس‌ها برای فعالیت‌های غیرقانونی، هک، اسپم و ... ممنوع است.\n"
            "۳. حفظ اطلاعات اکانت بر عهده کاربر است.\n"
            "۴. پشتیبانی تنها برای مشکلات فنی ارائه می‌شود.\n\n"
            "لطفاً قوانین را مطالعه کرده و در صورت تایید دکمه زیر را لمس کنید."
        )
        await message.answer(rules_text, reply_markup=get_rules_acceptance())
        return

    await show_start_menu(message.bot, message.chat.id, user_id)

@router.callback_query(F.data == "accept_rules")
async def accept_rules_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    await update_user_rules_accepted(user_id, True)
    await callback.answer("✅ قوانین پذیرفته شد.", show_alert=True)
    await callback.message.delete()

    # Restart the flow
    await show_start_menu(callback.bot, callback.message.chat.id, user_id)

@router.callback_query(F.data == "check_join")
async def check_join_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    if await check_channel_membership(callback.bot, user_id):
        await callback.message.delete()
        await show_start_menu(callback.bot, callback.message.chat.id, user_id)
    else:
        await callback.answer("❌ هنوز در کانال عضو نشده‌اید!", show_alert=True)

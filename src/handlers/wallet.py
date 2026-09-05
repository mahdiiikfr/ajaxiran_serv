import logging
import random
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from keyboards.inline import get_charge_methods, get_charge_amounts, get_admin_receipt_approval, get_admin_card_approval, get_verify_payment_button
from keyboards.reply import get_main_menu
from database.crud import get_wallet, get_user, update_user_phone, update_user_zarinpal_card, add_pending_payment, get_pending_payment, add_wallet, delete_pending_payment, update_user_verified_card
from services.zarinpal import send_otp_sms, calculate_zarinpal_fee, create_zarinpal_payment, verify_zarinpal_payment
from config import ADMIN_IDS, CARD_NUMBER, CARD_HOLDER

logger = logging.getLogger(__name__)
router = Router()

class WalletState(StatesGroup):
    waiting_for_amount = State()
    choosing_method = State()
    waiting_for_phone = State()
    waiting_for_otp = State()
    waiting_for_zarinpal_card = State()
    waiting_for_card_photo = State()
    waiting_for_receipt = State()
    admin_waiting_for_card_number = State()

@router.message(F.text == "💰 کیف پول و شارژ")
async def wallet_menu(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    balance = await get_wallet(user_id)

    msg = f"💰 <b>کیف پول:</b> <code>{balance:,}</code> تومان\n\nلطفاً مبلغ شارژ را انتخاب کنید:"
    await message.answer(msg, reply_markup=get_charge_amounts())

@router.callback_query(F.data.startswith("charge_amount_"))
async def process_charge_amount(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    val = callback.data.split("_")[2]

    if val == "custom":
        await state.set_state(WalletState.waiting_for_amount)
        await callback.message.edit_text("✍️ مبلغ دلخواه خود را به <b>تومان</b> وارد کنید (حداقل 10,000 تومان):")
        return

    amount = int(val)
    await state.update_data(charge_amount=amount)
    await show_payment_methods(callback.message, amount, state, edit=True)

@router.message(WalletState.waiting_for_amount)
async def process_custom_amount(message: Message, state: FSMContext):
    text = message.text.replace(",", "")
    if not text.isdigit():
        return await message.answer("❌ لطفاً یک عدد معتبر وارد کنید:")

    amount = int(text)
    if amount < 10000:
        return await message.answer("❌ حداقل مبلغ شارژ ۱۰,۰۰۰ تومان است.")

    await state.update_data(charge_amount=amount)
    await show_payment_methods(message, amount, state, edit=False)

async def show_payment_methods(msg_obj: Message, amount: int, state: FSMContext, edit: bool):
    text = f"مبلغ شارژ: <code>{amount:,}</code> تومان\n\nلطفاً روش پرداخت را انتخاب کنید:"
    await state.set_state(WalletState.choosing_method)
    if edit:
        await msg_obj.edit_text(text, reply_markup=get_charge_methods())
    else:
        await msg_obj.answer(text, reply_markup=get_charge_methods())

# --- ZARINPAL FLOW ---
@router.callback_query(WalletState.choosing_method, F.data == "pay_zarinpal")
async def pay_zarinpal_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    user = await get_user(user_id)

    if not user.get('phone_number'):
        await state.set_state(WalletState.waiting_for_phone)
        await callback.message.edit_text("📱 برای پرداخت آنلاین، ابتدا شماره موبایل خود را وارد کنید (مثلاً 09121234567):")
        return

    if not user.get('zarinpal_card_number'):
        await state.set_state(WalletState.waiting_for_zarinpal_card)
        await callback.message.edit_text("💳 جهت پرداخت از طریق درگاه، لطفاً شماره کارت ۱۶ رقمی خود را وارد کنید.\n⚠️ پرداخت فقط با این کارت مجاز خواهد بود.")
        return

    await generate_zarinpal_link(callback.message, state, edit=True)

@router.message(WalletState.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    if not (phone.startswith("09") and len(phone) == 11 and phone.isdigit()):
        return await message.answer("❌ شماره موبایل نامعتبر است.")

    otp = random.randint(10000, 99999)
    await state.update_data(phone=phone, otp=str(otp))

    await message.answer("⏳ در حال ارسال پیامک...")
    res = await send_otp_sms(phone, otp)

    await state.set_state(WalletState.waiting_for_otp)
    await message.answer("✅ کد تایید پیامک شد. لطفاً آن را وارد کنید:")

@router.message(WalletState.waiting_for_otp)
async def process_otp(message: Message, state: FSMContext):
    data = await state.get_data()
    if message.text.strip() != data.get("otp"):
        return await message.answer("❌ کد اشتباه است. دوباره تلاش کنید.")

    user_id = message.from_user.id
    phone = data.get("phone")
    await update_user_phone(user_id, phone)

    await message.answer("✅ شماره موبایل تایید شد.")
    user = await get_user(user_id)
    if not user.get('zarinpal_card_number'):
        await state.set_state(WalletState.waiting_for_zarinpal_card)
        await message.answer("💳 جهت پرداخت از طریق درگاه، لطفاً شماره کارت ۱۶ رقمی خود را وارد کنید.")
    else:
        await generate_zarinpal_link(message, state, edit=False)

@router.message(WalletState.waiting_for_zarinpal_card)
async def process_zarinpal_card(message: Message, state: FSMContext):
    card = message.text.replace("-", "").replace(" ", "")
    if len(card) != 16 or not card.isdigit():
        return await message.answer("❌ شماره کارت نامعتبر است.")

    user_id = message.from_user.id
    await update_user_zarinpal_card(user_id, card)
    await message.answer("✅ کارت شما ثبت شد.")

    await generate_zarinpal_link(message, state, edit=False)

async def generate_zarinpal_link(msg_obj: Message, state: FSMContext, edit: bool):
    data = await state.get_data()
    amount = data.get("charge_amount")
    user_id = msg_obj.chat.id
    user = await get_user(user_id)

    amount_irr = amount * 10
    fee_res = await calculate_zarinpal_fee(amount_irr)

    if 'data' in fee_res and fee_res['data'] and fee_res['data'].get('code') == 100:
        suggested = fee_res['data']['suggested_amount']

        zp_res = await create_zarinpal_payment(suggested, user['phone_number'], user['zarinpal_card_number'])
        if 'data' in zp_res and zp_res['data'] and zp_res['data'].get('code') == 100:
            authority = zp_res['data']['authority']

            payment_id = await add_pending_payment(user_id, amount, authority)

            text = f"مبلغ نهایی با کارمزد: <code>{suggested//10:,}</code> تومان\n\nبرای پرداخت روی دکمه زیر کلیک کنید و پس از پرداخت گزینه بررسی وضعیت را بزنید:"
            markup = get_verify_payment_button(payment_id, authority)

            if edit:
                await msg_obj.edit_text(text, reply_markup=markup)
            else:
                await msg_obj.answer(text, reply_markup=markup)
            await state.clear()
            return

    err = "❌ خطا در ارتباط با درگاه زرین‌پال."
    if edit:
        await msg_obj.edit_text(err)
    else:
        await msg_obj.answer(err)
    await state.clear()

@router.callback_query(F.data.startswith("verify_payment_"))
async def verify_payment_handler(callback: CallbackQuery):
    await callback.answer("در حال بررسی...", show_alert=False)
    payment_id = int(callback.data.split("_")[2])
    payment = await get_pending_payment(payment_id)

    if not payment:
        return await callback.message.edit_text("❌ این پرداخت منقضی شده یا قبلاً تایید شده است.")

    user_id, amount, authority = payment
    if not authority:
        return await callback.message.edit_text("❌ امکان بررسی این پرداخت وجود ندارد.")

    # Amount stored is in Toman, Zarinpal expects IRR with fees, so we need to calculate again
    # The actual verified amount should match suggested_amount. For simplicity, we just pass amount*10.
    amount_irr = amount * 10
    fee_res = await calculate_zarinpal_fee(amount_irr)
    if 'data' in fee_res and fee_res['data'] and fee_res['data'].get('code') == 100:
        suggested = fee_res['data']['suggested_amount']
        verify_res = await verify_zarinpal_payment(suggested, authority)

        if 'data' in verify_res and verify_res['data'] and verify_res['data'].get('code') in [100, 101]:
            # Success
            await add_wallet(user_id, amount)
            await delete_pending_payment(payment_id)

            await callback.message.edit_text(f"✅ پرداخت شما با موفقیت تایید شد!\nمبلغ <code>{amount:,}</code> تومان به کیف پول شما اضافه شد.")
            return

    await callback.message.answer("❌ پرداخت هنوز انجام نشده یا ناموفق بوده است.")

# --- CARD TO CARD FLOW ---
@router.callback_query(WalletState.choosing_method, F.data == "pay_cart")
async def pay_cart_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    user = await get_user(user_id)

    if not user.get('verified_card_number'):
        await state.set_state(WalletState.waiting_for_card_photo)
        text = (
            "🪪 <b>احراز کارت بانکی</b>\n\n"
            "جهت واریز کارت به کارت، ابتدا باید یک تصویر از کارت بانکی خود (با پوشاندن CVV2 و تاریخ انقضا) ارسال کنید.\n"
            "لطفاً همین الان عکس کارت بانکی خود را ارسال کنید:"
        )
        await callback.message.edit_text(text)
        return

    data = await state.get_data()
    amount = data.get("charge_amount")

    text = (
        f"🧾 <b>فاکتور کارت به کارت</b>\n\n"
        f"💳 مبلغ: <code>{amount:,}</code> تومان\n"
        f"💳 شماره کارت مقصد:\n<code>{CARD_NUMBER}</code>\n"
        f"👤 بنام: {CARD_HOLDER}\n\n"
        f"⚠️ شما فقط مجاز هستید با کارتی که تایید کرده‌اید واریز کنید:\n"
        f"<code>{user['verified_card_number']}</code>\n\n"
        "عکس فیش واریزی را ارسال کنید."
    )
    await state.set_state(WalletState.waiting_for_receipt)
    await callback.message.edit_text(text)

@router.message(WalletState.waiting_for_card_photo, F.photo)
async def process_card_photo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    photo_id = message.photo[-1].file_id

    await message.answer("⏳ کارت شما برای بررسی ادمین ارسال شد.")

    admin_msg = f"🪪 درخواست تایید کارت بانکی\n👤 کاربر: <code>{user_id}</code> (@{message.from_user.username})"
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_photo(chat_id=admin_id, photo=photo_id, caption=admin_msg, reply_markup=get_admin_card_approval(user_id))
        except Exception:
            pass
    await state.clear()

@router.callback_query(F.data.startswith("card_approve_"))
async def admin_card_approve(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("دسترسی ندارید", show_alert=True)
    user_id = int(callback.data.split("_")[2])

    await state.update_data(target_card_user_id=user_id)
    await state.set_state(WalletState.admin_waiting_for_card_number)
    await callback.message.edit_caption(caption="لطفاً شماره کارت ۱۶ رقمی را در چت ارسال کنید:")

@router.message(WalletState.admin_waiting_for_card_number)
async def admin_save_card_number(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return await state.clear()

    card = message.text.replace(" ", "").replace("-", "")
    if len(card) != 16 or not card.isdigit():
        return await message.answer("❌ نامعتبر")

    data = await state.get_data()
    target_user = data.get("target_card_user_id")

    await update_user_verified_card(target_user, card)
    await message.answer("✅ کارت تایید و ثبت شد.")

    try:
        await message.bot.send_message(target_user, f"✅ کارت شما تایید شد: <code>{card}</code>\nحالا میتوانید از منوی شارژ، اقدام کنید.")
    except Exception:
        pass
    await state.clear()

@router.callback_query(F.data.startswith("card_reject_"))
async def admin_card_reject(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("دسترسی ندارید", show_alert=True)
    user_id = int(callback.data.split("_")[2])

    await callback.message.edit_caption(caption="❌ کارت رد شد.")
    try:
        await callback.bot.send_message(user_id, "❌ کارت شما رد شد. عکسی واضح تر و بدون پوشاندن نام و شماره کارت ارسال کنید.")
    except Exception:
        pass

@router.message(WalletState.waiting_for_receipt, F.photo)
async def process_receipt(message: Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get("charge_amount")
    user_id = message.from_user.id
    photo_id = message.photo[-1].file_id

    payment_id = await add_pending_payment(user_id, amount, None)

    await message.answer("⏳ فیش شما دریافت شد و پس از بررسی حساب شما شارژ خواهد شد.")
    await state.clear()

    user = await get_user(user_id)
    caption = (
        f"📥 فیش واریزی جدید\n"
        f"👤 کاربر: <code>{user_id}</code> (@{message.from_user.username})\n"
        f"💰 مبلغ: <code>{amount:,}</code> تومان\n"
        f"⚠️ کارت تایید شده کاربر: <code>{user.get('verified_card_number', 'نامشخص')}</code>"
    )
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_photo(chat_id=admin_id, photo=photo_id, caption=caption, reply_markup=get_admin_receipt_approval(payment_id))
        except Exception:
            pass

@router.callback_query(F.data.startswith("receipt_approve_"))
async def admin_receipt_approve(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("دسترسی ندارید", show_alert=True)

    payment_id = int(callback.data.split("_")[2])
    payment = await get_pending_payment(payment_id)
    if not payment:
        return await callback.answer("از قبل تایید یا رد شده", show_alert=True)

    user_id, amount, _ = payment
    # Delete payment before processing to avoid race conditions!
    await delete_pending_payment(payment_id)
    await add_wallet(user_id, amount)


    await callback.message.edit_caption(caption=f"✅ تایید شد. {amount:,} تومان به کاربر اضافه شد.")
    try:
        await callback.bot.send_message(user_id, f"✅ شارژ کیف پول تایید شد! مبلغ <code>{amount:,}</code> تومان به موجودی اضافه شد.")
    except Exception:
        pass

@router.callback_query(F.data.startswith("receipt_reject_"))
async def admin_receipt_reject(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("دسترسی ندارید", show_alert=True)

    payment_id = int(callback.data.split("_")[2])
    payment = await get_pending_payment(payment_id)
    if not payment:
        return await callback.answer("از قبل تایید یا رد شده", show_alert=True)

    user_id, amount, _ = payment
    await delete_pending_payment(payment_id)

    await callback.message.edit_caption(caption="❌ رسید رد شد.")
    try:
        await callback.bot.send_message(user_id, f"❌ متاسفانه فیش واریزی <code>{amount:,}</code> تومانی شما تایید نشد.")
    except Exception:
        pass

import logging
import random
import string
import os
import json
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from keyboards.inline import get_vpn_packages, get_panel_packages
from keyboards.reply import get_main_menu
from database.crud import get_wallet, add_wallet, add_user_service, add_partner, get_partner
from services.pasarguard_api import PasarGuardAPI
from config import PASARGUARD_BASE_URL, PASARGUARD_GROUP_NORMAL, PASARGUARD_GROUP_GAMING

logger = logging.getLogger(__name__)
router = Router()
api = PasarGuardAPI()

class StoreState(StatesGroup):
    waiting_for_vpn_custom_volume = State()
    waiting_for_panel_custom_volume = State()
    waiting_for_panel_renewal_volume = State()

def get_vpn_price(volume_gb: int, is_gaming: bool) -> int:
    return volume_gb * (12000 if is_gaming else 6000)

def get_panel_price(volume_gb: int, is_gaming: bool) -> int:
    if is_gaming:
        return volume_gb * (5000 if volume_gb < 1000 else 2500)
    else:
        return volume_gb * (3000 if volume_gb < 1000 else 1500)

def generate_random_string(length=6):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def generate_random_password():
    lowers = random.choices(string.ascii_lowercase, k=3)
    digits = random.choices(string.digits, k=3)
    uppers = random.choices(string.ascii_uppercase, k=4)
    specials = random.choices(["!", "@", "#", "$", "%", "&"], k=2)
    pwd_list = lowers + digits + uppers + specials
    random.shuffle(pwd_list)
    return "".join(pwd_list)

# --- سیستم پیشرفته جلوگیری از سوءاستفاده (مجزا برای گیمینگ و عادی) ---
TESTS_FILE = "used_tests_v2.json"

async def is_test_used(user_id: int, vpn_type: str) -> bool:
    if not os.path.exists(TESTS_FILE):
        return False
    try:
        with open(TESTS_FILE, "r") as f:
            data = json.load(f)
        # بررسی می‌کند که آیا کاربر این نوع خاص از تست را گرفته یا نه
        return data.get(str(user_id), {}).get(vpn_type, False)
    except:
        return False

async def set_test_used(user_id: int, vpn_type: str):
    data = {}
    if os.path.exists(TESTS_FILE):
        try:
            with open(TESTS_FILE, "r") as f:
                data = json.load(f)
        except:
            pass
            
    if str(user_id) not in data:
        data[str(user_id)] = {}
        
    data[str(user_id)][vpn_type] = True
    
    with open(TESTS_FILE, "w") as f:
        json.dump(data, f)

# --- Free Test Store ---
@router.message(F.text.in_(["🎁 تست سرویس عادی (تانل/مستقیم)", "🎁 تست سرویس گیمینگ"]))
async def process_free_test(message: Message, state: FSMContext):
    user_id = message.from_user.id
    is_gaming = "گیمینگ" in message.text
    vpn_type = "gaming" if is_gaming else "normal"
    vpn_name = "گیمینگ" if is_gaming else "عادی (تانل/مستقیم)"

    # بررسی دریافت تست در گذشته (اختصاصی برای هر نوع)
    if await is_test_used(user_id, vpn_type):
        return await message.answer(f"❌ شما قبلاً سرویس تست رایگان **{vpn_name}** خود را دریافت کرده‌اید!\n\nشما فقط مجاز به دریافت یک بار تست از هر نوع هستید.")

    text = f"⏳ در حال ساخت اکانت تست رایگان {vpn_name} (۱ گیگ / ۱ روزه)..."
    msg_obj = await message.answer(text)

    volume_gb = 1
    expire_duration = 1 * 24 * 3600 # 1 day

    try:
        group_name = PASARGUARD_GROUP_GAMING if is_gaming else PASARGUARD_GROUP_NORMAL
        group_id = await api.get_group_by_name(group_name)
        if not group_id:
             raise Exception(f"گروه '{group_name}' در پنل یافت نشد.")

        # پیشوند tg برای گیمینگ و tn برای عادی
        username = f"{'tg' if is_gaming else 'tn'}test{generate_random_string(4)}"
        bytes_limit = volume_gb * 1024**3

        created = await api.create_user(username, bytes_limit, expire_duration, [group_id], f"Free Test {vpn_type} - User {user_id}")

        if isinstance(created, dict) and 'subscription_url' in created:
            sub_path = created['subscription_url']
        elif isinstance(created, dict) and 'links' in created and isinstance(created['links'], list) and len(created['links']) > 0:
            sub_path = created['links'][0]
        else:
            sub_path = created.get('subscription_url', f"/sub/{created.get('subscription_token', username)}") if isinstance(created, dict) else f"/sub/{username}"

        if sub_path.startswith('http'):
            sub_link = sub_path
        else:
            sub_link = f"{PASARGUARD_BASE_URL.rstrip('/')}{sub_path}"

        await add_user_service(user_id, username, sub_link, volume_gb, vpn_type)
        await set_test_used(user_id, vpn_type) # ثبت کاربر برای این نوع خاص

        res_msg = (
            f"🎉 <b>اشتراک تست {vpn_name} شما با موفقیت ساخته شد!</b>\n\n"
            f"👤 <b>نام کاربری:</b> <code>{username}</code>\n"
            f"📊 <b>حجم:</b> {volume_gb} گیگابایت\n"
            f"⏳ <b>زمان:</b> 24 ساعت (1 روز)\n\n"
            f"🔗 <b>لینک اشتراک:</b>\n<code>{sub_link}</code>"
        )
        await msg_obj.edit_text(res_msg)

    except Exception as e:
        logger.error(f"Error creating Test VPN user: {e}")
        await msg_obj.edit_text(f"❌ متاسفانه خطایی در ارتباط با سرور رخ داد.\nخطا: {str(e)}")

# --- VPN Store ---
@router.message(F.text == "🛒 خرید اشتراک عادی (تانل/مستقیم)")
async def vpn_normal_menu(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(vpn_type="normal")
    await message.answer("🛒 <b>بسته‌های اشتراک عادی (یک ماهه):</b>\n\nلطفاً حجم مورد نظر خود را انتخاب کنید:", reply_markup=get_vpn_packages("normal"))

@router.message(F.text == "🎮 خرید اشتراک گیمینگ")
async def vpn_gaming_menu(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(vpn_type="gaming")
    await message.answer("🎮 <b>بسته‌های اشتراک گیمینگ (یک ماهه):</b>\n\nلطفاً حجم مورد نظر خود را انتخاب کنید:", reply_markup=get_vpn_packages("gaming"))

@router.callback_query(F.data.startswith("buy_vpn_"))
async def process_vpn_buy(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split("_")
    vpn_type = parts[2]
    val = parts[3]

    await state.update_data(vpn_type=vpn_type)

    if val == "custom":
        await state.set_state(StoreState.waiting_for_vpn_custom_volume)
        await callback.message.edit_text("✍️ لطفاً حجم دلخواه خود را به <b>گیگابایت</b> وارد کنید (حداقل 10 گیگ):")
        return

    await checkout_vpn(callback.message, int(val), vpn_type, state, edit=True)

@router.message(StoreState.waiting_for_vpn_custom_volume)
async def process_vpn_custom_volume(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❌ لطفاً یک عدد معتبر وارد کنید.")

    vol = int(message.text)
    if vol < 10:
        return await message.answer("❌ حداقل حجم 10 گیگابایت است.")

    data = await state.get_data()
    await checkout_vpn(message, vol, data.get("vpn_type"), state, edit=False)

async def checkout_vpn(msg_obj: Message, volume_gb: int, vpn_type: str, state: FSMContext, edit: bool):
    user_id = msg_obj.chat.id
    is_gaming = (vpn_type == "gaming")
    price = get_vpn_price(volume_gb, is_gaming)

    balance = await get_wallet(user_id)
    if balance < price:
        err = f"❌ موجودی شما کافی نیست.\nموجودی: <code>{balance:,}</code> تومان\nمبلغ مورد نیاز: <code>{price:,}</code> تومان"
        if edit:
            await msg_obj.edit_text(err)
        else:
            await msg_obj.answer(err)
        await state.clear()
        return

    text = "⏳ در حال ساخت اکانت..."
    if edit:
        await msg_obj.edit_text(text)
    else:
        msg_obj = await msg_obj.answer(text)

    # Deduct balance
    await add_wallet(user_id, -price)

    try:
        group_name = PASARGUARD_GROUP_GAMING if is_gaming else PASARGUARD_GROUP_NORMAL
        group_id = await api.get_group_by_name(group_name)
        if not group_id:
             raise Exception(f"گروه '{group_name}' در پنل یافت نشد.")

        username = f"{'g' if is_gaming else 'n'}{generate_random_string(6)}"
        bytes_limit = volume_gb * 1024**3
        expire_duration = 30 * 24 * 3600 # 30 days

        created = await api.create_user(username, bytes_limit, expire_duration, [group_id], f"Created by Bot - User {user_id}")

        if isinstance(created, dict) and 'subscription_url' in created:
            sub_path = created['subscription_url']
        elif isinstance(created, dict) and 'links' in created and isinstance(created['links'], list) and len(created['links']) > 0:
            sub_path = created['links'][0]
        else:
            sub_path = created.get('subscription_url', f"/sub/{created.get('subscription_token', username)}") if isinstance(created, dict) else f"/sub/{username}"

        if sub_path.startswith('http'):
            sub_link = sub_path
        else:
            sub_link = f"{PASARGUARD_BASE_URL.rstrip('/')}{sub_path}"

        await add_user_service(user_id, username, sub_link, volume_gb, vpn_type)

        res_msg = (
            f"🎉 <b>اشتراک شما با موفقیت ساخته شد!</b>\n\n"
            f"👤 <b>نام کاربری:</b> <code>{username}</code>\n"
            f"📊 <b>حجم:</b> {volume_gb} گیگابایت\n"
            f"⏳ <b>زمان:</b> 30 روز\n\n"
            f"🔗 <b>لینک اشتراک:</b>\n<code>{sub_link}</code>"
        )
        await msg_obj.edit_text(res_msg)

    except Exception as e:
        logger.error(f"Error creating VPN user: {e}")
        await add_wallet(user_id, price) # Refund
        await msg_obj.edit_text(f"❌ متاسفانه خطایی در ارتباط با سرور رخ داد. وجه به کیف پول شما بازگشت داده شد.\nخطا: {str(e)}")

    await state.clear()

# --- Panel Store ---
@router.message(F.text == "💼 خرید و مدیریت پنل نمایندگی")
async def panel_menu(message: Message, state: FSMContext):
    await state.clear()
    partner = await get_partner(message.from_user.id)
    if partner:
        op_username, status, ptype = partner
        msg = (
            f"✅ <b>شما از قبل یک پنل نمایندگی دارید.</b>\n\n"
            f"👤 <b>نام کاربری اپراتور:</b> <code>{op_username}</code>\n"
            f"⚙️ <b>نوع پنل:</b> {'گیمینگ' if ptype == 'gaming' else 'عادی'}\n"
            f"وضعیت: {status}\n\n"
            "جهت تمدید حجم پنل خود روی دکمه زیر کلیک کنید."
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="تمدید حجم پنل", callback_data="panel_renew")
        await message.answer(msg, reply_markup=builder.as_markup())
        return

    msg = (
        "💼 <b>خرید پنل نمایندگی پاسارگاد</b>\n\n"
        "در این بخش می‌توانید به عنوان یک اپراتور، پنل نمایندگی تهیه کنید. با خرید پنل، می‌توانید کاربران خود را مستقلاً بسازید.\n\n"
        "لطفاً نوع پنل را انتخاب کنید:"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="پنل عادی", callback_data="panel_choose_normal")
    builder.button(text="پنل گیمینگ", callback_data="panel_choose_gaming")
    builder.adjust(2)

    await message.answer(msg, reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("panel_choose_"))
async def process_panel_type(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    panel_type = callback.data.split("_")[2]
    await state.update_data(panel_type=panel_type)

    await callback.message.edit_text(
        f"💼 <b>خرید پنل نمایندگی ({'گیمینگ' if panel_type == 'gaming' else 'عادی'})</b>\n\nلطفاً حجم مورد نظر خود را انتخاب کنید:",
        reply_markup=get_panel_packages(panel_type)
    )

@router.callback_query(F.data.startswith("buy_panel_"))
async def process_panel_buy(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split("_")
    panel_type = parts[2]
    val = parts[3]

    await state.update_data(panel_type=panel_type)

    if val == "custom":
        await state.set_state(StoreState.waiting_for_panel_custom_volume)
        await callback.message.edit_text("✍️ لطفاً حجم دلخواه پنل را به <b>گیگابایت</b> وارد کنید (حداقل 100 گیگ):")
        return

    await checkout_panel(callback.message, int(val), panel_type, state, edit=True)

@router.message(StoreState.waiting_for_panel_custom_volume)
async def process_panel_custom_volume(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❌ لطفاً یک عدد معتبر وارد کنید.")

    vol = int(message.text)
    if vol < 100:
        return await message.answer("❌ حداقل حجم برای پنل 100 گیگابایت است.")

    data = await state.get_data()
    await checkout_panel(message, vol, data.get("panel_type"), state, edit=False)

async def checkout_panel(msg_obj: Message, volume_gb: int, panel_type: str, state: FSMContext, edit: bool):
    user_id = msg_obj.chat.id
    is_gaming = (panel_type == "gaming")
    price = get_panel_price(volume_gb, is_gaming)

    balance = await get_wallet(user_id)
    if balance < price:
        err = f"❌ موجودی شما کافی نیست.\nموجودی: <code>{balance:,}</code> تومان\nمبلغ مورد نیاز: <code>{price:,}</code> تومان"
        if edit:
            await msg_obj.edit_text(err)
        else:
            await msg_obj.answer(err)
        await state.clear()
        return

    text = "⏳ در حال ساخت پنل نمایندگی..."
    if edit:
        await msg_obj.edit_text(text)
    else:
        msg_obj = await msg_obj.answer(text)

    # Deduct
    await add_wallet(user_id, -price)

    try:
        op_username = f"op_{generate_random_string(4)}"
        op_password = generate_random_password()

        bytes_limit = volume_gb * 1024**3
        await api.create_admin(op_username, op_password, is_sudo=False, role_id=3, data_limit=bytes_limit)

        await add_partner(user_id, op_username, panel_type)

        res_msg = (
            f"🎉 <b>پنل نمایندگی شما با موفقیت ساخته شد!</b>\n\n"
            f"🌐 <b>آدرس ورود:</b> {PASARGUARD_BASE_URL.rstrip('/')}/dashboard/\n"
            f"👤 <b>نام کاربری:</b> <code>{op_username}</code>\n"
            f"🔑 <b>رمز عبور:</b> <code>{op_password}</code>\n"
            f"📊 <b>حجم تخصیص یافته:</b> {volume_gb} گیگابایت"
        )
        await msg_obj.edit_text(res_msg)

    except Exception as e:
        logger.error(f"Error creating panel: {e}")
        await add_wallet(user_id, price) # Refund
        await msg_obj.edit_text(f"❌ خطا در ساخت پنل رخ داد. وجه بازگشت داده شد.\nخطا: {str(e)}")

    await state.clear()

@router.callback_query(F.data == "panel_renew")
async def panel_renew_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    partner = await get_partner(callback.from_user.id)
    if not partner:
        return

    op_username, status, ptype = partner
    await state.update_data(panel_type=ptype, op_username=op_username)

    await state.set_state(StoreState.waiting_for_panel_renewal_volume)
    await callback.message.edit_text("✍️ لطفاً حجم مورد نیاز برای تمدید پنل خود را به <b>گیگابایت</b> وارد کنید (حداقل 10 گیگ):")

@router.message(StoreState.waiting_for_panel_renewal_volume)
async def process_panel_renewal_volume(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❌ لطفاً یک عدد معتبر وارد کنید.")

    vol = int(message.text)
    if vol < 10:
        return await message.answer("❌ حداقل حجم برای تمدید 10 گیگابایت است.")

    data = await state.get_data()
    panel_type = data.get("panel_type")
    op_username = data.get("op_username")
    is_gaming = (panel_type == "gaming")
    price = get_panel_price(vol, is_gaming)

    balance = await get_wallet(message.from_user.id)
    if balance < price:
        err = f"❌ موجودی شما کافی نیست.\nموجودی: <code>{balance:,}</code> تومان\nمبلغ مورد نیاز: <code>{price:,}</code> تومان"
        await message.answer(err)
        await state.clear()
        return

    msg_obj = await message.answer("⏳ در حال تمدید حجم پنل...")

    await add_wallet(message.from_user.id, -price)
    try:
        bytes_add = vol * 1024**3
        await api.modify_admin_data_limit(op_username, bytes_add)

        await msg_obj.edit_text(f"✅ با موفقیت {vol} گیگابایت به حجم پنل شما افزوده شد!")

    except Exception as e:
        logger.error(f"Error renewing panel: {e}")
        await add_wallet(message.from_user.id, price)
        await msg_obj.edit_text(f"❌ خطا در تمدید پنل. وجه بازگشت داده شد.\nخطا: {str(e)}")

    await state.clear()

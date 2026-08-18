import logging
import asyncio
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)
from pasarguard import PasarguardAPI, Tools, UserCreate, UserStatus, AdminCreate

# ==================== تنظیمات اصلی ====================
PASARGUARD_BASE_URL = "https://lemina.digistoretg.ir:8000"
ADMIN_USERNAME = "375659"
ADMIN_PASSWORD = "375659M.M375659m.m"

BOT_TOKEN = "8709291270:AAHYPTiiEm9pnwRQn38KErrQG5LDry3tHAA"
ADMIN_CHAT_ID = 8853904925        # آیدی عددی ادمین اصلی
CARD_NUMBER = "5022291572821799"
CARD_HOLDER = "."
SUPPORT_USERNAME = "ajaxiran_sup" # آیدی پشتیبانی

REQUIRED_CHANNEL = "@AjaxIran_ir"  # کانال جوین اجباری
PARTNER_PANEL_FEE = 100_000        # هزینه ورودی پنل نمایندگی
DB_NAME = "bot_database.db"       # فایل دیتابیس SQLite
# ======================================================

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- مدیریت دیتابیس SQLite ---
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        # کیف پول
        cursor.execute('''CREATE TABLE IF NOT EXISTS wallets (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0
        )''')
        # سرویس‌ها
        cursor.execute('''CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            sub_link TEXT,
            volume_gb INTEGER
        )''')
        # نمایندگان
        cursor.execute('''CREATE TABLE IF NOT EXISTS partners (
            user_id INTEGER PRIMARY KEY,
            op_username TEXT,
            status TEXT DEFAULT 'ACTIVE',
            debt_amount INTEGER DEFAULT 0,
            last_processed_volume_gb REAL DEFAULT 0
        )''')
        # تست‌های استفاده شده
        cursor.execute('''CREATE TABLE IF NOT EXISTS used_tests (
            user_id INTEGER PRIMARY KEY
        )''')
        # فاکتورهای در انتظار
        cursor.execute('''CREATE TABLE IF NOT EXISTS pending_payments (
            payment_id INTEGER PRIMARY KEY,
            user_id INTEGER,
            amount INTEGER
        )''')
        conn.commit()

init_db()

# --- توابع دیتابیس ---
def get_wallet(user_id: int) -> int:
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM wallets WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row[0] if row else 0

def add_wallet(user_id: int, amount: int):
    current = get_wallet(user_id)
    new_bal = current + amount
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO wallets (user_id, balance) VALUES (?, ?)", (user_id, new_bal))
        conn.commit()

def add_user_service(user_id: int, username: str, sub_link: str, volume_gb: int):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO services (user_id, username, sub_link, volume_gb) VALUES (?, ?, ?, ?)",
                       (user_id, username, sub_link, volume_gb))
        conn.commit()

def get_user_services(user_id: int):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username, sub_link, volume_gb FROM services WHERE user_id = ?", (user_id,))
        return cursor.fetchall()

def is_test_used(user_id: int) -> bool:
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM used_tests WHERE user_id = ?", (user_id,))
        return cursor.fetchone() is not None

def set_test_used(user_id: int):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO used_tests (user_id) VALUES (?)", (user_id,))
        conn.commit()

def add_partner(user_id: int, op_username: str):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO partners (user_id, op_username, status, debt_amount, last_processed_volume_gb) VALUES (?, ?, 'ACTIVE', 0, 0)",
                       (user_id, op_username))
        conn.commit()

def get_partner(user_id: int):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT op_username, status, debt_amount, last_processed_volume_gb FROM partners WHERE user_id = ?", (user_id,))
        return cursor.fetchone()

def update_partner(user_id: int, status: str, debt: int, processed_vol: float):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE partners SET status = ?, debt_amount = ?, last_processed_volume_gb = ? WHERE user_id = ?",
                       (status, debt, processed_vol, user_id))
        conn.commit()

def get_all_partners():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, op_username, status, debt_amount, last_processed_volume_gb FROM partners")
        return cursor.fetchall()

def add_pending_payment(pid: int, user_id: int, amount: int):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO pending_payments (payment_id, user_id, amount) VALUES (?, ?, ?)", (pid, user_id, amount))
        conn.commit()

def get_pending_payment(pid: int):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, amount FROM pending_payments WHERE payment_id = ?", (pid,))
        return cursor.fetchone()

def delete_pending_payment(pid: int):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM pending_payments WHERE payment_id = ?", (pid,))
        conn.commit()


user_states = {}
payment_counter = 1000

class Pricing:
    @staticmethod
    def user_plan_price(volume_gb: int) -> int:
        if volume_gb < 100:
            return volume_gb * 5_000
        elif 100 <= volume_gb < 500:
            return volume_gb * 3_000
        elif 500 <= volume_gb < 1000:
            return volume_gb * 2_000
        else:
            return int((volume_gb / 1000) * 1_500_000)

    @staticmethod
    def partner_discounted_price(volume_gb: float) -> int:
        """محاسبه هزینه با ۵۰٪ تخفیف برای نماینده"""
        normal_price = Pricing.user_plan_price(int(volume_gb)) if volume_gb >= 1 else volume_gb * 5000
        return int(normal_price * 0.5)


# --- بررسی عضویت کانال ---
async def check_channel_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        if member.status in ['creator', 'administrator', 'member']:
            return True
    except Exception as e:
        print(f"Channel Check Error: {e}")
        return True

    keyboard = [
        [InlineKeyboardButton("📢 عضویت در کانال تلگرام", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@', '')}")],
        [InlineKeyboardButton("✅ عضو شدم / تایید", callback_data='check_join')]
    ]
    msg = f"⚠️ **جهت استفاده از خدمات ربات، ابتدا باید در کانال ما عضو شوید:**\n\n🆔 {REQUIRED_CHANNEL}"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return False


def main_reply_keyboard():
    keyboard = [
        [KeyboardButton("🎁 دریافت تست رایگان (۱ گیگ / ۱ ساعته)")],
        [KeyboardButton("🛒 خرید اشتراک عادی"), KeyboardButton("📡 خرید بر اساس اوتباند")],
        [KeyboardButton("💼 ثبت‌نام پنل نمایندگی (۱۰۰ ت)"), KeyboardButton("📦 سرویس‌های من")],
        [KeyboardButton("💰 کیف پول / شارژ"), KeyboardButton("🎧 پشتیبانی آنلاین")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_channel_membership(update, context):
        return

    user_id = update.effective_user.id
    balance = get_wallet(user_id)
    
    msg = (
        f"🚀 **به ربات هوشمند خدمات V2Ray پاسارگاد خوش آمدید!**\n\n"
        f"💳 **موجودی کیف پول شما:** `{balance:,}` تومان\n\n"
        f"از منوی زیر گزینه مورد نظر خود را انتخاب کنید 👇"
    )
    await update.message.reply_text(msg, reply_markup=main_reply_keyboard(), parse_mode='Markdown')


# --- دستور واقعی محاسبه و تسویه بدهی نمایندگان بر اساس API پاسارگاد ---
async def admin_check_partners_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_CHAT_ID:
        return

    await update.message.reply_text("⏳ در حال دریافت اطلاعات واقعی از پاسارگاد و محاسبه حجم اکانت‌های نمایندگان...")
    partners = get_all_partners()
    
    if not partners:
        await update.message.reply_text("ℹ️ هنوز هیچ نماینده‌ای در دیتابیس ثبت نشده است.")
        return

    processed_count = 0
    
    try:
        async with PasarguardAPI(base_url=PASARGUARD_BASE_URL) as api:
            token_res = await api.get_token(ADMIN_USERNAME, ADMIN_PASSWORD)
            token = token_res.access_token

            # دریافت تمام کاربران ثبت شده در پنل پاسارگاد
            all_users = await api.get_users(token=token)

            for partner in partners:
                p_user_id, op_uname, status, current_debt, last_processed_vol = partner
                processed_count += 1
                
                # پیدا کردن تمام کاربرانی که توسط این نماینده ایجاد شده‌اند
                # (معمولاً در پنل پاسارگاد کاربرانی که توسط اپراتور ساخته می‌شوند admin/owner مشخص دارند)
                total_current_vol_bytes = 0
                for u in all_users:
                    # بررسی اینکه کاربر متعلق به این اپراتور است
                    if hasattr(u, 'admin') and u.admin and u.admin.username == op_uname:
                        total_current_vol_bytes += getattr(u, 'data_limit', 0) or 0

                # تبدیل حجم کل ساخته‌شده به گیگابایت
                total_current_vol_gb = total_current_vol_bytes / (1024**3)
                
                # محاسبه حجم جدید ساخته‌شده از آخرین بررسی
                new_volume_gb = total_current_vol_gb - last_processed_vol

                if new_volume_gb <= 0 and current_debt <= 0:
                    continue # حجمی اضافه نشده و بدهی ندارد

                # محاسبه قیمت ۵۰٪ تخفیف برای حجم جدید
                new_cost = Pricing.partner_discounted_price(new_volume_gb) if new_volume_gb > 0 else 0
                total_debt = current_debt + new_cost

                user_balance = get_wallet(p_user_id)

                # اگر کیف پول کافی باشد -> کسر خودکار
                if user_balance >= total_debt and total_debt > 0:
                    add_wallet(p_user_id, -total_debt)
                    update_partner(p_user_id, "ACTIVE", 0, total_current_vol_gb)
                    try:
                        await context.bot.send_message(
                            p_user_id,
                            f"✅ **تسویه حساب نمایندگی انجام شد:**\n\n"
                            f"📊 حجم جدید ساخته‌شده: `{new_volume_gb:.1f}` گیگابایت\n"
                            f"💵 مبلغ کسرشده (با ۵۰٪ تخفیف): `{total_debt:,}` تومان\n"
                            f"💳 موجودی باقی‌مانده: `{get_wallet(p_user_id):,}` تومان"
                        )
                    except Exception:
                        pass
                elif total_debt > 0:
                    # کیف پول کافی نیست -> اخطار و مسدودسازی
                    update_partner(p_user_id, "DISABLED", total_debt, total_current_vol_gb)
                    msg = (
                        f"⚠️ **فاکتور بدهی واقعی اکانت‌های ساخته‌شده:**\n\n"
                        f"👤 اپراتور: `{op_uname}`\n"
                        f"📊 حجم جدید اضافه شده: `{new_volume_gb:.1f}` گیگابایت\n"
                        f"💵 بدهی قابل پرداخت (با ۵۰٪ تخفیف): `{total_debt:,}` تومان\n"
                        f"💳 موجودی فعلی شما: `{user_balance:,}` تومان\n\n"
                        f"⚠️ **موجودی شما کافی نیست!** لطفاً جهت جلوگیری از مسدود ماندن اکانت‌ها، کیف پول خود را شارژ کنید."
                    )
                    try:
                        await context.bot.send_message(p_user_id, msg, parse_mode='Markdown')
                    except Exception as e:
                        print(f"Error notifying partner {p_user_id}: {e}")

        await update.message.reply_text(f"✅ بررسی واقعی پاسارگاد کامل شد. {processed_count} نماینده بر اساس مصرف دقیق محاسبه شدند.")

    except Exception as e:
        await update.message.reply_text(f"❌ خطایی در استعلام از پاسارگاد رخ داد: {e}")


async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_channel_membership(update, context):
        return

    text = update.message.text
    user_id = update.effective_user.id
    balance = get_wallet(user_id)

    state = user_states.get(user_id)
    if state == 'WAITING_FOR_CUSTOM_CHARGE':
        if text.isdigit():
            amount = int(text)
            if amount < 10_000:
                await update.message.reply_text("❌ حداقل مبلغ شارژ ۱۰,۰۰۰ تومان است.")
                return
            user_states.pop(user_id, None)
            await initiate_payment(update.message, user_id, amount)
        else:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر به تومان وارد کنید:")
        return

    # ۱. تست رایگان
    if text == "🎁 دریافت تست رایگان (۱ گیگ / ۱ ساعته)":
        if is_test_used(user_id):
            await update.message.reply_text("❌ شما قبلاً تست رایگان خود را دریافت کرده‌اید!")
            return

        await update.message.reply_text("⏳ در حال ساخت اکانت تست ۱ گیگابایتی...")
        try:
            async with PasarguardAPI(base_url=PASARGUARD_BASE_URL) as api:
                token_res = await api.get_token(ADMIN_USERNAME, ADMIN_PASSWORD)
                uname = f"test{Tools.random_username(prefix='')}".replace("_", "")
                
                new_user = UserCreate(
                    username=uname,
                    data_limit=Tools.gb(1),
                    expire=Tools.hours(1),
                    status=UserStatus.ACTIVE,
                    note=f"Test Account User {user_id}"
                )
                created = await api.create_user_in_all_groups(new_user, token_res.access_token)
                full_sub_url = f"{PASARGUARD_BASE_URL}{created.subscription_url}"
                
                set_test_used(user_id)
                add_user_service(user_id, created.username, full_sub_url, 1)

                await update.message.reply_text(
                    f"🎉 **اشتراک تست رایگان ساخته شد!**\n\n"
                    f"👤 نام کاربری: `{created.username}`\n"
                    f"📊 حجم: ۱ گیگابایت | ⌛ زمان: ۱ ساعت\n\n"
                    f"🔗 **لینک اشتراک:**\n`{full_sub_url}`",
                    parse_mode='Markdown'
                )
        except Exception as e:
            await update.message.reply_text(f"❌ خطایی در ساخت اکانت تست رخ داد: {e}")

    # ۲. خرید عادی
    elif text == "🛒 خرید اشتراک عادی":
        keyboard = [
            [InlineKeyboardButton("⚡ ۱۰ گیگ (۵۰,۰۰۰ ت)", callback_data='buy_gb_10'), InlineKeyboardButton("⚡ ۲۰ گیگ (۱۰۰,۰۰۰ ت)", callback_data='buy_gb_20')],
            [InlineKeyboardButton("⚡ ۵۰ گیگ (۲۵۰,۰۰۰ ت)", callback_data='buy_gb_50'), InlineKeyboardButton("⚡ ۱۰۰ گیگ (۳۰۰,۰۰۰ ت)", callback_data='buy_gb_100')],
            [InlineKeyboardButton("⚡ ۲۰۰ گیگ (۶۰۰,۰۰۰ ت)", callback_data='buy_gb_200'), InlineKeyboardButton("⚡ ۵۰۰ گیگ (۱,۰۰۰,۰۰۰ ت)", callback_data='buy_gb_500')],
            [InlineKeyboardButton("🔥 اشتراک نامحدود (۱۰۰ گیگ) - ۲۵۰,۰۰۰ ت", callback_data='buy_unlimited')]
        ]
        await update.message.reply_text(f"🛒 **انتخاب پلن کاربر عادی:**\n💳 موجودی: `{balance:,}` تومان", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    # ۳. خرید اوتباند
    elif text == "📡 خرید بر اساس اوتباند":
        keyboard = [[InlineKeyboardButton("💬 ارتباط با پشتیبانی جهت خرید اوتباند", url=f"https://t.me/{SUPPORT_USERNAME}")]]
        await update.message.reply_text(
            f"📡 **خرید اشتراک بر اساس اوتباند اختصاصی**\n\nبرای خرید کانفیگ با مسیر دلخواه، پیام دهید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ۴. نمایندگی ۱۰۰ تومانی
    elif text == "💼 ثبت‌نام پنل نمایندگی (۱۰۰ ت)":
        keyboard = [[InlineKeyboardButton("✅ ایجاد پنل نمایندگی (۱۰۰,۰۰۰ تومان)", callback_data='create_partner_panel')]]
        await update.message.reply_text(
            f"💼 **شرایط نمایندگی ویژه (پس‌پراخت):**\n\n"
            f"۱. ورودی ساخت پنل: **۱۰۰,۰۰۰ تومان**\n"
            f"۲. محاسبه هزینه اکانت‌ها هر ۲۴ ساعت با **۵۰٪ تخفیف**.\n"
            f"۳. در صورت عدم پرداخت فاکتور: **مسدود شدن پنل و کاربران** تا زمان تسویه.\n\n"
            f"💳 موجودی: `{balance:,}` تومان",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    # ۵. سرویس‌های من
    elif text == "📦 سرویس‌های من":
        services = get_user_services(user_id)
        if not services:
            await update.message.reply_text("❌ شما هنوز سرویسی خریداری نکرده‌اید.")
            return

        msg = "📦 **لیست سرویس‌های شما:**\n\n"
        for idx, s in enumerate(services, 1):
            msg += f"🔹 **سرویس {idx}:**\n👤 کاربر: `{s[0]}`\n📊 حجم: {s[2]}GB\n🔗 لینک:\n`{s[1]}`\n--------------------\n"
        await update.message.reply_text(msg, parse_mode='Markdown')

    # ۶. کیف پول
    elif text == "💰 کیف پول / شارژ":
        keyboard = [
            [InlineKeyboardButton("➕ ۱۰۰,۰۰۰ تومان", callback_data='charge_100'), InlineKeyboardButton("➕ ۲۰۰,۰۰۰ تومان", callback_data='charge_200')],
            [InlineKeyboardButton("➕ ۵۰۰,۰۰۰ تومان", callback_data='charge_500'), InlineKeyboardButton("➕ ۱,۰۰۰,۰۰۰ تومان", callback_data='charge_1000')],
            [InlineKeyboardButton("✏️ ورود مبلغ دلخواه", callback_data='charge_custom')]
        ]
        await update.message.reply_text(f"💰 **کیف پول:** `{balance:,}` تومان", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    # ۷. پشتیبانی
    elif text == "🎧 پشتیبانی آنلاین":
        keyboard = [[InlineKeyboardButton("💬 چت با پشتیبانی", url=f"https://t.me/{SUPPORT_USERNAME}")]]
        await update.message.reply_text("🎧 جهت ارتباط کلیک کنید:", reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    balance = get_wallet(user_id)

    if data == 'check_join':
        if await check_channel_membership(update, context):
            await start(update, context)
        return

    # شارژ
    if data.startswith('charge_'):
        val = data.split('_')[1]
        if val == 'custom':
            user_states[user_id] = 'WAITING_FOR_CUSTOM_CHARGE'
            await query.edit_message_text("✍️ مبلغ دلخواه خود را به **تومان** وارد کنید:")
            return
        amount = int(val) * 1000
        await initiate_payment(query, user_id, amount)

    # خرید کاربر
    elif data.startswith('buy_gb_') or data == 'buy_unlimited':
        gb = 100 if data == 'buy_unlimited' else int(data.split('_')[2])
        price = 250_000 if data == 'buy_unlimited' else Pricing.user_plan_price(gb)

        if balance < price:
            await query.edit_message_text(f"❌ موجودی کافی نیست. هزینه: `{price:,}` تومان | موجودی: `{balance:,}` تومان", parse_mode='Markdown')
            return

        add_wallet(user_id, -price)
        await query.edit_message_text("⏳ در حال ساخت اشتراک...")

        try:
            async with PasarguardAPI(base_url=PASARGUARD_BASE_URL) as api:
                token_res = await api.get_token(ADMIN_USERNAME, ADMIN_PASSWORD)
                uname = f"u{Tools.random_username(prefix='')}".replace("_", "")
                
                new_user = UserCreate(
                    username=uname,
                    data_limit=Tools.gb(gb),
                    expire=Tools.days(30),
                    status=UserStatus.ACTIVE,
                    note=f"Normal Buy {gb}GB"
                )
                created = await api.create_user_in_all_groups(new_user, token_res.access_token)
                full_sub_url = f"{PASARGUARD_BASE_URL}{created.subscription_url}"
                add_user_service(user_id, created.username, full_sub_url, gb)

                await query.edit_message_text(
                    f"🎉 **اشتراک ساخته شد!**\n\n👤 نام کاربری: `{created.username}`\n📊 حجم: {gb} گیگ\n🔗 لینک اشتراک:\n`{full_sub_url}`",
                    parse_mode='Markdown'
                )
        except Exception as e:
            add_wallet(user_id, price)
            await query.edit_message_text(f"❌ خطایی رخ داد (مبلغ بازگشت داده شد):\n{str(e)}")

    # ساخت پنل نمایندگی
    elif data == 'create_partner_panel':
        if balance < PARTNER_PANEL_FEE:
            await query.edit_message_text(f"❌ برای ثبت نام پنل نیازمند ۱۰۰,۰۰۰ تومان شارژ کیف پول هستید.")
            return

        add_wallet(user_id, -PARTNER_PANEL_FEE)
        await query.edit_message_text("⏳ در حال ساخت پنل نمایندگی...")

        try:
            async with PasarguardAPI(base_url=PASARGUARD_BASE_URL) as api:
                token_res = await api.get_token(ADMIN_USERNAME, ADMIN_PASSWORD)
                op_username = f"op{Tools.random_username(prefix='')}".replace("_", "")
                op_password = "Pass" + Tools.random_username(prefix="")[:6].upper() + "!99"

                admin_data = AdminCreate(
                    username=op_username,
                    password=op_password,
                    role_id=3,
                    is_sudo=False
                )
                await api.create_admin(admin=admin_data, token=token_res.access_token)
                add_partner(user_id, op_username)

                msg = (
                    f"🎉 **پنل نمایندگی با موفقیت ساخته شد!**\n\n"
                    f"🌐 **آدرس ورود:** {PASARGUARD_BASE_URL}/dashboard/\n"
                    f"👤 **نام کاربری:** `{op_username}`\n"
                    f"🔑 **رمز عبور:** `{op_password}`"
                )
                await query.edit_message_text(msg, parse_mode='Markdown')
        except Exception as e:
            add_wallet(user_id, PARTNER_PANEL_FEE)
            await query.edit_message_text(f"❌ خطا در ساخت پنل:\n{str(e)}")

    # تایید / رد ادمین
    elif data.startswith('admin_confirm_') or data.startswith('admin_reject_'):
        pid = int(data.split('_')[2])
        pdata = get_pending_payment(pid)

        async def safe_edit(text):
            if query.message.photo:
                await query.edit_message_caption(caption=text)
            else:
                await query.edit_message_text(text=text)

        if not pdata:
            await safe_edit("❌ این درخواست قبلاً تعیین تکلیف شده است.")
            return

        target_user_id, amount = pdata

        if data.startswith('admin_confirm_'):
            add_wallet(target_user_id, amount)
            delete_pending_payment(pid)
            await safe_edit(f"✅ تایید شد! مبلغ {amount:,} تومان شارژ شد.")

            partner_info = get_partner(target_user_id)
            if partner_info and partner_info[1] == "DISABLED":
                debt = partner_info[2]
                if get_wallet(target_user_id) >= debt:
                    add_wallet(target_user_id, -debt)
                    update_partner(target_user_id, "ACTIVE", 0, partner_info[3])

                    try:
                        await context.bot.send_message(target_user_id, "🎉 **تسویه بدهی انجام شد! پنل نمایندگی شما مجدداً فعال گردید.**")
                    except Exception as e:
                        print(f"Error: {e}")

            try:
                await context.bot.send_message(target_user_id, f"🎉 فاکتور تایید شد! `{amount:,}` تومان به کیف پول اضافه شد.")
            except Exception:
                pass
        elif data.startswith('admin_reject_'):
            delete_pending_payment(pid)
            await safe_edit("❌ درخواست رد شد.")


async def initiate_payment(query_or_update, user_id: int, amount: int):
    global payment_counter
    payment_counter += 1
    pid = payment_counter
    add_pending_payment(pid, user_id, amount)
    user_states[user_id] = f"WAITING_FOR_RECEIPT_{pid}"

    msg = (
        f"💳 **فاکتور شارژ کیف پول**\n🆔 شناسه: `{pid}`\n💵 مبلغ: `{amount:,}` تومان\n\n"
        f"💳 شماره کارت:\n`{CARD_NUMBER}`\n👤 به نام: `{CARD_HOLDER}`\n\n"
        f"⚠️ **عکس رسید پرداخت را ارسال کنید.**"
    )
    if hasattr(query_or_update, 'edit_message_text'):
        await query_or_update.edit_message_text(msg, parse_mode='Markdown')
    else:
        await query_or_update.reply_text(msg, parse_mode='Markdown')


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_states.get(user_id)

    if state and state.startswith("WAITING_FOR_RECEIPT_"):
        pid = int(state.split("_")[3])
        pdata = get_pending_payment(pid)

        if not pdata:
            await update.message.reply_text("❌ فاکتور منقضی شده است.")
            return

        photo_file_id = update.message.photo[-1].file_id
        amount = pdata[1]
        user_states.pop(user_id, None)

        await update.message.reply_text("⏳ رسید برای ادمین ارسال شد.")

        admin_keyboard = [[
            InlineKeyboardButton("✅ تایید و شارژ", callback_data=f'admin_confirm_{pid}'),
            InlineKeyboardButton("❌ رد رسید", callback_data=f'admin_reject_{pid}')
        ]]
        caption_text = f"📥 رسید جدید!\n👤 کاربر: {user_id}\n🆔 فاکتور: {pid}\n💰 مبلغ: {amount:,} تومان"

        try:
            await context.bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=photo_file_id, caption=caption_text, reply_markup=InlineKeyboardMarkup(admin_keyboard))
        except Exception as e:
            print(f"Error sending photo to admin: {e}")


def main():
    print("🚀 ربات پاسارگاد (با سیستم محاسبه واقعی API) اجرا شد...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check_partners", admin_check_partners_now))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))

    app.run_polling()

if __name__ == '__main__':
    main()
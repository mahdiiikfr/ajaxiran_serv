from aiogram import Router, F
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import SUPPORT_USERNAME

router = Router()

@router.message(F.text.in_(["🎧 پشتیبانی", "📜 قوانین و راهنما"]))
async def support_menu(message: Message):
    text = (
        "❓ <b>سوالات متداول</b>\n\n"
        "1️⃣ <b>فیلترشکن شما آیپی ثابته؟ میتونم برای صرافی های ارز دیجیتال استفاده کنم؟</b>\n"
        "✅ به دلیل وضعیت نت و محدودیت های کشور سرویس ما مناسب ترید نیست و فقط لوکیشن‌ ثابته.\n\n"
        "2️⃣ <b>اگه قبل از منقضی شدن اکانت، تمدید کنم روزها و حجم باقی مانده می سوزد؟</b>\n"
        "✅ خیر، بسته تمدید شده برای شما رزرو می گردد و به محض پایان حجم یا زمان باقیمانده جایگزین می گردد.\n\n"
        "3️⃣ <b>سرویسها چند کاربره هستند؟</b>\n"
        "✅ تمامی سرویسهای ما سه کاربره هستند و در صورت سوء استفاده و پخش شدن لینک توسط سیستم تشخیص داده شده و مسدود میگردد.\n\n"
        "4️⃣ <b>فیلترشکن شما از چه نوعی هست؟</b>\n"
        "✅ فیلترشکن های ما v2ray است و پروتکل‌های مختلفی را ساپورت میکنیم تا با سخت تر شدن حلقه فیلترینگ بتوانیم بهترین سرویس ممکن را ارائه دهیم.\n\n"
        "5️⃣ <b>فیلترشکن وصل نمیشه، چیکار کنم؟</b>\n"
        "✅ ابتدا سرویس خود را بروزرسانی کنید تا آخرین سرورها را دریافت نمایید. در صورتی که با همه سرورها تست کردید و همه قطع بودند با پشتیبانی تماس بگیرید.\n\n"
        "6️⃣ <b>امکان بازگشت وجه دارید؟</b>\n"
        "✅ امکان بازگشت وجه در صورت حل نشدن مشکل از سمت ما وجود دارد.\n\n"
        "📬 در صورتی که نتوانستید پاسخ سوالات و مشکلات خود را در بخش بالا پیدا کنید، جهت ارتباط بیشتر می توانید با دکمه زیر به پشتیبانی پیام بدید."
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="💬 ارتباط با پشتیبانی", url=f"https://t.me/{SUPPORT_USERNAME}")

    await message.answer(text, reply_markup=builder.as_markup())

@router.message(F.text == "📦 سرویس‌های من")
async def my_services(message: Message):
    from database.crud import get_user_services
    services = await get_user_services(message.from_user.id)

    if not services:
        await message.answer("❌ شما هنوز سرویسی خریداری نکرده‌اید.")
        return

    msg = "📦 لیست سرویس‌های فعال شما:\n\n"
    for idx, s in enumerate(services, 1):
        # s[0] username, s[1] sub_link, s[2] volume_gb, s[3] type
        srv_type = "گیمینگ" if s[3] == "gaming" else "عادی"
        msg += (
            f"🔹 سرویس {idx} | نوع: {srv_type}\n"
            f"👤 نام کاربری: <code>{s[0]}</code>\n"
            f"📊 حجم کل: {s[2]} گیگابایت\n"
            "🔗 لینک اتصال:\n"
            f"<code>{s[1]}</code>\n"
            "➖➖➖➖➖➖➖➖\n"
        )

    await message.answer(msg)

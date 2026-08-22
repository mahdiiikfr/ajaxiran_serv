import aiohttp
import logging

from config import SMS_API_KEY, SMS_TEMPLATE_ID, ZARINPAL_MERCHANT_ID, CALLBACK_URL

logger = logging.getLogger(__name__)

async def send_otp_sms(mobile: str, otp_code: int):
    """تابع ارسال پیامک از طریق وب‌سرویس sms.ir به صورت غیرهمزمان"""
    url = "https://api.sms.ir/v1/send/verify"
    headers = {
        "X-API-KEY": SMS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "mobile": mobile,
        "templateId": int(SMS_TEMPLATE_ID),
        "parameters": [{"name": "Code", "value": str(otp_code)}]
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=15) as response:
                return await response.json()
    except Exception as e:
        logger.error(f"Error sending SMS: {e}")
        return {"status": 0, "message": str(e)}

async def calculate_zarinpal_fee(amount: int):
    """تابع محاسبه کارمزد تراکنش"""
    url = "https://payment.zarinpal.com/pg/v4/payment/feeCalculation.json"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "merchant_id": ZARINPAL_MERCHANT_ID,
        "amount": amount,
        "currency": "IRR"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=15) as response:
                return await response.json()
    except Exception as e:
        logger.error(f"Error calculating fee: {e}")
        return {"errors": str(e)}

async def create_zarinpal_payment(amount: int, mobile: str, card_pan: str):
    """تابع ساخت لینک پرداخت زرین‌پال با کارت محدود شده"""
    url = "https://payment.zarinpal.com/pg/v4/payment/request.json"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "merchant_id": ZARINPAL_MERCHANT_ID,
        "amount": amount,
        "description": "شارژ کیف پول",
        "callback_url": CALLBACK_URL,
        "metadata": {
            "mobile": mobile,
            "card_pan": card_pan
        }
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=15) as response:
                return await response.json()
    except Exception as e:
        logger.error(f"Error creating ZarinPal payment: {e}")
        return {"errors": str(e)}

async def verify_zarinpal_payment(amount: int, authority: str):
    """تابع اعتبارسنجی تراکنش پس از پرداخت موفق در درگاه"""
    url = "https://payment.zarinpal.com/pg/v4/payment/verify.json"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "merchant_id": ZARINPAL_MERCHANT_ID,
        "amount": amount,
        "authority": authority
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=15) as response:
                return await response.json()
    except Exception as e:
        logger.error(f"Error verifying ZarinPal payment: {e}")
        return {"errors": str(e)}

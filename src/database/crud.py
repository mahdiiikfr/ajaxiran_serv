import aiosqlite
import logging

from config import DB_PATH

logger = logging.getLogger(__name__)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                phone_number TEXT,
                verified_card_number TEXT,
                zarinpal_card_number TEXT,
                rules_accepted BOOLEAN DEFAULT 0
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS wallets (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                sub_link TEXT,
                volume_gb INTEGER,
                type TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS partners (
                user_id INTEGER PRIMARY KEY,
                op_username TEXT,
                status TEXT DEFAULT 'ACTIVE',
                type TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS pending_payments (
                payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                authority TEXT
            )
        ''')
        await db.commit()
    logger.info("Database initialized.")

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "user_id": row[0],
                    "username": row[1],
                    "phone_number": row[2],
                    "verified_card_number": row[3],
                    "zarinpal_card_number": row[4],
                    "rules_accepted": bool(row[5])
                }
            return None

async def create_user(user_id: int, username: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        await db.execute("INSERT OR IGNORE INTO wallets (user_id, balance) VALUES (?, 0)", (user_id,))
        await db.commit()

async def update_user_rules_accepted(user_id: int, accepted: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET rules_accepted = ? WHERE user_id = ?", (int(accepted), user_id))
        await db.commit()
    return True

async def get_wallet(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT balance FROM wallets WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def add_wallet(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        # Prevent double spending race condition by executing an atomic update
        await db.execute("UPDATE wallets SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

async def update_user_verified_card(user_id: int, card_number: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET verified_card_number = ? WHERE user_id = ?", (card_number, user_id))
        await db.commit()
    return True

async def update_user_zarinpal_card(user_id: int, card_number: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET zarinpal_card_number = ? WHERE user_id = ?", (card_number, user_id))
        await db.commit()
    return True

async def update_user_phone(user_id: int, phone: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET phone_number = ? WHERE user_id = ?", (phone, user_id))
        await db.commit()
    return True

async def add_pending_payment(user_id: int, amount: int, authority: str = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("INSERT INTO pending_payments (user_id, amount, authority) VALUES (?, ?, ?)", (user_id, amount, authority))
        await db.commit()
        return cursor.lastrowid

async def get_pending_payment(payment_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, amount, authority FROM pending_payments WHERE payment_id = ?", (payment_id,)) as cursor:
            return await cursor.fetchone()

async def delete_pending_payment(payment_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM pending_payments WHERE payment_id = ?", (payment_id,))
        await db.commit()

async def add_user_service(user_id: int, username: str, sub_link: str, volume_gb: int, type: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO services (user_id, username, sub_link, volume_gb, type) VALUES (?, ?, ?, ?, ?)",
                       (user_id, username, sub_link, volume_gb, type))
        await db.commit()

async def get_user_services(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT username, sub_link, volume_gb, type FROM services WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchall()

async def add_partner(user_id: int, op_username: str, type: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO partners (user_id, op_username, status, type) VALUES (?, ?, 'ACTIVE', ?)", (user_id, op_username, type))
        await db.commit()

async def get_partner(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT op_username, status, type FROM partners WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

async def update_partner_status(user_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE partners SET status = ? WHERE user_id = ?", (status, user_id))
        await db.commit()

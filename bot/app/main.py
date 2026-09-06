import asyncio
import os
import httpx
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
API = os.getenv("API_BASE_URL", "http://api:8000").rstrip("/")

dp = Dispatcher()


async def ensure_user(message: Message) -> dict:
    payload = {
        "telegram_id": message.from_user.id,
        "username": message.from_user.username,
        "display_name": message.from_user.full_name,
    }
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{API}/api/users", json=payload)
        r.raise_for_status()
        return r.json()


@dp.message(CommandStart())
async def start(message: Message):
    await ensure_user(message)
    await message.answer("سلام 👋\nحساب شما آماده است. برای دیدن پلن‌ها /plans و برای سرویس‌های شما /my را بزنید.")


@dp.message(Command("plans"))
async def plans(message: Message):
    await ensure_user(message)
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{API}/api/plans")
        r.raise_for_status()
        data = r.json()
    if not data:
        await message.answer("فعلاً پلن فعالی تعریف نشده است.")
        return
    lines = ["پلن‌های فعال:"]
    for p in data:
        lines.append(f"• {p['name']} — {p['traffic_gb']}GB / {p['days']} روز — {p['price']:,} {p['currency']}")
    await message.answer("\n".join(lines))


@dp.message(Command("my"))
async def my_services(message: Message):
    user = await ensure_user(message)
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{API}/api/subscriptions/by-user/{user['id']}")
        r.raise_for_status()
        data = r.json()
    if not data:
        await message.answer("هنوز سرویسی ندارید.")
        return
    lines = ["سرویس‌های شما:"]
    for s in data:
        lines.append(f"• #{s['id']} — {s['status']} — پایان: {s.get('expires_at') or '-'}")
        if s.get("subscription_url"):
            lines.append(s["subscription_url"])
    await message.answer("\n".join(lines))


async def main():
    if not TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set")
    bot = Bot(TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

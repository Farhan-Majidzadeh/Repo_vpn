import asyncio
import os
import httpx
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
API = os.getenv("API_BASE_URL", "http://api:8000").rstrip("/")
ADMINS = {int(x) for x in os.getenv("TELEGRAM_ADMIN_IDS", "").split(",") if x.strip().isdigit()}

dp = Dispatcher()


async def api_request(method, path, **kwargs):
    async with httpx.AsyncClient(timeout=40) as c:
        r = await c.request(method, f"{API}{path}", **kwargs)
        r.raise_for_status()
        return r.json()


async def ensure_user(message: Message) -> dict:
    return await api_request("POST", "/api/users", json={
        "telegram_id": message.from_user.id,
        "username": message.from_user.username,
        "display_name": message.from_user.full_name,
    })


@dp.message(CommandStart())
async def start(message: Message):
    await ensure_user(message)
    await message.answer("سلام 👋\nحساب شما آماده است. برای دیدن پلن‌ها /plans و برای سرویس‌های شما /my را بزنید.")


@dp.message(Command("plans"))
async def plans(message: Message):
    await ensure_user(message)
    data = await api_request("GET", "/api/plans")
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
    data = await api_request("GET", f"/api/subscriptions/by-user/{user['id']}")
    if not data:
        await message.answer("هنوز سرویسی ندارید.")
        return
    lines = ["سرویس‌های شما:"]
    for s in data:
        lines.append(f"• #{s['id']} — {s['status']} — پایان: {s.get('expires_at') or '-'}")
        if s.get("subscription_url"):
            lines.append(s["subscription_url"])
    await message.answer("\n".join(lines))


@dp.message(Command("admin"))
async def admin(message: Message):
    if not message.from_user or message.from_user.id not in ADMINS:
        return
    await message.answer("مدیریت آزمایشی: /grant <telegram_id> <plan_id>\nفقط ادمین می‌تواند سرویس رایگان آزمایشی صادر کند.")


@dp.message(Command("grant"))
async def grant(message: Message):
    if not message.from_user or message.from_user.id not in ADMINS:
        return
    try:
        _, tg, plan = message.text.split()
        tg, plan = int(tg), int(plan)
        user = await api_request("GET", f"/api/users/by-telegram/{tg}")
        sub = await api_request(
            "POST", "/api/subscriptions",
            json={"user_id": user["id"], "plan_id": plan},
            headers={"X-Admin-Key": os.environ["APP_SECRET"]},
        )
        await message.answer(f"سرویس آزمایشی ساخته شد: #{sub['id']}\n{sub.get('subscription_url') or 'لینک هنوز از پنل دریافت نشده است.'}")
    except Exception as exc:
        await message.answer(f"صدور ناموفق: {type(exc).__name__}. جزئیات در لاگ سرور بررسی شود.")


async def main():
    if not TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set")
    bot = Bot(TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

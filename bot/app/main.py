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


def order_headers():
    return {"X-Admin-Key": os.environ["APP_SECRET"]}


@dp.message(CommandStart())
async def start(message: Message):
    await ensure_user(message)
    await message.answer(
        "سلام 👋\n"
        "برای دیدن پلن‌ها /plans، خرید /buy <plan_id>، سفارش‌ها /orders و سرویس‌ها /my را بزنید."
    )


@dp.message(Command("plans"))
async def plans(message: Message):
    await ensure_user(message)
    data = await api_request("GET", "/api/plans")
    if not data:
        await message.answer("فعلاً پلن فعالی تعریف نشده است.")
        return
    lines = ["پلن‌های فعال:"]
    for p in data:
        lines.append(f"• #{p['id']} {p['name']} — {p['traffic_gb']}GB / {p['days']} روز — {p['price']:,} {p['currency']}")
        lines.append(f"  خرید: /buy {p['id']}")
    await message.answer("\n".join(lines))


@dp.message(Command("buy"))
async def buy(message: Message):
    if not message.from_user or not message.chat or message.chat.type != "private":
        await message.answer("خرید را فقط در گفت‌وگوی خصوصی با ربات انجام دهید.")
        return
    try:
        _, value = message.text.split()
        plan_id = int(value)
        if plan_id <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("فرمت درست: /buy <plan_id> — شناسه پلن را از /plans بردارید.")
        return
    try:
        user = await ensure_user(message)
        order = await api_request(
            "POST",
            "/api/orders",
            headers=order_headers(),
            json={
                "user_id": user["id"],
                "plan_id": plan_id,
                "idempotency_key": f"telegram:{message.chat.id}:{message.message_id}",
            },
        )
        await message.answer(
            f"سفارش #{order['id']} ثبت شد — وضعیت: {order['status']}\n"
            f"{order['plan_name']} — {order['price']:,} {order['currency']}\n\n"
            f"{order['payment_instructions']}\n\n"
            "پس از واریز، مدیر پرداخت را بررسی و سفارش را تأیید می‌کند. وضعیت را با /orders ببینید."
        )
    except Exception:
        await message.answer("ثبت سفارش ناموفق بود. ابتدا /orders را بررسی کنید و سپس دوباره تلاش کنید.")


@dp.message(Command("orders"))
async def my_orders(message: Message):
    if not message.from_user or not message.chat or message.chat.type != "private":
        await message.answer("سفارش‌ها را فقط در گفت‌وگوی خصوصی با ربات ببینید.")
        return
    try:
        user = await ensure_user(message)
        orders = await api_request("GET", f"/api/orders/by-user/{user['id']}", headers=order_headers())
        if not orders:
            await message.answer("هنوز سفارشی ندارید. برای انتخاب پلن /plans را بزنید.")
            return
        lines = ["سفارش‌های شما:"]
        for order in orders:
            line = f"• #{order['id']} — {order['plan_name']} — {order['status']}"
            if order.get("subscription_id"):
                line += f" — سرویس #{order['subscription_id']}"
            lines.append(line)
        await message.answer("\n".join(lines))
    except Exception:
        await message.answer("دریافت سفارش‌ها ناموفق بود. کمی بعد دوباره تلاش کنید.")


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
    await message.answer(
        "مدیریت سفارش‌ها:\n"
        "/approve <order_id>\n/reject <order_id>\n/reconcile <order_id>\n"
        "صدور آزمایشی: /grant <telegram_id> <plan_id>\n"
        "قبل از تأیید سفارش، واریز را مستقل بررسی کنید."
    )


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
            headers=order_headers(),
        )
        await message.answer(f"سرویس آزمایشی ساخته شد: #{sub['id']}\n{sub.get('subscription_url') or 'لینک هنوز از پنل دریافت نشده است.'}")
    except Exception as exc:
        await message.answer(f"صدور ناموفق: {type(exc).__name__}. جزئیات در لاگ سرور بررسی شود.")


async def order_decision(message: Message, action: str):
    if not message.from_user or message.from_user.id not in ADMINS:
        return
    try:
        _, value = message.text.split()
        order_id = int(value)
        if order_id <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer(f"فرمت درست: /{action} <order_id>")
        return
    try:
        order = await api_request("POST", f"/api/orders/{order_id}/{action}", headers=order_headers())
        await message.answer(f"سفارش #{order['id']}: {order['status']}")
    except Exception:
        await message.answer("عملیات سفارش ناموفق بود. وضعیت سفارش و لاگ سرور را بررسی کنید.")


@dp.message(Command("approve"))
async def approve(message: Message):
    await order_decision(message, "approve")


@dp.message(Command("reject"))
async def reject(message: Message):
    await order_decision(message, "reject")


@dp.message(Command("reconcile"))
async def reconcile(message: Message):
    await order_decision(message, "reconcile")


async def main():
    if not TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set")
    bot = Bot(TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

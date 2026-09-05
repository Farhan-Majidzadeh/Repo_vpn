import asyncio
import logging

import httpx
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message

from vpn_sales.config import get_settings

settings = get_settings()
dispatcher = Dispatcher()
logger = logging.getLogger(__name__)


@dispatcher.message(CommandStart())
async def start(message: Message) -> None:
    if settings.sales_mode == "disabled":
        await message.answer("فروش در حال حاضر غیرفعال است.")
        return
    if (
        settings.sales_mode == "private_beta"
        and (
            message.from_user is None
            or message.from_user.id not in settings.private_beta_ids
        )
    ):
        await message.answer("نسخهٔ آزمایشی خصوصی است و هنوز برای فروش عمومی باز نشده است.")
        return

    async with httpx.AsyncClient(base_url=settings.api_base_url, timeout=10) as client:
        response = await client.get("/api/v1/packages")
        response.raise_for_status()
        packages = response.json()

    if not packages:
        await message.answer("در حال حاضر پکیج فعالی وجود ندارد.")
        return
    lines = ["پکیج‌های فعال:"]
    for package in packages:
        gb = package["traffic_bytes"] // (1024**3)
        price = f'{package["price_toman"]:,}'
        lines.append(
            f'• {package["name"]}: {gb} گیگ، '
            f'{package["duration_days"]} روز، {price} تومان'
        )
    await message.answer("\n".join(lines))


async def main() -> None:
    if not settings.telegram_bot_token:
        logger.warning("bot is idle because TELEGRAM_BOT_TOKEN is not configured")
        await asyncio.Event().wait()
        return
    await dispatcher.start_polling(Bot(settings.telegram_bot_token))


if __name__ == "__main__":
    logging.basicConfig(level=settings.log_level)
    asyncio.run(main())

import asyncio
import logging

from redis.asyncio import Redis

from vpn_sales.config import get_settings

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        while True:
            item = await redis.blpop("vpn-sales:jobs", timeout=5)
            if item:
                _, job_id = item
                logger.info("received provisioning job %s", job_id)
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())

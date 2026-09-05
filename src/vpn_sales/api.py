from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from vpn_sales.config import get_settings
from vpn_sales.db import get_session
from vpn_sales.models import Package

settings = get_settings()
redis = Redis.from_url(settings.redis_url, decode_responses=True)
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await redis.aclose()


app = FastAPI(title="VPN Sales API", version="0.1.0", lifespan=lifespan)


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def ready(session: SessionDep) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    await redis.ping()
    return {"status": "ready"}


@app.get("/api/v1/packages")
async def packages(session: SessionDep) -> list[dict]:
    result = await session.execute(
        select(Package).where(Package.is_active.is_(True)).order_by(Package.traffic_bytes)
    )
    return [
        {
            "id": str(package.id),
            "code": package.code,
            "name": package.name,
            "traffic_bytes": package.traffic_bytes,
            "duration_days": package.duration_days,
            "price_toman": package.price_toman,
        }
        for package in result.scalars()
    ]

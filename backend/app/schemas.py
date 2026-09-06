from datetime import datetime
from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    telegram_id: int | None = None
    username: str | None = None
    display_name: str | None = None


class UserOut(UserCreate):
    id: int
    is_active: bool
    is_blacklisted: bool
    model_config = {"from_attributes": True}


class PlanCreate(BaseModel):
    name: str
    days: int = Field(gt=0)
    traffic_gb: int = Field(gt=0)
    price: int = Field(ge=0)
    currency: str = "IRR"


class PlanOut(PlanCreate):
    id: int
    is_active: bool
    model_config = {"from_attributes": True}


class SubscriptionCreate(BaseModel):
    user_id: int
    plan_id: int


class SubscriptionOut(BaseModel):
    id: int
    user_id: int
    plan_id: int
    status: str
    panel_username: str | None = None
    subscription_url: str | None = None
    traffic_limit_bytes: int
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    model_config = {"from_attributes": True}

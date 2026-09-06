from datetime import datetime, timedelta, timezone
import secrets
from sqlalchemy.orm import Session
from . import models
from .panels import get_adapter


def create_subscription(db: Session, user: models.User, plan: models.Plan) -> models.Subscription:
    if user.is_blacklisted or not user.is_active:
        raise ValueError("user is not eligible")
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=plan.days)
    panel_username = f"u{user.id}_{secrets.token_hex(4)}"
    traffic = plan.traffic_gb * 1024**3
    result = get_adapter().create_user(panel_username, traffic, int(expires.timestamp()))
    sub = models.Subscription(
        user_id=user.id,
        plan_id=plan.id,
        status=models.SubscriptionStatus.active.value,
        panel_username=result.username,
        subscription_url=result.subscription_url,
        traffic_limit_bytes=traffic,
        starts_at=now,
        expires_at=expires,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub

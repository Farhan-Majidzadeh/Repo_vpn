from contextlib import asynccontextmanager
import secrets
from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import get_settings
from .db import Base, engine, get_db
from . import models, schemas
from .service import create_subscription
from .panels import get_adapter


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Repo_vpn API", version="0.2.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/panel")
def panel_health():
    return {"healthy": get_adapter().health()}


@app.post("/api/users", response_model=schemas.UserOut)
def create_user(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    if payload.telegram_id is not None:
        existing = db.scalar(select(models.User).where(models.User.telegram_id == payload.telegram_id))
        if existing:
            return existing
    user = models.User(**payload.model_dump())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.get("/api/users/by-telegram/{telegram_id}", response_model=schemas.UserOut)
def get_user_by_telegram(telegram_id: int, db: Session = Depends(get_db)):
    user = db.scalar(select(models.User).where(models.User.telegram_id == telegram_id))
    if not user:
        raise HTTPException(404, "user not found")
    return user


def require_admin(request: Request):
    supplied = request.headers.get("X-Admin-Key", "")
    expected = get_settings().app_secret
    if (
        not expected
        or expected == "dev-only-change-me"
        or not secrets.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))
    ):
        raise HTTPException(403, "admin authorization required")


@app.post("/api/plans", response_model=schemas.PlanOut)
def create_plan(payload: schemas.PlanCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    plan = models.Plan(**payload.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@app.get("/api/plans", response_model=list[schemas.PlanOut])
def list_plans(db: Session = Depends(get_db)):
    return list(db.scalars(select(models.Plan).where(models.Plan.is_active.is_(True)).order_by(models.Plan.price)).all())


@app.post("/api/subscriptions", response_model=schemas.SubscriptionOut)
def provision_subscription(payload: schemas.SubscriptionCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    user = db.get(models.User, payload.user_id)
    plan = db.get(models.Plan, payload.plan_id)
    if not user or not plan:
        raise HTTPException(404, "user or plan not found")
    try:
        return create_subscription(db, user, plan)
    except Exception as exc:
        db.rollback()
        raise HTTPException(502, f"panel provisioning failed: {exc}") from exc


@app.get("/api/subscriptions/by-user/{user_id}", response_model=list[schemas.SubscriptionOut])
def subscriptions_by_user(user_id: int, db: Session = Depends(get_db)):
    return list(db.scalars(select(models.Subscription).where(models.Subscription.user_id == user_id).order_by(models.Subscription.created_at.desc())).all())

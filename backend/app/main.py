from contextlib import asynccontextmanager
import secrets
from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
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


app = FastAPI(title="Repo_vpn API", version="0.3.0", lifespan=lifespan)


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
        raise HTTPException(502, "panel provisioning failed") from exc


@app.get("/api/subscriptions/by-user/{user_id}", response_model=list[schemas.SubscriptionOut])
def subscriptions_by_user(user_id: int, db: Session = Depends(get_db)):
    return list(db.scalars(select(models.Subscription).where(models.Subscription.user_id == user_id).order_by(models.Subscription.created_at.desc())).all())


def order_receipt(order: models.Order) -> schemas.OrderReceipt:
    return schemas.OrderReceipt(
        **schemas.OrderOut.model_validate(order).model_dump(),
        payment_instructions=get_settings().payment_instructions,
    )


@app.post("/api/orders", response_model=schemas.OrderReceipt, dependencies=[Depends(require_admin)])
def create_order(payload: schemas.OrderCreate, db: Session = Depends(get_db)):
    existing = db.scalar(select(models.Order).where(models.Order.idempotency_key == payload.idempotency_key))
    if existing:
        if existing.user_id != payload.user_id or existing.plan_id != payload.plan_id:
            raise HTTPException(409, "idempotency key already used")
        return order_receipt(existing)

    user = db.get(models.User, payload.user_id)
    plan = db.get(models.Plan, payload.plan_id)
    if not user or not plan:
        raise HTTPException(404, "user or plan not found")
    if not user.is_active or user.is_blacklisted or not plan.is_active:
        raise HTTPException(409, "user or plan is not eligible")

    order = models.Order(
        **payload.model_dump(),
        plan_name=plan.name,
        days=plan.days,
        traffic_gb=plan.traffic_gb,
        price=plan.price,
        currency=plan.currency,
    )
    db.add(order)
    try:
        db.commit()
        db.refresh(order)
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(models.Order).where(models.Order.idempotency_key == payload.idempotency_key))
        if existing and existing.user_id == payload.user_id and existing.plan_id == payload.plan_id:
            return order_receipt(existing)
        raise HTTPException(409, "order could not be created")
    return order_receipt(order)


@app.get("/api/orders/by-user/{user_id}", response_model=list[schemas.OrderOut], dependencies=[Depends(require_admin)])
def orders_by_user(user_id: int, db: Session = Depends(get_db)):
    return list(db.scalars(select(models.Order).where(models.Order.user_id == user_id).order_by(models.Order.id.desc())))


def complete_order(order: models.Order, db: Session) -> models.Order:
    panel_username = f"order_{order.id}"
    existing_sub = db.scalar(select(models.Subscription).where(models.Subscription.panel_username == panel_username))
    if existing_sub:
        order.subscription_id = existing_sub.id
        order.status = "completed"
        order.decided_at = models.utcnow()
        db.commit()
        db.refresh(order)
        return order

    user = db.get(models.User, order.user_id)
    if not user:
        raise RuntimeError("order user no longer exists")
    plan = models.Plan(
        id=order.plan_id,
        name=order.plan_name,
        days=order.days,
        traffic_gb=order.traffic_gb,
        price=order.price,
        currency=order.currency,
    )
    sub = create_subscription(db, user, plan, commit=False, panel_username=panel_username)
    order.subscription_id = sub.id
    order.status = "completed"
    order.decided_at = models.utcnow()
    db.add(models.AuditLog(
        actor="api-admin",
        action="approve_order",
        entity_type="order",
        entity_id=str(order.id),
        detail=f"subscription_id={sub.id}",
    ))
    db.commit()
    db.refresh(order)
    return order


def decide_order(order_id: int, approve: bool, db: Session):
    target = "provisioning" if approve else "rejected"
    changed = db.execute(
        update(models.Order)
        .where(models.Order.id == order_id, models.Order.status == "pending")
        .values(status=target, decided_at=models.utcnow())
    )
    db.commit()
    order = db.get(models.Order, order_id)
    if not order:
        raise HTTPException(404, "order not found")
    if not changed.rowcount:
        if order.status == ("completed" if approve else "rejected"):
            return order
        raise HTTPException(409, "order already decided or requires reconciliation")

    if not approve:
        db.add(models.AuditLog(
            actor="api-admin",
            action="reject_order",
            entity_type="order",
            entity_id=str(order.id),
            detail=None,
        ))
        db.commit()
        db.refresh(order)
        return order

    try:
        return complete_order(order, db)
    except Exception as exc:
        db.rollback()
        raise HTTPException(502, "provisioning outcome requires administrator reconciliation") from exc


@app.post("/api/orders/{order_id}/approve", response_model=schemas.OrderOut, dependencies=[Depends(require_admin)])
def approve_order(order_id: int, db: Session = Depends(get_db)):
    return decide_order(order_id, True, db)


@app.post("/api/orders/{order_id}/reject", response_model=schemas.OrderOut, dependencies=[Depends(require_admin)])
def reject_order(order_id: int, db: Session = Depends(get_db)):
    return decide_order(order_id, False, db)


@app.post("/api/orders/{order_id}/reconcile", response_model=schemas.OrderOut, dependencies=[Depends(require_admin)])
def reconcile_order(order_id: int, db: Session = Depends(get_db)):
    order = db.get(models.Order, order_id)
    if not order:
        raise HTTPException(404, "order not found")
    if order.status == "completed":
        return order
    if order.status != "provisioning":
        raise HTTPException(409, "order is not awaiting reconciliation")
    try:
        return complete_order(order, db)
    except Exception as exc:
        db.rollback()
        raise HTTPException(502, "order reconciliation failed") from exc

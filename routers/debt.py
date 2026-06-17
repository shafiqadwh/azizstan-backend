"""Admin: manage debt items and payments."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from dependencies import require_min_role, get_current_user, assert_same_org
import models, schemas

router = APIRouter(prefix="/debts", tags=["debt"])

_admin = require_min_role("Admin")


# ─── Debt Items ───────────────────────────────────────────────────────────────

@router.get("/", response_model=list[schemas.DebtSummary])
def list_debts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.DebtItem).filter(
        models.DebtItem.organization_id == current_user.organization_id
    )

    # Owners see only debts for their plantations
    if current_user.role == "Owner":
        owned_ids = [po.plantation_id for po in current_user.plantation_ownerships]
        query = query.filter(models.DebtItem.plantation_id.in_(owned_ids))

    items = query.all()
    return [_build_debt_summary(item) for item in items]


@router.post("/", response_model=schemas.DebtSummary)
def create_debt(
    body: schemas.DebtItemCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_admin),
):
    plantation = db.query(models.Plantation).filter(
        models.Plantation.id == body.plantation_id,
        models.Plantation.organization_id == current_user.organization_id,
    ).first()
    if not plantation:
        raise HTTPException(status_code=404, detail="Plantation not found")

    if body.tapper_id:
        tapper = db.query(models.Tapper).filter(
            models.Tapper.id == body.tapper_id,
            models.Tapper.organization_id == current_user.organization_id,
        ).first()
        if not tapper:
            raise HTTPException(status_code=404, detail="Tapper not found")

    item = models.DebtItem(
        organization_id=current_user.organization_id,
        created_by=current_user.id,
        **body.model_dump(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _build_debt_summary(item)


@router.get("/{debt_id}", response_model=schemas.DebtSummary)
def get_debt(
    debt_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    item = _get_debt_or_404(db, debt_id)
    assert_same_org(item.organization_id, current_user)
    return _build_debt_summary(item)


@router.put("/{debt_id}")
def close_debt(
    debt_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_admin),
):
    item = _get_debt_or_404(db, debt_id)
    assert_same_org(item.organization_id, current_user)
    item.is_active = False
    db.commit()
    return {"status": "closed"}


# ─── Debt Payments ────────────────────────────────────────────────────────────

@router.post("/{debt_id}/payments", response_model=schemas.DebtPaymentOut)
def add_payment(
    debt_id: int,
    body: schemas.DebtPaymentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_admin),
):
    item = _get_debt_or_404(db, debt_id)
    assert_same_org(item.organization_id, current_user)

    if not item.is_active:
        raise HTTPException(status_code=400, detail="Debt is already closed")

    total_paid = sum(p.amount for p in item.payments)
    if total_paid + body.amount > item.total_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Payment exceeds remaining balance ({item.total_amount - total_paid:.2f})",
        )

    payment = models.DebtPayment(debt_item_id=debt_id, **body.model_dump())
    db.add(payment)

    # Auto-close debt if fully paid
    if round(total_paid + body.amount, 4) >= item.total_amount:
        item.is_active = False

    db.commit()
    db.refresh(payment)
    return payment


@router.get("/{debt_id}/payments", response_model=list[schemas.DebtPaymentOut])
def list_payments(
    debt_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    item = _get_debt_or_404(db, debt_id)
    assert_same_org(item.organization_id, current_user)
    return item.payments


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_debt_or_404(db: Session, debt_id: int) -> models.DebtItem:
    item = db.query(models.DebtItem).filter(models.DebtItem.id == debt_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Debt item not found")
    return item


def _build_debt_summary(item: models.DebtItem) -> schemas.DebtSummary:
    total_paid = sum(p.amount for p in item.payments)
    return schemas.DebtSummary(
        id=item.id,
        description=item.description,
        total_amount=item.total_amount,
        total_paid=total_paid,
        balance=item.total_amount - total_paid,
        debtor_type=item.debtor_type,
        owner_share_pct=item.owner_share_pct,
        is_active=item.is_active,
        plantation=item.plantation,
        tapper=item.tapper,
        payments=item.payments,
    )

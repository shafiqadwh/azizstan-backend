"""Buyer: create transactions. Admin/Owner: view transactions."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from dependencies import require_min_role, get_current_user, assert_same_org
import models, schemas

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("/", response_model=schemas.TransactionOut)
def create_transaction(
    body: schemas.TransactionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_min_role("Buyer")),
):
    # ── 1. Validate plot ──────────────────────────────────────────────────────
    plot = db.query(models.Plot).filter(models.Plot.id == body.plot_id).first()
    if not plot:
        raise HTTPException(status_code=404, detail="Plot not found")
    assert_same_org(plot.organization_id, current_user)

    plantation = plot.plantation

    # ── 2. Validate tapper ────────────────────────────────────────────────────
    tapper = db.query(models.Tapper).filter(
        models.Tapper.id == body.tapper_id,
        models.Tapper.organization_id == current_user.organization_id,
    ).first()
    if not tapper:
        raise HTTPException(status_code=404, detail="Tapper not found")

    # ── 3. Business logic ─────────────────────────────────────────────────────
    gross = body.rubber_weight * body.rubber_price_per_unit
    tapper_share = gross / 2
    owner_rubber_pool = gross / 2

    backteam_pct = plantation.backteam_percentage
    backteam_amount = owner_rubber_pool * (backteam_pct / 100)
    owner_rubber_net = owner_rubber_pool - backteam_amount

    # wood_income goes 100% to owners, bypasses BackTeam cut
    wood_income = body.wood_income

    # ── 4. Create transaction record ──────────────────────────────────────────
    tx = models.Transaction(
        organization_id=current_user.organization_id,
        plot_id=body.plot_id,
        tapper_id=body.tapper_id,
        buyer_id=current_user.id,
        rubber_weight=body.rubber_weight,
        rubber_price_per_unit=body.rubber_price_per_unit,
        wood_income=wood_income,
        notes=body.notes,
        gross_rubber_amount=gross,
        tapper_share=tapper_share,
        owner_rubber_pool=owner_rubber_pool,
        backteam_amount=backteam_amount,
        owner_rubber_net=owner_rubber_net,
    )
    db.add(tx)
    db.flush()  # get tx.id before creating shares

    # ── 5. BackTeam shares ────────────────────────────────────────────────────
    backteam_members = (
        db.query(models.BackTeamMember)
        .filter(models.BackTeamMember.organization_id == current_user.organization_id)
        .all()
    )
    for member in backteam_members:
        amount = backteam_amount * (member.share_percentage / 100)
        db.add(models.BackTeamShare(
            transaction_id=tx.id,
            backteam_member_id=member.id,
            user_id=member.user_id,
            share_percentage=member.share_percentage,
            amount=amount,
        ))

    # ── 6. Owner shares ───────────────────────────────────────────────────────
    plantation_owners = (
        db.query(models.PlantationOwner)
        .filter(models.PlantationOwner.plantation_id == plantation.id)
        .all()
    )
    for po in plantation_owners:
        rubber_amount = owner_rubber_net * (po.share_percentage / 100)
        wood_amount = wood_income * (po.share_percentage / 100)
        db.add(models.OwnerShare(
            transaction_id=tx.id,
            plantation_owner_id=po.id,
            owner_id=po.owner_id,
            share_percentage=po.share_percentage,
            rubber_amount=rubber_amount,
            wood_amount=wood_amount,
            total_amount=rubber_amount + wood_amount,
        ))

    db.commit()
    db.refresh(tx)
    return tx


@router.get("/", response_model=list[schemas.TransactionOut])
def list_transactions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Transaction).filter(
        models.Transaction.organization_id == current_user.organization_id
    )

    # Owners see only their plantations' transactions
    if current_user.role == "Owner":
        owned_plantation_ids = [
            po.plantation_id for po in current_user.plantation_ownerships
        ]
        plot_ids = (
            db.query(models.Plot.id)
            .filter(models.Plot.plantation_id.in_(owned_plantation_ids))
            .scalar_subquery()
        )
        query = query.filter(models.Transaction.plot_id.in_(plot_ids))

    # Buyers see only their own transactions
    elif current_user.role == "Buyer":
        query = query.filter(models.Transaction.buyer_id == current_user.id)

    return query.order_by(models.Transaction.date.desc()).all()


@router.get("/{tx_id}", response_model=schemas.TransactionOut)
def get_transaction(
    tx_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tx = db.query(models.Transaction).filter(models.Transaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    assert_same_org(tx.organization_id, current_user)
    return tx


@router.patch("/{tx_id}/mark-paid", response_model=schemas.TransactionOut)
def mark_paid(
    tx_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_min_role("Admin")),
):
    tx = db.query(models.Transaction).filter(models.Transaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    assert_same_org(tx.organization_id, current_user)
    tx.is_paid = True
    db.commit()
    db.refresh(tx)
    return tx

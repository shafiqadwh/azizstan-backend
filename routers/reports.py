"""Owner/Admin: income summary and debt overview."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user, require_min_role
import models

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/my-income")
def my_income(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_min_role("Owner")),
):
    """Owner sees their cumulative income broken down by plantation."""
    shares = (
        db.query(models.OwnerShare)
        .filter(models.OwnerShare.owner_id == current_user.id)
        .all()
    )

    total_rubber = sum(s.rubber_amount for s in shares)
    total_wood = sum(s.wood_amount for s in shares)
    total = sum(s.total_amount for s in shares)

    # Group by plantation
    by_plantation: dict[int, dict] = {}
    for s in shares:
        tx = s.transaction
        plantation = tx.plot.plantation
        pid = plantation.id
        if pid not in by_plantation:
            by_plantation[pid] = {
                "plantation_id": pid,
                "plantation_name": plantation.name,
                "rubber_amount": 0.0,
                "wood_amount": 0.0,
                "total_amount": 0.0,
                "transaction_count": 0,
            }
        by_plantation[pid]["rubber_amount"] += s.rubber_amount
        by_plantation[pid]["wood_amount"] += s.wood_amount
        by_plantation[pid]["total_amount"] += s.total_amount
        by_plantation[pid]["transaction_count"] += 1

    return {
        "owner_id": current_user.id,
        "owner_name": current_user.username,
        "total_rubber_income": total_rubber,
        "total_wood_income": total_wood,
        "total_income": total,
        "by_plantation": list(by_plantation.values()),
    }


@router.get("/my-debts")
def my_debts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_min_role("Owner")),
):
    """Owner sees outstanding and paid debts for their plantations."""
    owned_plantation_ids = [po.plantation_id for po in current_user.plantation_ownerships]

    debts = (
        db.query(models.DebtItem)
        .filter(
            models.DebtItem.plantation_id.in_(owned_plantation_ids),
            models.DebtItem.debtor_type.in_(["owner", "split"]),
        )
        .all()
    )

    result = []
    for debt in debts:
        total_paid = sum(p.amount for p in debt.payments)
        # For 'split' debts, owner only owes their percentage
        owner_owes = debt.total_amount * (debt.owner_share_pct / 100)
        owner_paid = sum(p.amount for p in debt.payments if p.paid_by == "owner")
        result.append({
            "debt_id": debt.id,
            "description": debt.description,
            "plantation": debt.plantation.name,
            "debtor_type": debt.debtor_type,
            "total_amount": debt.total_amount,
            "owner_owes": owner_owes,
            "owner_paid": owner_paid,
            "owner_balance": max(0.0, owner_owes - owner_paid),
            "is_active": debt.is_active,
        })

    return {
        "owner_id": current_user.id,
        "debts": result,
        "total_outstanding": sum(d["owner_balance"] for d in result if d["is_active"]),
    }


@router.get("/backteam-income")
def backteam_income(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_min_role("Admin")),
):
    """Admin/SuperAdmin sees BackTeam income summary."""
    shares = (
        db.query(models.BackTeamShare)
        .join(models.Transaction)
        .filter(models.Transaction.organization_id == current_user.organization_id)
        .all()
    )

    by_member: dict[int, dict] = {}
    for s in shares:
        uid = s.user_id
        if uid not in by_member:
            by_member[uid] = {
                "user_id": uid,
                "username": s.member.username,
                "share_percentage": s.share_percentage,
                "total_amount": 0.0,
                "transaction_count": 0,
            }
        by_member[uid]["total_amount"] += s.amount
        by_member[uid]["transaction_count"] += 1

    return {
        "total_backteam_income": sum(v["total_amount"] for v in by_member.values()),
        "by_member": list(by_member.values()),
    }


@router.get("/tappers")
def tapper_accounts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_min_role("Admin")),
):
    """Admin: list all tappers with their transaction summary and debt totals."""
    org_id = current_user.organization_id
    tappers = (
        db.query(models.Tapper)
        .filter(models.Tapper.organization_id == org_id)
        .all()
    )

    result = []
    for tapper in tappers:
        txs = (
            db.query(models.Transaction)
            .filter(
                models.Transaction.tapper_id == tapper.id,
                models.Transaction.organization_id == org_id,
            )
            .order_by(models.Transaction.date.desc())
            .all()
        )
        total_rubber = sum(tx.rubber_weight for tx in txs)
        total_earnings = sum(tx.tapper_share for tx in txs)
        unpaid = sum(tx.tapper_share for tx in txs if not tx.is_paid)

        # Debts assigned to this tapper
        debts = (
            db.query(models.DebtItem)
            .filter(
                models.DebtItem.tapper_id == tapper.id,
                models.DebtItem.debtor_type.in_(["tapper", "split"]),
                models.DebtItem.organization_id == org_id,
            )
            .all()
        )
        tapper_debt_total = 0.0
        for d in debts:
            if not d.is_active:
                continue
            tapper_pct = 1.0 if d.debtor_type == "tapper" else (1.0 - d.owner_share_pct / 100)
            owed = d.total_amount * tapper_pct
            paid = sum(p.amount for p in d.payments if p.paid_by == "tapper")
            tapper_debt_total += max(0.0, owed - paid)

        result.append({
            "id": tapper.id,
            "name": tapper.name,
            "phone": tapper.phone,
            "plantation_id": tapper.plantation_id,
            "plantation_name": tapper.plantation.name if tapper.plantation else "",
            "is_active": tapper.is_active,
            "transaction_count": len(txs),
            "total_rubber_kg": total_rubber,
            "total_earnings": total_earnings,
            "unpaid_earnings": unpaid,
            "outstanding_debt": tapper_debt_total,
            "recent_transactions": [
                {
                    "id": tx.id,
                    "date": tx.date.isoformat(),
                    "rubber_weight": tx.rubber_weight,
                    "rubber_price_per_unit": tx.rubber_price_per_unit,
                    "tapper_share": tx.tapper_share,
                    "is_paid": tx.is_paid,
                    "plot_name": tx.plot.name if tx.plot else "",
                }
                for tx in txs[:10]
            ],
        })

    return result


@router.get("/overview")
def admin_overview(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_min_role("Admin")),
):
    """Admin: total transactions, volume, and outstanding debts."""
    org_id = current_user.organization_id
    transactions = (
        db.query(models.Transaction)
        .filter(models.Transaction.organization_id == org_id)
        .all()
    )
    debts = (
        db.query(models.DebtItem)
        .filter(
            models.DebtItem.organization_id == org_id,
            models.DebtItem.is_active == True,
        )
        .all()
    )

    total_gross = sum(t.gross_rubber_amount for t in transactions)
    total_backteam = sum(t.backteam_amount for t in transactions)
    outstanding_debt = sum(
        d.total_amount - sum(p.amount for p in d.payments) for d in debts
    )

    return {
        "transaction_count": len(transactions),
        "total_gross_rubber": total_gross,
        "total_backteam_income": total_backteam,
        "outstanding_debt_total": outstanding_debt,
        "unpaid_transactions": sum(1 for t in transactions if not t.is_paid),
    }

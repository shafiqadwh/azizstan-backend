"""Admin: export Word documents for transactions."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from dependencies import require_min_role, assert_same_org
import models
import export as export_utils

router = APIRouter(prefix="/export", tags=["export"])

_admin = require_min_role("Admin")


@router.get("/envelope/{tx_id}")
def export_envelope(
    tx_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_admin),
):
    tx = _get_tx_or_404(db, tx_id)
    assert_same_org(tx.organization_id, current_user)
    return export_utils.generate_envelope_dl(tx)


@router.get("/a4/{tx_id}")
def export_a4(
    tx_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_admin),
):
    tx = _get_tx_or_404(db, tx_id)
    assert_same_org(tx.organization_id, current_user)
    return export_utils.generate_a4_summary(tx)


def _get_tx_or_404(db: Session, tx_id: int) -> models.Transaction:
    tx = db.query(models.Transaction).filter(models.Transaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return tx

"""SuperAdmin: manage BackTeam members and org settings."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from dependencies import require_role, get_current_user
import models, schemas

router = APIRouter(prefix="/org", tags=["organization"])

_super = require_role("SuperAdmin", "PlatformAdmin")


@router.get("/backteam", response_model=list[schemas.BackTeamMemberOut])
def list_backteam(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_super),
):
    return (
        db.query(models.BackTeamMember)
        .filter(models.BackTeamMember.organization_id == current_user.organization_id)
        .all()
    )


@router.post("/backteam", response_model=schemas.BackTeamMemberOut)
def add_backteam_member(
    body: schemas.BackTeamMemberCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_super),
):
    user = db.query(models.User).filter(
        models.User.id == body.user_id,
        models.User.organization_id == current_user.organization_id,
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found in this organization")

    if db.query(models.BackTeamMember).filter(models.BackTeamMember.user_id == body.user_id).first():
        raise HTTPException(status_code=400, detail="User is already a BackTeam member")

    _validate_backteam_total(db, current_user.organization_id, body.share_percentage)

    member = models.BackTeamMember(
        organization_id=current_user.organization_id,
        user_id=body.user_id,
        share_percentage=body.share_percentage,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.put("/backteam/{member_id}", response_model=schemas.BackTeamMemberOut)
def update_backteam_member(
    member_id: int,
    body: schemas.BackTeamMemberUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_super),
):
    member = db.query(models.BackTeamMember).filter(
        models.BackTeamMember.id == member_id,
        models.BackTeamMember.organization_id == current_user.organization_id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="BackTeam member not found")

    _validate_backteam_total(db, current_user.organization_id, body.share_percentage, exclude_id=member_id)
    member.share_percentage = body.share_percentage
    db.commit()
    db.refresh(member)
    return member


@router.delete("/backteam/{member_id}")
def remove_backteam_member(
    member_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_super),
):
    member = db.query(models.BackTeamMember).filter(
        models.BackTeamMember.id == member_id,
        models.BackTeamMember.organization_id == current_user.organization_id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="BackTeam member not found")
    db.delete(member)
    db.commit()
    return {"status": "removed"}


def _validate_backteam_total(db: Session, org_id: int, new_pct: float, exclude_id: int | None = None):
    """Ensure BackTeam percentages sum to exactly 100 after adding/updating."""
    query = db.query(models.BackTeamMember).filter(models.BackTeamMember.organization_id == org_id)
    if exclude_id:
        query = query.filter(models.BackTeamMember.id != exclude_id)
    current_total = sum(m.share_percentage for m in query.all())
    if round(current_total + new_pct, 4) > 100:
        raise HTTPException(
            status_code=400,
            detail=f"BackTeam percentages would exceed 100% (current total: {current_total}%)",
        )

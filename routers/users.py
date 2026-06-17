"""User management within an organization (Admin+)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from dependencies import require_min_role, get_current_user, assert_same_org
import models, schemas, auth as auth_utils

router = APIRouter(prefix="/users", tags=["users"])

_admin = require_min_role("Admin")


@router.get("/", response_model=list[schemas.UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_admin),
):
    return (
        db.query(models.User)
        .filter(models.User.organization_id == current_user.organization_id)
        .all()
    )


@router.post("/", response_model=schemas.UserOut)
def create_user(
    body: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_admin),
):
    if db.query(models.User).filter(models.User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    allowed_roles = {"Admin", "Owner", "Buyer"}
    if current_user.role == "SuperAdmin":
        allowed_roles.add("SuperAdmin")
    if body.role not in allowed_roles:
        raise HTTPException(status_code=403, detail=f"Cannot create role: {body.role}")

    user = models.User(
        organization_id=current_user.organization_id,
        username=body.username,
        email=body.email,
        hashed_password=auth_utils.hash_password(body.password),
        role=body.role,
        language=body.language,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/{user_id}", response_model=schemas.UserOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_admin),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    assert_same_org(user.organization_id, current_user)
    return user


@router.put("/{user_id}", response_model=schemas.UserOut)
def update_user(
    user_id: int,
    body: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_admin),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    assert_same_org(user.organization_id, current_user)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_admin),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    assert_same_org(user.organization_id, current_user)
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    user.is_active = False
    db.commit()
    return {"status": "deactivated"}

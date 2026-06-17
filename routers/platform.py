"""PlatformAdmin-only: manage organizations and seed first SuperAdmin."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from dependencies import require_role
import models, schemas, auth as auth_utils

router = APIRouter(prefix="/platform", tags=["platform"])

_platform_admin = require_role("PlatformAdmin")


@router.get("/organizations", response_model=list[schemas.Organization])
def list_orgs(db: Session = Depends(get_db), _=Depends(_platform_admin)):
    return db.query(models.Organization).all()


@router.post("/organizations", response_model=schemas.Organization)
def create_org(body: schemas.OrganizationCreate, db: Session = Depends(get_db), _=Depends(_platform_admin)):
    if db.query(models.Organization).filter(models.Organization.slug == body.slug).first():
        raise HTTPException(status_code=400, detail="Slug already taken")
    org = models.Organization(**body.model_dump())
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@router.get("/organizations/{org_id}", response_model=schemas.Organization)
def get_org(org_id: int, db: Session = Depends(get_db), _=Depends(_platform_admin)):
    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.put("/organizations/{org_id}", response_model=schemas.Organization)
def update_org(org_id: int, body: schemas.OrganizationUpdate, db: Session = Depends(get_db), _=Depends(_platform_admin)):
    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(org, field, value)
    db.commit()
    db.refresh(org)
    return org


@router.post("/organizations/{org_id}/seed-admin", response_model=schemas.UserOut)
def seed_super_admin(
    org_id: int,
    body: schemas.UserCreate,
    db: Session = Depends(get_db),
    _=Depends(_platform_admin),
):
    """Create the first SuperAdmin for an organization."""
    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    if db.query(models.User).filter(models.User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = models.User(
        organization_id=org_id,
        username=body.username,
        email=body.email,
        hashed_password=auth_utils.hash_password(body.password),
        role="SuperAdmin",
        language=body.language,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db
import models, auth

security = HTTPBearer()

ROLE_HIERARCHY = ["Buyer", "Owner", "Admin", "SuperAdmin", "PlatformAdmin"]


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> models.User:
    payload = auth.decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = (
        db.query(models.User)
        .filter(models.User.id == int(user_id), models.User.is_active == True)
        .first()
    )
    if not user:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def require_role(*roles: str):
    """Allow access only to users with one of the given roles."""
    def checker(current_user: models.User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {' or '.join(roles)}",
            )
        return current_user
    return checker


def require_min_role(min_role: str):
    """Allow access to users at or above the given role in the hierarchy."""
    def checker(current_user: models.User = Depends(get_current_user)):
        if min_role not in ROLE_HIERARCHY:
            raise HTTPException(status_code=500, detail="Invalid role config")
        user_level = ROLE_HIERARCHY.index(current_user.role) if current_user.role in ROLE_HIERARCHY else -1
        min_level = ROLE_HIERARCHY.index(min_role)
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires at least {min_role} role",
            )
        return current_user
    return checker


def get_org_id(current_user: models.User = Depends(get_current_user)) -> int:
    """Extract and validate organization_id from the current user."""
    if not current_user.organization_id:
        raise HTTPException(status_code=403, detail="No organization associated with this user")
    return current_user.organization_id


def assert_same_org(resource_org_id: int, current_user: models.User):
    """Raise 403 if resource belongs to a different org (PlatformAdmin bypasses)."""
    if current_user.role == "PlatformAdmin":
        return
    if resource_org_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Access denied: different organization")

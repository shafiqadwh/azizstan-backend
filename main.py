from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import models, auth as auth_utils
from database import engine, get_db
from routers import auth, platform, organizations, users, plantations, transactions, debt, reports, export

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="ARP API",
    description="Accounts for Rubber Plantation",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(platform.router)
app.include_router(organizations.router)
app.include_router(users.router)
app.include_router(plantations.router)
app.include_router(transactions.router)
app.include_router(debt.router)
app.include_router(reports.router)
app.include_router(export.router)


@app.get("/")
def root():
    return {"message": "ARP API v2.0", "docs": "/docs"}


@app.post("/api/seed-platform", tags=["dev"])
def seed_platform(db: Session = Depends(get_db)):
    """Dev only: create the first PlatformAdmin account."""
    if db.query(models.User).filter(models.User.role == "PlatformAdmin").first():
        return {"status": "already seeded"}

    admin = models.User(
        organization_id=None,
        username="Platform Admin",
        email="admin@arp.local",
        hashed_password=auth_utils.hash_password("admin1234"),
        role="PlatformAdmin",
        language="th",
    )
    db.add(admin)
    db.commit()
    return {
        "status": "seeded",
        "email": admin.email,
        "password": "admin1234",
        "note": "Change password immediately in production",
    }

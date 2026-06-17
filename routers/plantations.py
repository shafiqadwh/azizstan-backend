"""Admin+: manage Plantations, Plots, Tappers, and ownership assignments."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from dependencies import require_min_role, assert_same_org
import models, schemas

router = APIRouter(tags=["plantations"])

_admin = require_min_role("Admin")
_buyer = require_min_role("Buyer")  # read-only access for Buyer+


# ─── Plantations ──────────────────────────────────────────────────────────────

@router.get("/plantations", response_model=list[schemas.PlantationOut])
def list_plantations(db: Session = Depends(get_db), current_user: models.User = Depends(_buyer)):
    return (
        db.query(models.Plantation)
        .filter(models.Plantation.organization_id == current_user.organization_id)
        .all()
    )


@router.post("/plantations", response_model=schemas.PlantationOut)
def create_plantation(
    body: schemas.PlantationCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_admin),
):
    plantation = models.Plantation(organization_id=current_user.organization_id, **body.model_dump())
    db.add(plantation)
    db.commit()
    db.refresh(plantation)
    return plantation


@router.get("/plantations/{plantation_id}", response_model=schemas.PlantationOut)
def get_plantation(plantation_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(_admin)):
    p = _get_plantation_or_404(db, plantation_id)
    assert_same_org(p.organization_id, current_user)
    return p


@router.put("/plantations/{plantation_id}", response_model=schemas.PlantationOut)
def update_plantation(
    plantation_id: int,
    body: schemas.PlantationUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_admin),
):
    p = _get_plantation_or_404(db, plantation_id)
    assert_same_org(p.organization_id, current_user)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(p, field, value)
    db.commit()
    db.refresh(p)
    return p


# ─── Plantation Owners ────────────────────────────────────────────────────────

@router.get("/plantations/{plantation_id}/owners", response_model=list[schemas.PlantationOwnerOut])
def list_owners(plantation_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(_admin)):
    p = _get_plantation_or_404(db, plantation_id)
    assert_same_org(p.organization_id, current_user)
    return p.plantation_owners


@router.post("/plantations/{plantation_id}/owners", response_model=schemas.PlantationOwnerOut)
def add_owner(
    plantation_id: int,
    body: schemas.PlantationOwnerCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_admin),
):
    p = _get_plantation_or_404(db, plantation_id)
    assert_same_org(p.organization_id, current_user)

    owner = db.query(models.User).filter(
        models.User.id == body.owner_id,
        models.User.organization_id == current_user.organization_id,
        models.User.role == "Owner",
    ).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner user not found")

    if db.query(models.PlantationOwner).filter_by(
        plantation_id=plantation_id, owner_id=body.owner_id
    ).first():
        raise HTTPException(status_code=400, detail="Owner already assigned to this plantation")

    _validate_owner_total(db, plantation_id, body.share_percentage)

    po = models.PlantationOwner(plantation_id=plantation_id, **body.model_dump())
    db.add(po)
    db.commit()
    db.refresh(po)
    return po


@router.delete("/plantations/{plantation_id}/owners/{owner_id}")
def remove_owner(
    plantation_id: int,
    owner_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_admin),
):
    p = _get_plantation_or_404(db, plantation_id)
    assert_same_org(p.organization_id, current_user)
    po = db.query(models.PlantationOwner).filter_by(plantation_id=plantation_id, owner_id=owner_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="Owner assignment not found")
    db.delete(po)
    db.commit()
    return {"status": "removed"}


# ─── Plots ────────────────────────────────────────────────────────────────────

@router.get("/plantations/{plantation_id}/tappers", response_model=list[schemas.TapperOut])
def list_plantation_tappers(plantation_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(_buyer)):
    p = _get_plantation_or_404(db, plantation_id)
    assert_same_org(p.organization_id, current_user)
    return [t for t in p.tappers if t.is_active]


@router.get("/plantations/{plantation_id}/plots", response_model=list[schemas.PlotOut])
def list_plots(plantation_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(_buyer)):
    p = _get_plantation_or_404(db, plantation_id)
    assert_same_org(p.organization_id, current_user)
    return p.plots


@router.post("/plantations/{plantation_id}/plots", response_model=schemas.PlotOut)
def create_plot(
    plantation_id: int,
    body: schemas.PlotCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_admin),
):
    p = _get_plantation_or_404(db, plantation_id)
    assert_same_org(p.organization_id, current_user)
    plot = models.Plot(
        organization_id=current_user.organization_id,
        plantation_id=plantation_id,
        **body.model_dump(),
    )
    db.add(plot)
    db.commit()
    db.refresh(plot)
    return plot


@router.put("/plots/{plot_id}", response_model=schemas.PlotOut)
def update_plot(
    plot_id: int,
    body: schemas.PlotUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_admin),
):
    plot = _get_plot_or_404(db, plot_id)
    assert_same_org(plot.organization_id, current_user)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(plot, field, value)
    db.commit()
    db.refresh(plot)
    return plot


@router.post("/plots/{plot_id}/tappers")
def assign_tapper(
    plot_id: int,
    body: schemas.PlotTapperAssign,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_admin),
):
    plot = _get_plot_or_404(db, plot_id)
    assert_same_org(plot.organization_id, current_user)

    tapper = db.query(models.Tapper).filter(
        models.Tapper.id == body.tapper_id,
        models.Tapper.organization_id == current_user.organization_id,
    ).first()
    if not tapper:
        raise HTTPException(status_code=404, detail="Tapper not found")

    if db.query(models.PlotTapper).filter_by(plot_id=plot_id, tapper_id=body.tapper_id).first():
        raise HTTPException(status_code=400, detail="Tapper already assigned to this plot")

    db.add(models.PlotTapper(plot_id=plot_id, tapper_id=body.tapper_id))
    db.commit()
    return {"status": "assigned"}


@router.delete("/plots/{plot_id}/tappers/{tapper_id}")
def unassign_tapper(
    plot_id: int,
    tapper_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_admin),
):
    plot = _get_plot_or_404(db, plot_id)
    assert_same_org(plot.organization_id, current_user)
    pt = db.query(models.PlotTapper).filter_by(plot_id=plot_id, tapper_id=tapper_id).first()
    if not pt:
        raise HTTPException(status_code=404, detail="Assignment not found")
    db.delete(pt)
    db.commit()
    return {"status": "unassigned"}


# ─── Tappers ──────────────────────────────────────────────────────────────────

@router.get("/tappers", response_model=list[schemas.TapperOut])
def list_tappers(db: Session = Depends(get_db), current_user: models.User = Depends(_buyer)):
    return (
        db.query(models.Tapper)
        .filter(
            models.Tapper.organization_id == current_user.organization_id,
            models.Tapper.is_active == True,
        )
        .all()
    )


@router.get("/tappers/{tapper_id}", response_model=schemas.TapperOut)
def get_tapper(tapper_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(_buyer)):
    tapper = db.query(models.Tapper).filter(
        models.Tapper.id == tapper_id,
        models.Tapper.organization_id == current_user.organization_id,
    ).first()
    if not tapper:
        raise HTTPException(status_code=404, detail="Tapper not found")
    return tapper


@router.post("/tappers", response_model=schemas.TapperOut)
def create_tapper(
    body: schemas.TapperCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_admin),
):
    plantation = _get_plantation_or_404(db, body.plantation_id)
    assert_same_org(plantation.organization_id, current_user)
    tapper = models.Tapper(organization_id=current_user.organization_id, **body.model_dump())
    db.add(tapper)
    db.commit()
    db.refresh(tapper)
    return tapper


@router.put("/tappers/{tapper_id}", response_model=schemas.TapperOut)
def update_tapper(
    tapper_id: int,
    body: schemas.TapperUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(_admin),
):
    tapper = db.query(models.Tapper).filter(models.Tapper.id == tapper_id).first()
    if not tapper:
        raise HTTPException(status_code=404, detail="Tapper not found")
    assert_same_org(tapper.organization_id, current_user)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(tapper, field, value)
    db.commit()
    db.refresh(tapper)
    return tapper


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_plantation_or_404(db, plantation_id):
    p = db.query(models.Plantation).filter(models.Plantation.id == plantation_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Plantation not found")
    return p


def _get_plot_or_404(db, plot_id):
    p = db.query(models.Plot).filter(models.Plot.id == plot_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Plot not found")
    return p


def _validate_owner_total(db, plantation_id: int, new_pct: float, exclude_id: int | None = None):
    query = db.query(models.PlantationOwner).filter(models.PlantationOwner.plantation_id == plantation_id)
    if exclude_id:
        query = query.filter(models.PlantationOwner.id != exclude_id)
    current_total = sum(po.share_percentage for po in query.all())
    if round(current_total + new_pct, 4) > 100:
        raise HTTPException(
            status_code=400,
            detail=f"Owner shares would exceed 100% (current: {current_total}%)",
        )

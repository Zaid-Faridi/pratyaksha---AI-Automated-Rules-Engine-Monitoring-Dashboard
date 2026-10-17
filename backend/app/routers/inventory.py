"""
Sanctioned Inventory Management Router for Pratyaksha.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Centre, SanctionedInventory
from app.schemas import (
    SanctionedInventoryCreate,
    SanctionedInventoryOut,
    SanctionedInventoryUpdate,
)

router = APIRouter(prefix="/inventory", tags=["Sanctioned Inventory"])


@router.get("", response_model=List[SanctionedInventoryOut])
def list_inventory(
    centre_id: Optional[str] = None,
    zone: Optional[str] = None,
    item: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List sanctioned inventory items across centres and zones."""
    query = db.query(SanctionedInventory)
    if centre_id:
        query = query.filter(SanctionedInventory.centre_id == centre_id)
    if zone:
        query = query.filter(SanctionedInventory.zone == zone)
    if item:
        query = query.filter(SanctionedInventory.item == item)
    return query.order_by(SanctionedInventory.centre_id, SanctionedInventory.zone).all()


@router.post("", response_model=SanctionedInventoryOut, status_code=status.HTTP_201_CREATED)
def create_inventory_item(
    payload: SanctionedInventoryCreate,
    db: Session = Depends(get_db),
):
    """Add a sanctioned equipment requirement for a centre and zone."""
    centre = db.query(Centre).filter(Centre.id == payload.centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail=f"Centre '{payload.centre_id}' not found.")

    # Check if item in that zone already exists
    existing = db.query(SanctionedInventory).filter(
        SanctionedInventory.centre_id == payload.centre_id,
        SanctionedInventory.zone == payload.zone,
        SanctionedInventory.item == payload.item,
    ).first()
    if existing:
        existing.expected_count = payload.expected_count
        db.commit()
        db.refresh(existing)
        return existing

    record = SanctionedInventory(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/{inventory_id}", response_model=SanctionedInventoryOut)
def get_inventory_item(inventory_id: int, db: Session = Depends(get_db)):
    """Retrieve details for a specific inventory requirement."""
    item = db.query(SanctionedInventory).filter(SanctionedInventory.id == inventory_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"Inventory item '{inventory_id}' not found.")
    return item


@router.put("/{inventory_id}", response_model=SanctionedInventoryOut)
def update_inventory_item(
    inventory_id: int,
    payload: SanctionedInventoryUpdate,
    db: Session = Depends(get_db),
):
    """Update sanctioned inventory expected quantity or zone."""
    item = db.query(SanctionedInventory).filter(SanctionedInventory.id == inventory_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"Inventory item '{inventory_id}' not found.")

    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, val)

    db.commit()
    db.refresh(item)
    return item


@router.delete("/{inventory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_inventory_item(inventory_id: int, db: Session = Depends(get_db)):
    """Remove a sanctioned inventory item."""
    item = db.query(SanctionedInventory).filter(SanctionedInventory.id == inventory_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"Inventory item '{inventory_id}' not found.")

    db.delete(item)
    db.commit()
    return None

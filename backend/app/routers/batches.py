"""
Training Batch Management Router for Pratyaksha.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Batch, Centre
from app.schemas import BatchCreate, BatchOut, BatchUpdate

router = APIRouter(prefix="/batches", tags=["Training Batches"])


@router.get("", response_model=List[BatchOut])
def list_batches(
    centre_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List training batches with optional centre filter."""
    query = db.query(Batch)
    if centre_id:
        query = query.filter(Batch.centre_id == centre_id)
    return query.order_by(Batch.centre_id, Batch.name).all()


@router.post("", response_model=BatchOut, status_code=status.HTTP_201_CREATED)
def create_batch(
    payload: BatchCreate,
    db: Session = Depends(get_db),
):
    """Create a new training batch schedule."""
    centre = db.query(Centre).filter(Centre.id == payload.centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail=f"Centre '{payload.centre_id}' not found.")

    existing = db.query(Batch).filter(Batch.id == payload.id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Batch '{payload.id}' already exists.")

    batch = Batch(**payload.model_dump())
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


@router.get("/{batch_id}", response_model=BatchOut)
def get_batch(batch_id: str, db: Session = Depends(get_db)):
    """Retrieve details for a specific batch."""
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found.")
    return batch


@router.put("/{batch_id}", response_model=BatchOut)
def update_batch(
    batch_id: str,
    payload: BatchUpdate,
    db: Session = Depends(get_db),
):
    """Update batch timing, days, or active zone."""
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found.")

    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(batch, field, val)

    db.commit()
    db.refresh(batch)
    return batch


@router.delete("/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_batch(batch_id: str, db: Session = Depends(get_db)):
    """Delete a training batch."""
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found.")

    db.delete(batch)
    db.commit()
    return None

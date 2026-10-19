"""
Trade Profiles Router for Pratyaksha.
Manages vocational trade standards, sanctioned equipment quotas, detector prompts,
required PPE lists, and compliance check definitions per trade.
Supports zone-level overrides per centre and direct UI editing.
"""

import os
from typing import Any, Dict, List, Optional
import yaml
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Centre, TradeProfile, utcnow
from app.schemas import (
    TradeProfileCreate,
    TradeProfileOut,
    TradeProfileUpdate,
)

router = APIRouter(prefix="/trades", tags=["Trade Profiles & Standards"])


def load_seed_trade_profiles() -> Dict[str, Any]:
    """Load default trade profiles from trade_profiles.yaml if present."""
    paths = [
        "trade_profiles.yaml",
        os.path.join(os.path.dirname(__file__), "../../../trade_profiles.yaml"),
    ]
    for p in paths:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data.get("trade_profiles", {}) if data else {}
    return {}


def sync_trade_profiles_from_yaml(db: Session) -> None:
    """Ensure all default YAML trade profiles exist in the database."""
    profiles = load_seed_trade_profiles()
    for t_id, p_data in profiles.items():
        existing = db.query(TradeProfile).filter(TradeProfile.id == t_id).first()
        if not existing:
            new_tp = TradeProfile(
                id=t_id,
                name=p_data.get("name", t_id.title()),
                category=p_data.get("category", "Vocational Training"),
                description=p_data.get("description", ""),
                sanctioned_equipment=p_data.get("sanctioned_equipment", []),
                required_ppe=p_data.get("required_ppe", []),
                safety_items=p_data.get("safety_items", ["fire_extinguisher", "first_aid_box"]),
                mandatory_signage=p_data.get("mandatory_signage", ["safety_signage", "biometric_device"]),
                workstation_capacity_rule=p_data.get("workstation_capacity_rule", {}),
                compliance_checks=p_data.get("compliance_checks", {}),
            )
            db.add(new_tp)
    try:
        db.commit()
    except Exception:
        db.rollback()


@router.get("", response_model=List[TradeProfileOut])
def list_trade_profiles(db: Session = Depends(get_db)):
    """List all registered vocational trade profiles."""
    profiles = db.query(TradeProfile).all()
    if not profiles:
        sync_trade_profiles_from_yaml(db)
        profiles = db.query(TradeProfile).all()
    return profiles


@router.get("/{trade_id}", response_model=TradeProfileOut)
def get_trade_profile(trade_id: str, db: Session = Depends(get_db)):
    """Fetch a specific trade profile by ID."""
    tp = db.query(TradeProfile).filter(TradeProfile.id == trade_id).first()
    if not tp:
        sync_trade_profiles_from_yaml(db)
        tp = db.query(TradeProfile).filter(TradeProfile.id == trade_id).first()
    if not tp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trade profile '{trade_id}' not found.",
        )
    return tp


@router.post("", response_model=TradeProfileOut, status_code=status.HTTP_201_CREATED)
def create_trade_profile(payload: TradeProfileCreate, db: Session = Depends(get_db)):
    """Create a new vocational trade profile with equipment & PPE standards."""
    existing = db.query(TradeProfile).filter(TradeProfile.id == payload.id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Trade profile with ID '{payload.id}' already exists.",
        )
    tp = TradeProfile(**payload.model_dump())
    db.add(tp)
    db.commit()
    db.refresh(tp)
    return tp


@router.put("/{trade_id}", response_model=TradeProfileOut)
def update_trade_profile(
    trade_id: str,
    payload: TradeProfileUpdate,
    db: Session = Depends(get_db),
):
    """Update trade profile standards, equipment lists, and compliance parameters."""
    tp = db.query(TradeProfile).filter(TradeProfile.id == trade_id).first()
    if not tp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trade profile '{trade_id}' not found.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(tp, field, val)
    tp.updated_at = utcnow()
    db.commit()
    db.refresh(tp)
    return tp


@router.get("/centres/{centre_id}/effective", response_model=Dict[str, Any])
def get_centre_effective_trade_profile(centre_id: str, db: Session = Depends(get_db)):
    """
    Get effective trade profile standards for a specific training centre,
    merging the master trade profile with any centre/zone-level overrides.
    """
    centre = db.query(Centre).filter(Centre.id == centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail=f"Centre '{centre_id}' not found.")

    if not centre.trade_id:
        # Default fallback
        sync_trade_profiles_from_yaml(db)
        tp = db.query(TradeProfile).filter(TradeProfile.id == "it_lab").first()
    else:
        tp = db.query(TradeProfile).filter(TradeProfile.id == centre.trade_id).first()

    if not tp:
        return {
            "centre_id": centre_id,
            "trade_id": None,
            "name": "General Skilling",
            "sanctioned_equipment": [],
            "required_ppe": [],
            "safety_items": ["fire_extinguisher", "first_aid_box"],
            "mandatory_signage": ["safety_signage", "biometric_device"],
            "compliance_checks": {},
            "overrides": centre.trade_overrides or {},
        }

    # Clone base trade dictionary
    effective: Dict[str, Any] = {
        "centre_id": centre_id,
        "trade_id": tp.id,
        "name": tp.name,
        "category": tp.category,
        "description": tp.description,
        "sanctioned_equipment": list(tp.sanctioned_equipment or []),
        "required_ppe": list(tp.required_ppe or []),
        "safety_items": list(tp.safety_items or []),
        "mandatory_signage": list(tp.mandatory_signage or []),
        "workstation_capacity_rule": dict(tp.workstation_capacity_rule or {}),
        "compliance_checks": dict(tp.compliance_checks or {}),
        "overrides": centre.trade_overrides or {},
    }

    # Apply overrides if present
    overrides = centre.trade_overrides or {}
    if "sanctioned_equipment" in overrides:
        effective["sanctioned_equipment"] = overrides["sanctioned_equipment"]
    if "required_ppe" in overrides:
        effective["required_ppe"] = overrides["required_ppe"]
    if "compliance_checks" in overrides:
        effective["compliance_checks"].update(overrides["compliance_checks"])

    return effective


@router.put("/centres/{centre_id}/trade")
@router.put("/centres/{centre_id}/effective")
def update_centre_trade(
    centre_id: str,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    """Assign or update a centre's trade profile and zone-level overrides."""
    centre = db.query(Centre).filter(Centre.id == centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail=f"Centre '{centre_id}' not found.")

    if "trade_id" in payload:
        trade_id = payload["trade_id"]
        if trade_id:
            tp = db.query(TradeProfile).filter(TradeProfile.id == trade_id).first()
            if not tp:
                raise HTTPException(status_code=400, detail=f"Trade profile '{trade_id}' does not exist.")
        centre.trade_id = trade_id

    if "trade_overrides" in payload:
        centre.trade_overrides = payload["trade_overrides"]

    db.commit()
    return {
        "status": "success",
        "centre_id": centre_id,
        "trade_id": centre.trade_id,
        "trade_overrides": centre.trade_overrides,
    }

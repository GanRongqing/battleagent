# -*- coding: utf-8 -*-
"""strategy_library/router.py — FastAPI CRUD endpoints for strategy metadata."""
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .models import StrategyCreate
from .repository import StrategyConflict, get_repository


class StrategyUpdateRequest(BaseModel):
    name: Optional[str] = None
    version: Optional[str] = None
    strategy_type: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    entrypoint: Optional[str] = None
    runtime_mode: Optional[str] = None
    parent_id: Optional[str] = None
    hash: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[dict] = None


router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.post("", status_code=201)
def create_strategy(req: StrategyCreate):
    repo = get_repository()
    if req.side not in ("white", "black", "neutral", "system"):
        raise HTTPException(422, f"invalid side: {req.side}")
    if req.status not in ("experimental", "active", "frozen", "completed", "deprecated"):
        raise HTTPException(422, f"invalid status: {req.status}")
    import time
    info = req.to_info(time.strftime("%Y-%m-%dT%H:%M:%S"))
    try:
        return repo.create_strategy(info)
    except StrategyConflict:
        raise HTTPException(409, f"strategy {req.strategy_id} already exists")


@router.get("")
def list_strategies(side: Optional[str] = Query(None),
                    status: Optional[str] = Query(None),
                    strategy_type: Optional[str] = Query(None)):
    return get_repository().list_strategies(side=side, status=status,
                                            strategy_type=strategy_type)


@router.get("/{strategy_id}")
def get_strategy(strategy_id: str):
    s = get_repository().get_strategy(strategy_id)
    if s is None:
        raise HTTPException(404, f"strategy {strategy_id} not found")
    return s


@router.patch("/{strategy_id}")
def update_strategy(strategy_id: str, req: StrategyUpdateRequest):
    s = get_repository().update_strategy(strategy_id, req.dict(exclude_none=True))
    if s is None:
        raise HTTPException(404, f"strategy {strategy_id} not found")
    return s


@router.delete("/{strategy_id}", status_code=204)
def delete_strategy(strategy_id: str):
    if not get_repository().delete_strategy(strategy_id):
        raise HTTPException(404, f"strategy {strategy_id} not found")
    return None

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class TableCreate(BaseModel):
    name: str = "Deals Rummy"
    mode: str = Field(default="free", pattern="^(free|real_money)$")
    max_players: int = Field(default=4, ge=2, le=4)
    num_deals: int = Field(default=2, ge=2, le=5)
    entry_fee_paise: int = Field(default=0, ge=0)
    pool_limit: Optional[int] = Field(default=None, ge=50, le=1000)
    turn_seconds: int = Field(default=30, ge=10, le=120)
    starting_chips: int = Field(default=160, ge=1)
    is_private: bool = False


class TableOut(BaseModel):
    id: str
    name: str
    mode: str
    status: str
    max_players: int
    num_deals: int
    entry_fee_paise: int
    pool_limit: Optional[int] = None
    turn_seconds: int
    online_players: int = 0
    is_private: bool = False
    join_code: Optional[str] = None

    model_config = {"from_attributes": True}


# ---- WebSocket message payloads ------------------------------------------------------
class WSAction(BaseModel):
    action: str  # join | draw | discard | declare | drop | leave | sync
    source: Optional[str] = None            # for draw: 'stock' | 'discard'
    card: Optional[str] = None              # for discard
    groups: Optional[list[list[str]]] = None  # for declare
